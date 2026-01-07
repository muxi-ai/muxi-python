import unittest

from muxi.formation import _parse_sse_lines


class TestSSEParsing(unittest.TestCase):
    def test_parse_simple_event(self):
        lines = ["event: message\n", "data: hello\n", "\n"]
        events = list(_parse_sse_lines(lines))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "message")
        self.assertEqual(events[0]["data"], "hello")

    def test_parse_multi_data(self):
        lines = ["data: one\n", "data: two\n", "\n"]
        events = list(_parse_sse_lines(lines))
        self.assertEqual(events[0]["data"], "one\ntwo")


if __name__ == "__main__":
    unittest.main()
