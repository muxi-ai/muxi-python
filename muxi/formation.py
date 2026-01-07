from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Generator, Optional

from .transport import Transport, TransportConfig


@dataclass
class FormationConfig:
    url: str
    key_id: str
    secret_key: str
    max_retries: int = 0
    timeout: int = 30
    debug: bool = False
    logger: Optional[logging.Logger] = None


def _parse_sse(lines: Generator[str, None, None]):
    event: Optional[str] = None
    data_parts = []
    for line in lines:
        line = line.rstrip("\n")
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


class FormationClient:
    def __init__(self, cfg: FormationConfig):
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

    def health(self) -> Dict[str, Any]:
        return self.transport.request_json("GET", "/health")

    def status(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/formation/status")

    def config(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/formation/config")

    def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc_post("/rpc/chat", payload)

    def chat_stream(self, payload: Dict[str, Any]):
        lines = self.transport.stream_lines("POST", "/rpc/chat/stream", body=payload)
        return _parse_sse(lines)

    def get_agents(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/agents")

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return self._rpc_get(f"/rpc/agents/{agent_id}")

    def get_secrets(self) -> Dict[str, Any]:
        return self._rpc_get("/rpc/secrets")

    def set_secret(self, name: str, value: str) -> Dict[str, Any]:
        return self._rpc_post("/rpc/secrets", {"name": name, "value": value})

    def delete_secret(self, name: str) -> Dict[str, Any]:
        return self._rpc_delete(f"/rpc/secrets/{name}")

    def stream_logs(self, params: Optional[Dict[str, Any]] = None):
        lines = self.transport.stream_lines("GET", "/rpc/logs/stream", params=params)
        return _parse_sse(lines)

    def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.transport.request_json("GET", path, params=params)

    def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self.transport.request_json("POST", path, body=body)

    def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return self.transport.request_json("DELETE", path)


class AsyncFormationClient:
    def __init__(self, cfg: FormationConfig):
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

    async def health(self) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", "/health")

    async def status(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/formation/status")

    async def config(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/formation/config")

    async def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc_post("/rpc/chat", payload)

    async def chat_stream(self, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        agen = await self._transport.astream_lines("POST", "/rpc/chat/stream", body=payload)

        async def _agen():
            async for line in agen:
                # reuse parser
                for evt in _parse_sse(iter([line])):
                    yield evt

        return _agen()

    async def get_agents(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/agents")

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return await self._rpc_get(f"/rpc/agents/{agent_id}")

    async def get_secrets(self) -> Dict[str, Any]:
        return await self._rpc_get("/rpc/secrets")

    async def set_secret(self, name: str, value: str) -> Dict[str, Any]:
        return await self._rpc_post("/rpc/secrets", {"name": name, "value": value})

    async def delete_secret(self, name: str) -> Dict[str, Any]:
        return await self._rpc_delete(f"/rpc/secrets/{name}")

    async def stream_logs(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        agen = await self._transport.astream_lines("GET", "/rpc/logs/stream", params=params)

        async def _agen():
            async for line in agen:
                for evt in _parse_sse(iter([line])):
                    yield evt

        return _agen()

    async def _rpc_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._transport.arequest_json("GET", path, params=params)

    async def _rpc_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return await self._transport.arequest_json("POST", path, body=body)

    async def _rpc_delete(self, path: str) -> Dict[str, Any]:
        return await self._transport.arequest_json("DELETE", path)
