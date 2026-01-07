from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .transport import Transport, TransportConfig


@dataclass
class ServerConfig:
    url: str
    key_id: str
    secret_key: str
    max_retries: int = 0
    timeout: int = 30
    debug: bool = False
    logger: Optional[logging.Logger] = None


class ServerClient:
    def __init__(self, cfg: ServerConfig):
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

    def deploy_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/deploy", payload)

    def update_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/update", payload)

    def start_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/start", {})

    def restart_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/restart", {})

    def rollback_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/rollback", {})

    def stop_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/stop", {})

    def delete_formation(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_delete(f"/rpc/formations/{formation_id}")

    def cancel_update(self, formation_id: str) -> Dict[str, Any]:
        return self._rpc_post(f"/rpc/formations/{formation_id}/cancel-update", {})

    def get_server_logs(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return self._rpc_get("/rpc/server/logs", params=params)

    def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.transport.request_json("GET", path, params=params)

    def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self.transport.request_json("POST", path, body=body)

    def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return self.transport.request_json("DELETE", path)


class AsyncServerClient:
    def __init__(self, cfg: ServerConfig):
        self._cfg = cfg
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

    async def deploy_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/deploy", payload)

    async def update_formation(self, formation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/update", payload)

    async def start_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/start", {})

    async def restart_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/restart", {})

    async def rollback_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/rollback", {})

    async def stop_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/stop", {})

    async def delete_formation(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_delete(f"/rpc/formations/{formation_id}")

    async def cancel_update(self, formation_id: str) -> Dict[str, Any]:
        return await self._rpc_post(f"/rpc/formations/{formation_id}/cancel-update", {})

    async def get_server_logs(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return await self._rpc_get("/rpc/server/logs", params=params)

    async def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", path, params=params)

    async def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", path, body=body)

    async def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", path)
