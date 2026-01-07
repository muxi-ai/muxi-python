import os
import unittest

from muxi.server import ServerClient, ServerConfig
from muxi.formation import FormationClient, FormationConfig
from muxi.errors import NotFoundError


def _env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise unittest.SkipTest(f"env {name} not set")
    return val


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server_url = _env("MUXI_SDK_E2E_SERVER_URL")
        key_id = _env("MUXI_SDK_E2E_KEY_ID")
        secret_key = _env("MUXI_SDK_E2E_SECRET_KEY")
        formation_id = _env("MUXI_SDK_E2E_FORMATION_ID")
        client_key = _env("MUXI_SDK_E2E_CLIENT_KEY")
        admin_key = _env("MUXI_SDK_E2E_ADMIN_KEY")

        cls.server = ServerClient(ServerConfig(url=server_url, key_id=key_id, secret_key=secret_key))
        cls.formation = FormationClient(
            FormationConfig(server_url=server_url, formation_id=formation_id, client_key=client_key, admin_key=admin_key)
        )

    def test_server_ping_health_status(self):
        size = self.server.ping()
        self.assertGreaterEqual(size, 0)
        health = self.server.health()
        self.assertIsInstance(health, dict)
        status = self.server.status()
        self.assertIsInstance(status, dict)

    def test_server_list_formations(self):
        formations = self.server.list_formations()
        self.assertIsInstance(formations, dict)

    def test_formation_health_status_config(self):
        try:
            health = self.formation.health()
            self.assertIsInstance(health, dict)
            status = self.formation.get_status()
            self.assertIsInstance(status, dict)
            config = self.formation.get_config()
            self.assertIsInstance(config, dict)
        except NotFoundError as e:
            raise unittest.SkipTest(str(e))

    def test_formation_agents(self):
        try:
            agents = self.formation.get_agents()
            self.assertIsInstance(agents, dict)
        except NotFoundError as e:
            raise unittest.SkipTest(str(e))


if __name__ == "__main__":
    unittest.main()
