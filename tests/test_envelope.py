import unittest

from muxi.transport import _unwrap_envelope


class TestEnvelope(unittest.TestCase):
    def test_unwraps_request_and_timestamp(self):
        env = {
            "object": "api_response",
            "timestamp": 123,
            "request": {"id": "req-1"},
            "data": {"foo": "bar"},
            "success": True,
        }
        out = _unwrap_envelope(env)
        self.assertEqual(out["foo"], "bar")
        self.assertEqual(out["request_id"], "req-1")
        self.assertEqual(out["timestamp"], 123)


if __name__ == "__main__":
    unittest.main()
