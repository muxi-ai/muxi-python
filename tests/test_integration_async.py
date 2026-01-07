import asyncio
import os
import unittest

from muxi.server import AsyncServerClient, ServerConfig
from muxi.formation import AsyncFormationClient, FormationConfig


def _env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise unittest.SkipTest(f"env {name} not set")
    return val


class AsyncIntegrationTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        server_url = _env("MUXI_SDK_E2E_SERVER_URL")
        key_id = _env("MUXI_SDK_E2E_KEY_ID")
        secret_key = _env("MUXI_SDK_E2E_SECRET_KEY")
        formation_id = _env("MUXI_SDK_E2E_FORMATION_ID")
        client_key = _env("MUXI_SDK_E2E_CLIENT_KEY")
        admin_key = _env("MUXI_SDK_E2E_ADMIN_KEY")

        cls.server = AsyncServerClient(ServerConfig(url=server_url, key_id=key_id, secret_key=secret_key))
        cls.formation = AsyncFormationClient(
            FormationConfig(server_url=server_url, formation_id=formation_id, client_key=client_key, admin_key=admin_key)
        )

    async def test_server_ping_health_status(self):
        size = await self.server.ping()
        self.assertGreaterEqual(size, 0)
        health = await self.server.health()
        self.assertIsInstance(health, dict)
        status = await self.server.status()
        self.assertIsInstance(status, dict)

    async def test_formation_health_status_config(self):
        health = await self.formation.health()
        self.assertIsInstance(health, dict)
        status = await self.formation.get_status()
        self.assertIsInstance(status, dict)
        config = await self.formation.get_config()
        self.assertIsInstance(config, dict)

    async def test_chat_stream(self):
        try:
            stream = await self.formation.chat_stream({"messages": [{"role": "user", "content": "hi"}]})
        except Exception as exc:
            self.skipTest(f"chat stream unavailable: {exc}")
            return

        async for evt in stream:
            self.assertIn("data", evt)
            return
        self.skipTest("chat stream returned no events")


if __name__ == "__main__":
    asyncio.run(unittest.main())
