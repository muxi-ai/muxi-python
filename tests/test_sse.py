import unittest

from muxi.errors import MuxiError
from muxi.formation import (
    _normalize_chat_sse_events,
    _parse_sse_lines,
    _parse_sse_lines_async,
    parse_ui_widgets,
)


async def _aiter(lines):
    for line in lines:
        yield line


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

    def test_parse_comment_and_done_without_data(self):
        lines = [": keepalive\n", "\n", "event: done\n", "\n"]
        events = list(_parse_sse_lines(lines))
        self.assertEqual(events, [{"event": "done", "data": ""}])

    def test_parse_unknown_fields_is_safe(self):
        lines = [
            "event: message\n",
            "id: 123\n",
            "retry: 1000\n",
            "data: hello\n",
            "\n",
        ]
        events = list(_parse_sse_lines(lines))
        self.assertEqual(events, [{"event": "message", "data": "hello"}])

    def test_parse_ui_widgets_from_ui_frame(self):
        lines = [
            "event: ui\n",
            'data: {"ui":[{"type":"options","id":"w1","prompt":"Which?",'
            '"options":[{"value":"us","label":"United States"}]},'
            '{"type":"action_link","id":"w2","label":"Dash","url":"https://x.io"}]}\n',
            "\n",
        ]
        events = list(_parse_sse_lines(lines))
        self.assertEqual(len(events), 1)

        widgets = parse_ui_widgets(events[0])
        self.assertEqual(len(widgets), 2)
        self.assertEqual(widgets[0]["type"], "options")
        self.assertEqual(widgets[0]["options"][0]["label"], "United States")
        self.assertEqual(widgets[1]["url"], "https://x.io")

    def test_parse_ui_widgets_ignores_other_frames(self):
        self.assertEqual(parse_ui_widgets({"event": "message", "data": "hi"}), [])
        self.assertEqual(parse_ui_widgets({"event": "ui", "data": "not json"}), [])
        self.assertEqual(parse_ui_widgets({"event": "ui", "data": '{"ui":{}}'}), [])

    def test_chat_stream_error_is_surfaced(self):
        with self.assertRaises(MuxiError) as ctx:
            list(
                _normalize_chat_sse_events(
                    [
                        {
                            "event": "error",
                            "data": '{"error":"boom","type":"RUNTIME_ERROR"}',
                        }
                    ]
                )
            )

        self.assertEqual(ctx.exception.code, "RUNTIME_ERROR")
        self.assertEqual(ctx.exception.message, "boom")


class TestAsyncSSEParsing(unittest.IsolatedAsyncioTestCase):
    async def test_parse_async_comment_and_multiline_data(self):
        lines = [
            ": keepalive\n",
            "\n",
            "event: planning\n",
            "data: one\n",
            "data: two\n",
            "\n",
        ]
        events = [event async for event in _parse_sse_lines_async(_aiter(lines))]
        self.assertEqual(events, [{"event": "planning", "data": "one\ntwo"}])


if __name__ == "__main__":
    unittest.main()
