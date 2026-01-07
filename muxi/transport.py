from __future__ import annotations

import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, Optional, Tuple
from urllib import parse, request, error

from .auth import build_auth_header
from .errors import ConnectionError, map_error
from .version import __version__


DEFAULT_TIMEOUT = 30


def _unwrap_envelope(obj: Any) -> Any:
    if not isinstance(obj, dict):
        return obj
    if "data" not in obj:
        return obj
    req = obj.get("request") or {}
    request_id = req.get("id") or obj.get("request_id")
    ts = obj.get("timestamp")
    data = obj.get("data")
    if isinstance(data, dict):
        out = dict(data)
        if request_id:
            out.setdefault("request_id", request_id)
        if ts is not None:
            out.setdefault("timestamp", ts)
        return out
    return data if data is not None else obj


@dataclass
class TransportConfig:
    base_url: str
    key_id: str
    secret_key: str
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = 0
    debug: bool = False
    logger: Optional[logging.Logger] = None


class Transport:
    def __init__(self, cfg: TransportConfig):
        self.base_url = cfg.base_url.rstrip("/")
        self.key_id = cfg.key_id
        self.secret_key = cfg.secret_key
        self.timeout = cfg.timeout or DEFAULT_TIMEOUT
        self.max_retries = cfg.max_retries or 0
        self.debug = cfg.debug or bool(os.getenv("MUXI_DEBUG"))
        self.logger = cfg.logger or logging.getLogger("muxi")

    def _headers(self, method: str, path: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": build_auth_header(self.key_id, self.secret_key, method, path),
            "Content-Type": "application/json",
            "X-Muxi-SDK": f"python/{__version__}",
            "X-Muxi-Client": f"{platform.system().lower()}-{platform.machine().lower()}/py{platform.python_version()}",
            "X-Muxi-Idempotency-Key": str(uuid.uuid4()),
        }
        if extra:
            headers.update(extra)
        return headers

    def _url_and_path(self, path: str, params: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        rel = path if path.startswith("/") else f"/{path}"
        query = parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        full_path = f"{rel}?{query}" if query else rel
        return f"{self.base_url}{full_path}", full_path

    def _log(self, msg: str) -> None:
        if self.debug and self.logger:
            self.logger.debug(msg)

    def request_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Any:
        url, full_path = self._url_and_path(path, params)
        data = None
        if body is not None:
            data = json.dumps(body).encode()

        headers = self._headers(method, full_path)
        attempt = 0
        backoff = 0.5
        while True:
            req = request.Request(url, data=data, method=method, headers=headers)
            start = time.time()
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    elapsed = time.time() - start
                    self._log(f"{method} {url} -> {resp.status} ({elapsed:.3f}s)")
                    content = resp.read()
                    if not content:
                        return None
                    try:
                        parsed = json.loads(content)
                        return _unwrap_envelope(parsed)
                    except json.JSONDecodeError:
                        return content.decode(errors="ignore")
            except error.HTTPError as http_err:
                status = http_err.code
                retry_after = int(http_err.headers.get("Retry-After", "0") or 0)
                err_body = http_err.read() or b""
                try:
                    payload = json.loads(err_body) if err_body else {}
                except json.JSONDecodeError:
                    payload = {}
                code = payload.get("code") or payload.get("error") or "ERROR"
                message = payload.get("message") or http_err.reason or ""
                err_obj = map_error(status, code, message, payload if isinstance(payload, dict) else None, retry_after)
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retrying {method} {url} after {sleep_for}s due to {status}")
                    time.sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise err_obj
            except error.URLError as url_err:
                if attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retrying {method} {url} after {sleep_for}s due to connection error: {url_err.reason}")
                    time.sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise ConnectionError("CONNECTION_ERROR", str(url_err.reason), 0)

    def stream_lines(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Iterable[str]:
        url, full_path = self._url_and_path(path, params)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
        headers = self._headers(method, full_path, {"Accept": "text/event-stream"})

        req = request.Request(url, data=data, method=method, headers=headers)
        resp = request.urlopen(req, timeout=None)
        def gen() -> Generator[str, None, None]:
            try:
                for raw in resp:
                    yield raw.decode(errors="ignore")
            finally:
                resp.close()
        return gen()

    async def arequest_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Any:
        import asyncio

        return await asyncio.to_thread(self.request_json, method, path, params=params, body=body)

    async def astream_lines(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None):
        import asyncio

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def run_stream():
            try:
                for line in self.stream_lines(method, path, params=params, body=body):
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        await asyncio.to_thread(run_stream)

        async def agen():
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line

        return agen()
