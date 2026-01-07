"""HTTP transport helpers shared by server and formation clients.

Uses httpx for pooled sync/async clients, injects standard headers, idempotency keys,
and wraps responses with retry/backoff and envelope unwrapping.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

import httpx

from .auth import build_auth_header
from .errors import ConnectionError, map_error
from .version import __version__


DEFAULT_TIMEOUT = 30


def _unwrap_envelope(obj: Any) -> Any:
    """Flatten server envelope while preserving request_id/timestamp when present."""
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
    """Connection settings for the server transport."""
    base_url: str
    key_id: str
    secret_key: str
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = 0
    debug: bool = False
    logger: Optional[logging.Logger] = None


class Transport:
    """Shared HTTP client for server API (sync and async)."""
    def __init__(self, cfg: TransportConfig):
        self.base_url = cfg.base_url.rstrip("/")
        self.key_id = (cfg.key_id or "").strip()
        self.secret_key = (cfg.secret_key or "").strip()
        self.timeout = cfg.timeout or DEFAULT_TIMEOUT
        self.max_retries = cfg.max_retries or 0
        self.debug = cfg.debug or bool(os.getenv("MUXI_DEBUG"))
        self.logger = cfg.logger or logging.getLogger("muxi")
        # Keep a small, pooled client per process; callers close via context manager.
        self._client = httpx.Client(http2=False, timeout=self.timeout)
        self._aclient = httpx.AsyncClient(http2=False, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    async def aclose(self) -> None:
        await self._aclient.aclose()

    def _headers(self, method: str, path: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build base headers including auth, sdk metadata, and idempotency."""
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
        """Return absolute URL and path-with-query for signing/logging."""
        rel = path if path.startswith("/") else f"/{path}"
        query = httpx.QueryParams({k: v for k, v in (params or {}).items() if v is not None})
        full_path = f"{rel}?{query}" if query else rel
        return f"{self.base_url}{full_path}", full_path

    def _log(self, msg: str) -> None:
        if self.debug and self.logger:
            self.logger.debug(msg)

    def _should_retry(self, status: int) -> bool:
        return status in (429, 500, 502, 503, 504)

    def request_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Any:
        """Sync JSON request with retry/backoff and envelope unwrapping."""
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(method, full_path)
        attempt = 0
        backoff = 0.5
        while True:
            start = time.time()
            try:
                resp = self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                )
                elapsed = time.time() - start
                self._log(f"{method} {url} -> {resp.status_code} ({elapsed:.3f}s)")
                if resp.status_code >= 400:
                    retry_after = int(resp.headers.get("Retry-After", "0") or 0)
                    payload = None
                    try:
                        payload = resp.json()
                    except Exception:
                        payload = None
                    code = (payload or {}).get("code") or (payload or {}).get("error") or "ERROR"
                    message = (payload or {}).get("message") or resp.reason_phrase
                    err_obj = map_error(resp.status_code, code, message, payload if isinstance(payload, dict) else None, retry_after)
                    if self._should_retry(resp.status_code) and attempt < self.max_retries:
                        sleep_for = min(backoff, 30)
                        self._log(f"retrying {method} {url} after {sleep_for}s due to {resp.status_code}")
                        time.sleep(sleep_for)
                        backoff *= 2
                        attempt += 1
                        continue
                    raise err_obj

                if not resp.content:
                    return None
                try:
                    parsed = resp.json()
                    return _unwrap_envelope(parsed)
                except Exception:
                    return resp.text
            except httpx.RequestError as req_err:
                if attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retrying {method} {url} after {sleep_for}s due to connection error: {req_err}")
                    time.sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise ConnectionError("CONNECTION_ERROR", str(req_err), 0)

    def stream_lines(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Iterable[str]:
        """Sync line stream (SSE) with infinite timeout."""
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(method, full_path, {"Accept": "text/event-stream"})
        resp = self._client.stream(method, url, headers=headers, json=body, timeout=None)

        def gen():
            with resp as r:
                for line in r.iter_lines():
                    if line is None:
                        continue
                    yield line

        return gen()

    async def arequest_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None) -> Any:
        """Async JSON request with retry/backoff and envelope unwrapping."""
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(method, full_path)
        attempt = 0
        backoff = 0.5
        while True:
            start = time.time()
            try:
                resp = await self._aclient.request(
                    method,
                    url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                )
                elapsed = time.time() - start
                self._log(f"{method} {url} -> {resp.status_code} ({elapsed:.3f}s)")
                if resp.status_code >= 400:
                    retry_after = int(resp.headers.get("Retry-After", "0") or 0)
                    payload = None
                    try:
                        payload = resp.json()
                    except Exception:
                        payload = None
                    code = (payload or {}).get("code") or (payload or {}).get("error") or "ERROR"
                    message = (payload or {}).get("message") or resp.reason_phrase
                    err_obj = map_error(resp.status_code, code, message, payload if isinstance(payload, dict) else None, retry_after)
                    if self._should_retry(resp.status_code) and attempt < self.max_retries:
                        sleep_for = min(backoff, 30)
                        self._log(f"retrying {method} {url} after {sleep_for}s due to {resp.status_code}")
                        await self._sleep(sleep_for)
                        backoff *= 2
                        attempt += 1
                        continue
                    raise err_obj

                if not resp.content:
                    return None
                try:
                    parsed = resp.json()
                    return _unwrap_envelope(parsed)
                except Exception:
                    return resp.text
            except httpx.RequestError as req_err:
                if attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retrying {method} {url} after {sleep_for}s due to connection error: {req_err}")
                    await self._sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise ConnectionError("CONNECTION_ERROR", str(req_err), 0)

    async def astream_lines(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None):
        """Async line stream (SSE) with infinite timeout."""
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(method, full_path, {"Accept": "text/event-stream"})
        stream = self._aclient.stream(method, url, headers=headers, json=body, timeout=None)

        async def agen():
            async with stream as r:
                async for line in r.aiter_lines():
                    if line is None:
                        continue
                    yield line

        return agen()

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)
