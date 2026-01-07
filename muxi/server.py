"""Server (control-plane) client interfaces."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Generator, Optional

from .transport import Transport, TransportConfig
from .formation import _parse_sse_lines, _parse_sse_lines_async


@dataclass
class ServerConfig:
    """Configuration for server control-plane calls."""
    url: str
    key_id: str
    secret_key: str
    max_retries: int = 0
    timeout: int = 30
    debug: bool = False
    logger: Optional[logging.Logger] = None


class ServerClient:
    """Sync client for server control-plane APIs."""
    def __init__(self, cfg: ServerConfig | None = None, **kwargs):
        if cfg is None:
            cfg = ServerConfig(**kwargs)
        self.transport = Transport(
            TransportConfig(
                base_url=cfg.url,
                key_id=cfg.key_id,
                secret_key=cfg.secret_key,
                timeout=cfg.timeout,
                max_retries=cfg.max_retries,
                debug=cfg.debug,
                logger=cfg.logger,
            )
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.transport.close()
        except Exception:
            pass
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # Unauthenticated
    def ping(self) -> int:
        resp = self.transport.request_json("GET", "/ping")
        return len(resp) if resp else 0

    def health(self) -> Dict[str, Any]:
        return self.transport.request_json("GET", "/health")

    # Authenticated
    def status(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/server/status")

    def list_formations(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/formations")

    def get_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_get(f"/rpc/formations/{formation_id}")

    def stop_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/stop", {})

    def start_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/start", {})

    def restart_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/restart", {})

    def rollback_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/rollback", {})

    def delete_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_delete(f"/rpc/formations/{formation_id}")

    def cancel_update(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/cancel-update", {})

    def deploy_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/deploy", payload)

    def update_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/update", payload)

    def get_formation_logs(self, formation_id: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return self._rpc_get(f"/rpc/formations/{formation_id}/logs", params=params)

    def get_server_logs(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return self._rpc_get("/rpc/server/logs", params=params)

    # Streaming (SSE)
    def deploy_formation_stream(self, formation_id: str, payload: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("POST", f"/rpc/formations/{formation_id}/deploy/stream", body=payload)
        return _parse_sse_lines(lines)

    def update_formation_stream(self, formation_id: str, payload: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("POST", f"/rpc/formations/{formation_id}/update/stream", body=payload)
        return _parse_sse_lines(lines)

    def start_formation_stream(self, formation_id: str) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("POST", f"/rpc/formations/{formation_id}/start/stream", body={})
        return _parse_sse_lines(lines)

    def restart_formation_stream(self, formation_id: str) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("POST", f"/rpc/formations/{formation_id}/restart/stream", body={})
        return _parse_sse_lines(lines)

    def rollback_formation_stream(self, formation_id: str) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("POST", f"/rpc/formations/{formation_id}/rollback/stream", body={})
        return _parse_sse_lines(lines)

    def stream_formation_logs(self, formation_id: str) -> Generator[Dict[str, Any], None, None]:
        lines = self.transport.stream_lines("GET", f"/rpc/formations/{formation_id}/logs/stream")
        return _parse_sse_lines(lines)

    def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.transport.request_json("GET", path, params=params)

    def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self.transport.request_json("POST", path, body=body)

    def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return self.transport.request_json("DELETE", path)


class AsyncServerClient:
    """Async client for server control-plane APIs."""
    def __init__(self, cfg: ServerConfig | None = None, **kwargs):
        if cfg is None:
            cfg = ServerConfig(**kwargs)
        self._transport = Transport(
            TransportConfig(
                base_url=cfg.url,
                key_id=cfg.key_id,
                secret_key=cfg.secret_key,
                timeout=cfg.timeout,
                max_retries=cfg.max_retries,
                debug=cfg.debug,
                logger=cfg.logger,
            )
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._transport.aclose()
        except Exception:
            pass
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def ping(self) -> int:
        resp = await self._transport.arequest_json("GET", "/ping")
        return len(resp) if resp else 0

    async def health(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/health")

    async def status(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/server/status")

    async def list_formations(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/formations")

    async def get_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_get(f"/rpc/formations/{formation_id}")

    async def stop_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/stop", {})

    async def start_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/start", {})

    async def restart_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/restart", {})

    async def rollback_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/rollback", {})

    async def delete_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_delete(f"/rpc/formations/{formation_id}")

    async def cancel_update(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/cancel-update", {})

    async def deploy_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/deploy", payload)

    async def update_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/update", payload)

    async def get_formation_logs(self, formation_id: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return await self._rpc_get(f"/rpc/formations/{formation_id}/logs", params=params)

    async def get_server_logs(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return await self._rpc_get("/rpc/server/logs", params=params)

    async def deploy_formation_stream(self, formation_id: str, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("POST", f"/rpc/formations/{formation_id}/deploy/stream", body=payload)
        return _parse_sse_lines_async(lines)

    async def update_formation_stream(self, formation_id: str, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("POST", f"/rpc/formations/{formation_id}/update/stream", body=payload)
        return _parse_sse_lines_async(lines)

    async def start_formation_stream(self, formation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("POST", f"/rpc/formations/{formation_id}/start/stream", body={})
        return _parse_sse_lines_async(lines)

    async def restart_formation_stream(self, formation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("POST", f"/rpc/formations/{formation_id}/restart/stream", body={})
        return _parse_sse_lines_async(lines)

    async def rollback_formation_stream(self, formation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("POST", f"/rpc/formations/{formation_id}/rollback/stream", body={})
        return _parse_sse_lines_async(lines)

    async def stream_formation_logs(self, formation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        lines = await self._transport.astream_lines("GET", f"/rpc/formations/{formation_id}/logs/stream")
        return _parse_sse_lines_async(lines)

    async def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", path, params=params)

    async def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", path, body=body)

    async def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", path)
