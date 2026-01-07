import unittest

from muxi.transport import Transport, TransportConfig
from muxi.version import __version__


class TestHeaders(unittest.TestCase):
    def test_headers_include_idempotency_and_sdk(self):
        t = Transport(TransportConfig(base_url="http://example", key_id="kid", secret_key="sek"))
        headers = t._headers("GET", "/path")  # type: ignore
        self.assertIn("X-Muxi-Idempotency-Key", headers)
        self.assertTrue(headers["X-Muxi-Idempotency-Key"])  # non-empty
        self.assertEqual(headers["X-Muxi-SDK"], f"python/{__version__}")


if __name__ == "__main__":
    unittest.main()
