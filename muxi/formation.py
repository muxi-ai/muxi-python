"""Formation (runtime) client interfaces and SSE helpers."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Generator, Iterable, Optional
import httpx
from urllib import parse

from .errors import ConnectionError, map_error
from .transport import _unwrap_envelope
from .version import __version__


DEFAULT_TIMEOUT = 30


@dataclass
class FormationConfig:
    """Configuration for formation (runtime) calls."""
    formation_id: str | None = None
    url: str | None = None
    server_url: str | None = None
    base_url: str | None = None
    admin_key: str | None = None
    client_key: str | None = None
    max_retries: int = 0
    timeout: int = DEFAULT_TIMEOUT
    debug: bool = False
    logger: Optional[logging.Logger] = None


def _build_base_url(cfg: FormationConfig) -> str:
    if cfg.base_url:
        return cfg.base_url.rstrip("/")
    if cfg.url:
        return cfg.url.rstrip("/") + "/v1"
    if cfg.server_url and cfg.formation_id:
        return f"{cfg.server_url.rstrip('/')}/api/{cfg.formation_id}/v1"
    raise ValueError("must set base_url, url, or server_url+formation_id")


def _parse_sse_lines(lines: Iterable[str]):
    """Parse SSE lines into event dicts (sync iterator)."""
    event: Optional[str] = None
    data_parts: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith(":"):
            continue
        if not line:
            if data_parts:
                yield {"event": event or "message", "data": "\n".join(data_parts)}
            event = None
            data_parts = []
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_parts.append(line[len("data:"):].strip())


async def _parse_sse_lines_async(lines) -> AsyncGenerator[Dict[str, Any], None]:
    """Async variant of SSE parser over an async line iterator."""
    event: Optional[str] = None
    data_parts: list[str] = []
    async for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith(":"):
            continue
        if not line:
            if data_parts:
                yield {"event": event or "message", "data": "\n".join(data_parts)}
            event = None
            data_parts = []
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_parts.append(line[len("data:"):].strip())


class _FormationTransport:
    """HTTP transport for formation API (client/admin keys, SSE)."""
    def __init__(self, base_url: str, admin_key: Optional[str], client_key: Optional[str], timeout: int, max_retries: int, debug: bool, logger: Optional[logging.Logger]):
        self.base_url = base_url.rstrip("/")
        self.admin_key = (admin_key or "").strip()
        self.client_key = (client_key or "").strip()
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_retries = max_retries or 0
        self.debug = debug or bool(os.getenv("MUXI_DEBUG"))
        self.logger = logger or logging.getLogger("muxi")
        self._client = httpx.Client(http2=False, timeout=self.timeout)
        self._aclient = httpx.AsyncClient(http2=False, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    async def aclose(self) -> None:
        await self._aclient.aclose()

    def _headers(self, *, use_admin: bool, user_id: str | None, content_type: Optional[str] = None, accept: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "X-Muxi-SDK": f"python/{__version__}",
            "X-Muxi-Client": f"python/{__version__}",
            "X-Muxi-Idempotency-Key": str(uuid.uuid4()),
        }
        if use_admin:
            if not self.admin_key:
                raise ValueError("admin key required")
            headers["X-MUXI-ADMIN-KEY"] = self.admin_key
        else:
            if not self.client_key:
                raise ValueError("client key required")
            headers["X-MUXI-CLIENT-KEY"] = self.client_key
        if user_id:
            headers["X-Muxi-User-ID"] = user_id
        if content_type:
            headers["Content-Type"] = content_type
        if accept:
            headers["Accept"] = accept
        return headers

    def _url_and_path(self, path: str, params: Optional[Dict[str, Any]]) -> tuple[str, str]:
        rel = path if path.startswith("/") else f"/{path}"
        query = httpx.QueryParams({k: v for k, v in (params or {}).items() if v is not None})
        full_path = f"{rel}?{query}" if query else rel
        return f"{self.base_url}{full_path}", full_path

    def _log(self, msg: str) -> None:
        if self.debug:
            self.logger.debug(msg)

    def _should_retry(self, status: int) -> bool:
        return status in (429, 500, 502, 503, 504)

    def request_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None, use_admin: bool = True, user_id: str = "") -> Any:
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(use_admin=use_admin, user_id=user_id, content_type="application/json" if body is not None else None)

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
                self._log(f"{method} {full_path} -> {resp.status_code} ({elapsed:.3f}s)")

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
                        self._log(f"retry {method} {full_path} after {sleep_for}s due to {resp.status_code}")
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
            except httpx.RequestError as url_err:
                if attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retry {method} {full_path} after {sleep_for}s due to connection error: {url_err}")
                    time.sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise ConnectionError("CONNECTION_ERROR", str(url_err), 0)

    def stream_sse(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None, use_admin: bool = True, user_id: str = "") -> Generator[Dict[str, Any], None, None]:
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(use_admin=use_admin, user_id=user_id, content_type="application/json" if body is not None else None, accept="text/event-stream")
        resp = self._client.stream(method, url, headers=headers, json=body, timeout=None)

        def gen() -> Generator[Dict[str, Any], None, None]:
            with resp as r:
                for evt in _parse_sse_lines(r.iter_lines()):
                    yield evt

        return gen()

    async def arequest_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None, use_admin: bool = True, user_id: str = "") -> Any:
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(use_admin=use_admin, user_id=user_id, content_type="application/json" if body is not None else None)

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
                self._log(f"{method} {full_path} -> {resp.status_code} ({elapsed:.3f}s)")

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
                        self._log(f"retry {method} {full_path} after {sleep_for}s due to {resp.status_code}")
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
            except httpx.RequestError as url_err:
                if attempt < self.max_retries:
                    sleep_for = min(backoff, 30)
                    self._log(f"retry {method} {full_path} after {sleep_for}s due to connection error: {url_err}")
                    await self._sleep(sleep_for)
                    backoff *= 2
                    attempt += 1
                    continue
                raise ConnectionError("CONNECTION_ERROR", str(url_err), 0)

    async def astream_sse(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None, use_admin: bool = True, user_id: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        url, full_path = self._url_and_path(path, params)
        headers = self._headers(use_admin=use_admin, user_id=user_id, content_type="application/json" if body is not None else None, accept="text/event-stream")
        stream = self._aclient.stream(method, url, headers=headers, json=body, timeout=None)

        async def agen():
            async with stream as r:
                async for evt in _parse_sse_lines_async(r.aiter_lines()):
                    yield evt

        return agen()

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)


class FormationClient:
    """Sync client for formation/runtime APIs."""
    def __init__(self, cfg: FormationConfig | None = None, **kwargs):
        if cfg is None:
            cfg = FormationConfig(**kwargs)
        base_url = _build_base_url(cfg)
        self._transport = _FormationTransport(base_url, cfg.admin_key, cfg.client_key, cfg.timeout, cfg.max_retries, cfg.debug, cfg.logger)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._transport.close()
        except Exception:
            pass
        return False

    # Health / status
    def health(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/health", use_admin=False)

    def get_status(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/status", use_admin=True)

    def get_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/config", use_admin=True)

    def get_formation_info(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/formation", use_admin=True)

    # Agents / MCP
    def get_agents(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/agents", use_admin=True)

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/agents/{agent_id}", use_admin=True)

    def get_mcp_servers(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/mcp/servers", use_admin=True)

    def get_mcp_server(self, server_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/mcp/servers/{server_id}", use_admin=True)

    def get_mcp_tools(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/mcp/tools", use_admin=True)

    # Secrets
    def get_secrets(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/secrets", use_admin=True)

    def get_secret(self, key: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/secrets/{key}", use_admin=True)

    def set_secret(self, key: str, value: str) -> None:
        self._transport.request_json("POST", f"/secrets/{key}", body={"value": value}, use_admin=True)

    def delete_secret(self, key: str) -> None:
        self._transport.request_json("DELETE", f"/secrets/{key}", use_admin=True)

    # Chat (client key)
    def chat(self, payload: Dict[str, Any], *, user_id: str = "") -> Dict[str, Any]:
        return self._transport.request_json("POST", "/chat", body=payload, use_admin=False, user_id=user_id)

    def chat_stream(self, payload: Dict[str, Any], *, user_id: str = "") -> Generator[Dict[str, Any], None, None]:
        body = dict(payload)
        body["stream"] = True
        return self._transport.stream_sse("POST", "/chat", body=body, use_admin=False, user_id=user_id)

    def audio_chat(self, payload: Dict[str, Any], *, user_id: str = "") -> Dict[str, Any]:
        return self._transport.request_json("POST", "/audiochat", body=payload, use_admin=False, user_id=user_id)

    def audio_chat_stream(self, payload: Dict[str, Any], *, user_id: str = "") -> Generator[Dict[str, Any], None, None]:
        body = dict(payload)
        body["stream"] = True
        return self._transport.stream_sse("POST", "/audiochat", body=body, use_admin=False, user_id=user_id)

    # Sessions / requests
    def get_sessions(self, user_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"user_id": user_id, "limit": limit}
        return self._transport.request_json("GET", "/sessions", params=params, use_admin=False, user_id=user_id)

    def get_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/sessions/{session_id}", use_admin=False, user_id=user_id)

    def get_session_messages(self, session_id: str, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/sessions/{session_id}/messages", use_admin=False, user_id=user_id)

    def restore_session(self, session_id: str, user_id: str, messages: list[Dict[str, Any]]) -> None:
        self._transport.request_json("POST", f"/sessions/{session_id}/restore", body={"messages": messages}, use_admin=False, user_id=user_id)

    def get_requests(self, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/requests", use_admin=False, user_id=user_id)

    def get_request_status(self, request_id: str, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/requests/{request_id}", use_admin=False, user_id=user_id)

    def cancel_request(self, request_id: str, user_id: str) -> None:
        self._transport.request_json("DELETE", f"/requests/{request_id}", use_admin=False, user_id=user_id)

    # Memory
    def get_memory_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/memory", use_admin=True)

    def get_memories(self, user_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"user_id": user_id, "limit": limit}
        return self._transport.request_json("GET", "/memory/user", params=params, use_admin=False)

    def add_memory(self, user_id: str, mem_type: str, detail: str) -> Dict[str, Any]:
        return self._transport.request_json("POST", "/memory", body={"user_id": user_id, "type": mem_type, "detail": detail}, use_admin=False)

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        self._transport.request_json("DELETE", f"/memory/{memory_id}?user_id={parse.quote(user_id)}", use_admin=False)

    def get_user_buffer(self, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/memory/buffer/{user_id}", use_admin=False)

    def clear_user_buffer(self, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("DELETE", f"/memory/buffer/{user_id}", use_admin=False)

    def clear_session_buffer(self, user_id: str, session_id: str) -> Dict[str, Any]:
        return self._transport.request_json("DELETE", f"/memory/buffer/{user_id}/{session_id}", use_admin=False)

    def clear_all_buffers(self) -> Dict[str, Any]:
        return self._transport.request_json("DELETE", "/memory/buffer", use_admin=True)

    def get_memory_buffers(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/memory/buffers", use_admin=True)

    def get_buffer_stats(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/memory/stats", use_admin=True)

    # Scheduler
    def get_scheduler_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/scheduler/config", use_admin=True)

    def get_scheduler_jobs(self, user_id: str) -> Dict[str, Any]:
        params = {"user_id": user_id}
        return self._transport.request_json("GET", "/scheduler/jobs", params=params, use_admin=True)

    def get_scheduler_job(self, job_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/scheduler/jobs/{job_id}", use_admin=True)

    def create_scheduler_job(self, job_type: str, schedule: str, message: str, user_id: str) -> Dict[str, Any]:
        body = {"type": job_type, "schedule": schedule, "message": message, "user_id": user_id}
        return self._transport.request_json("POST", "/scheduler/jobs", body=body, use_admin=True)

    def delete_scheduler_job(self, job_id: str) -> None:
        self._transport.request_json("DELETE", f"/scheduler/jobs/{job_id}", use_admin=True)

    # Async / logging / a2a
    def get_async_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/async", use_admin=True)

    def get_async_jobs(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/async/jobs", use_admin=True)

    def get_async_job(self, job_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/async/jobs/{job_id}", use_admin=True)

    def cancel_async_job(self, job_id: str) -> None:
        self._transport.request_json("DELETE", f"/async/jobs/{job_id}", use_admin=True)

    def get_a2a_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/a2a", use_admin=True)

    def get_logging_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/logging", use_admin=True)

    def get_logging_destinations(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/logging/destinations", use_admin=True)

    # Credentials / identifiers
    def list_credential_services(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/credentials/services", use_admin=True)

    def list_credentials(self, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/credentials", use_admin=False, user_id=user_id)

    def get_credential(self, credential_id: str, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/credentials/{credential_id}", use_admin=False, user_id=user_id)

    def create_credential(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._transport.request_json("POST", "/credentials", body=payload, use_admin=False, user_id=user_id)

    def delete_credential(self, credential_id: str, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("DELETE", f"/credentials/{credential_id}", use_admin=False, user_id=user_id)

    def get_user_identifiers(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/users/identifiers", use_admin=True)

    def get_user_identifiers_for_user(self, user_id: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/users/{user_id}/identifiers", use_admin=True)

    def link_user_identifier(self, muxi_user_id: str, identifiers: list[Any]) -> Dict[str, Any]:
        return self._transport.request_json("POST", "/users/identifiers", body={"muxi_user_id": muxi_user_id, "identifiers": identifiers}, use_admin=True)

    def unlink_user_identifier(self, identifier: str) -> None:
        self._transport.request_json("DELETE", f"/users/identifiers/{identifier}", use_admin=True)

    # Overlord / LLM
    def get_overlord_config(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/overlord", use_admin=True)

    def get_overlord_persona(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/overlord/persona", use_admin=True)

    def get_llm_settings(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/llm/settings", use_admin=True)

    # Triggers / SOP / Audit
    def get_triggers(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/triggers", use_admin=False)

    def get_trigger(self, name: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/triggers/{name}", use_admin=False)

    def fire_trigger(self, name: str, data: Any, *, async_mode: bool = False, user_id: str = "") -> Dict[str, Any]:
        params = {"async": str(async_mode).lower()}
        return self._transport.request_json("POST", f"/triggers/{name}", params=params, body=data, use_admin=False, user_id=user_id)

    def get_sops(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/sops", use_admin=False)

    def get_sop(self, name: str) -> Dict[str, Any]:
        return self._transport.request_json("GET", f"/sops/{name}", use_admin=False)

    def get_audit_log(self) -> Dict[str, Any]:
        return self._transport.request_json("GET", "/audit", use_admin=True)

    def clear_audit_log(self) -> None:
        self._transport.request_json("DELETE", "/audit?confirm=clear-audit-log", use_admin=True)

    # Events / logs streaming
    def stream_events(self, user_id: str) -> Generator[Dict[str, Any], None, None]:
        return self._transport.stream_sse("GET", f"/events/{user_id}", use_admin=False)

    def stream_request(self, user_id: str, session_id: str, request_id: str) -> Generator[Dict[str, Any], None, None]:
        return self._transport.stream_sse("GET", f"/requests/{request_id}/stream?user_id={parse.quote(user_id)}&session_id={parse.quote(session_id)}", use_admin=False)

    def stream_logs(self, filters: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        return self._transport.stream_sse("POST", "/logs/stream", body=filters or {}, use_admin=True)

    # Resolve user
    def resolve_user(self, identifier: str, create_user: bool = False) -> Dict[str, Any]:
        params = {"identifier": identifier, "create_user": str(create_user).lower()}
        return self._transport.request_json("GET", "/users/resolve", params=params, use_admin=False)


class AsyncFormationClient:
    """Async client for formation/runtime APIs."""
    def __init__(self, cfg: FormationConfig | None = None, **kwargs):
        if cfg is None:
            cfg = FormationConfig(**kwargs)
        base_url = _build_base_url(cfg)
        self._transport = _FormationTransport(base_url, cfg.admin_key, cfg.client_key, cfg.timeout, cfg.max_retries, cfg.debug, cfg.logger)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._transport.aclose()
        except Exception:
            pass
        return False

    async def health(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/health", use_admin=False)

    async def get_status(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/status", use_admin=True)

    async def get_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/config", use_admin=True)

    async def get_formation_info(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/formation", use_admin=True)

    async def get_agents(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/agents", use_admin=True)

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/agents/{agent_id}", use_admin=True)

    async def get_mcp_servers(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/mcp/servers", use_admin=True)

    async def get_mcp_server(self, server_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/mcp/servers/{server_id}", use_admin=True)

    async def get_mcp_tools(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/mcp/tools", use_admin=True)

    async def get_secrets(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/secrets", use_admin=True)

    async def get_secret(self, key: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/secrets/{key}", use_admin=True)

    async def set_secret(self, key: str, value: str) -> None:
        await self._transport.arequest_json("POST", f"/secrets/{key}", body={"value": value}, use_admin=True)

    async def delete_secret(self, key: str) -> None:
        await self._transport.arequest_json("DELETE", f"/secrets/{key}", use_admin=True)

    async def chat(self, payload: Dict[str, Any], *, user_id: str = "") -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", "/chat", body=payload, use_admin=False, user_id=user_id)

    async def chat_stream(self, payload: Dict[str, Any], *, user_id: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        body = dict(payload)
        body["stream"] = True
        return await self._transport.astream_sse("POST", "/chat", body=body, use_admin=False, user_id=user_id)

    async def audio_chat(self, payload: Dict[str, Any], *, user_id: str = "") -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", "/audiochat", body=payload, use_admin=False, user_id=user_id)

    async def audio_chat_stream(self, payload: Dict[str, Any], *, user_id: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        body = dict(payload)
        body["stream"] = True
        return await self._transport.astream_sse("POST", "/audiochat", body=body, use_admin=False, user_id=user_id)

    async def get_sessions(self, user_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"user_id": user_id, "limit": limit}
        return await self._transport.arequest_json("GET", "/sessions", params=params, use_admin=False, user_id=user_id)

    async def get_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/sessions/{session_id}", use_admin=False, user_id=user_id)

    async def get_session_messages(self, session_id: str, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/sessions/{session_id}/messages", use_admin=False, user_id=user_id)

    async def restore_session(self, session_id: str, user_id: str, messages: list[Dict[str, Any]]) -> None:
        await self._transport.arequest_json("POST", f"/sessions/{session_id}/restore", body={"messages": messages}, use_admin=False, user_id=user_id)

    async def get_requests(self, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/requests", use_admin=False, user_id=user_id)

    async def get_request_status(self, request_id: str, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/requests/{request_id}", use_admin=False, user_id=user_id)

    async def cancel_request(self, request_id: str, user_id: str) -> None:
        await self._transport.arequest_json("DELETE", f"/requests/{request_id}", use_admin=False, user_id=user_id)

    async def get_memory_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/memory", use_admin=True)

    async def get_memories(self, user_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"user_id": user_id, "limit": limit}
        return await self._transport.arequest_json("GET", "/memory/user", params=params, use_admin=False)

    async def add_memory(self, user_id: str, mem_type: str, detail: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", "/memory", body={"user_id": user_id, "type": mem_type, "detail": detail}, use_admin=False)

    async def delete_memory(self, user_id: str, memory_id: str) -> None:
        await self._transport.arequest_json("DELETE", f"/memory/{memory_id}?user_id={parse.quote(user_id)}", use_admin=False)

    async def get_user_buffer(self, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/memory/buffer/{user_id}", use_admin=False)

    async def clear_user_buffer(self, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", f"/memory/buffer/{user_id}", use_admin=False)

    async def clear_session_buffer(self, user_id: str, session_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", f"/memory/buffer/{user_id}/{session_id}", use_admin=False)

    async def clear_all_buffers(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", "/memory/buffer", use_admin=True)

    async def get_memory_buffers(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/memory/buffers", use_admin=True)

    async def get_buffer_stats(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/memory/stats", use_admin=True)

    async def get_scheduler_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/scheduler/config", use_admin=True)

    async def get_scheduler_jobs(self, user_id: str) -> Dict[str, Any]:
        params = {"user_id": user_id}
        return await self._transport.arequest_json("GET", "/scheduler/jobs", params=params, use_admin=True)

    async def get_scheduler_job(self, job_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/scheduler/jobs/{job_id}", use_admin=True)

    async def create_scheduler_job(self, job_type: str, schedule: str, message: str, user_id: str) -> Dict[str, Any]:
        body = {"type": job_type, "schedule": schedule, "message": message, "user_id": user_id}
        return await self._transport.arequest_json("POST", "/scheduler/jobs", body=body, use_admin=True)

    async def delete_scheduler_job(self, job_id: str) -> None:
        await self._transport.arequest_json("DELETE", f"/scheduler/jobs/{job_id}", use_admin=True)

    async def get_async_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/async", use_admin=True)

    async def get_async_jobs(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/async/jobs", use_admin=True)

    async def get_async_job(self, job_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/async/jobs/{job_id}", use_admin=True)

    async def cancel_async_job(self, job_id: str) -> None:
        await self._transport.arequest_json("DELETE", f"/async/jobs/{job_id}", use_admin=True)

    async def get_a2a_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/a2a", use_admin=True)

    async def get_logging_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/logging", use_admin=True)

    async def get_logging_destinations(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/logging/destinations", use_admin=True)

    async def list_credential_services(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/credentials/services", use_admin=True)

    async def list_credentials(self, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/credentials", use_admin=False, user_id=user_id)

    async def get_credential(self, credential_id: str, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/credentials/{credential_id}", use_admin=False, user_id=user_id)

    async def create_credential(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", "/credentials", body=payload, use_admin=False, user_id=user_id)

    async def delete_credential(self, credential_id: str, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", f"/credentials/{credential_id}", use_admin=False, user_id=user_id)

    async def get_user_identifiers(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/users/identifiers", use_admin=True)

    async def get_user_identifiers_for_user(self, user_id: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/users/{user_id}/identifiers", use_admin=True)

    async def link_user_identifier(self, muxi_user_id: str, identifiers: list[Any]) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", "/users/identifiers", body={"muxi_user_id": muxi_user_id, "identifiers": identifiers}, use_admin=True)

    async def unlink_user_identifier(self, identifier: str) -> None:
        await self._transport.arequest_json("DELETE", f"/users/identifiers/{identifier}", use_admin=True)

    async def get_overlord_config(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/overlord", use_admin=True)

    async def get_overlord_persona(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/overlord/persona", use_admin=True)

    async def get_llm_settings(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/llm/settings", use_admin=True)

    async def get_triggers(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/triggers", use_admin=False)

    async def get_trigger(self, name: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/triggers/{name}", use_admin=False)

    async def fire_trigger(self, name: str, data: Any, *, async_mode: bool = False, user_id: str = "") -> Dict[str, Any]:
        params = {"async": str(async_mode).lower()}
        return await self._transport.arequest_json("POST", f"/triggers/{name}", params=params, body=data, use_admin=False, user_id=user_id)

    async def get_sops(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/sops", use_admin=False)

    async def get_sop(self, name: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", f"/sops/{name}", use_admin=False)

    async def get_audit_log(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/audit", use_admin=True)

    async def clear_audit_log(self) -> None:
        await self._transport.arequest_json("DELETE", "/audit?confirm=clear-audit-log", use_admin=True)

    async def stream_events(self, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        return await self._transport.astream_sse("GET", f"/events/{user_id}", use_admin=False)

    async def stream_request(self, user_id: str, session_id: str, request_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        return await self._transport.astream_sse("GET", f"/requests/{request_id}/stream?user_id={parse.quote(user_id)}&session_id={parse.quote(session_id)}", use_admin=False)

    async def stream_logs(self, filters: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        return await self._transport.astream_sse("POST", "/logs/stream", body=filters or {}, use_admin=True)

    async def resolve_user(self, identifier: str, create_user: bool = False) -> Dict[str, Any]:
        params = {"identifier": identifier, "create_user": str(create_user).lower()}
        return await self._transport.arequest_json("GET", "/users/resolve", params=params, use_admin=False)
