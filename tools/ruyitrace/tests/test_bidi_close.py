from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "bidi_close.py"
SPEC = importlib.util.spec_from_file_location("bidi_close", MODULE_PATH)
assert SPEC and SPEC.loader
bidi_close = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bidi_close
SPEC.loader.exec_module(bidi_close)


class FakeConnection:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = [json.dumps(item) for item in responses]
        self.sent: list[dict[str, object]] = []

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def recv(self) -> str:
        return self.responses.pop(0)

    def close(self) -> None:
        return None


class BidiCloseTests(unittest.TestCase):
    def test_receive_response_skips_events(self) -> None:
        connection = FakeConnection(
            [
                {"type": "event", "method": "log.entryAdded", "params": {}},
                {"type": "success", "id": 7, "result": {}},
            ]
        )
        self.assertEqual(
            bidi_close.receive_response(connection, 7),
            {"type": "success", "id": 7, "result": {}},
        )

    def test_send_command_serializes_bidi_envelope(self) -> None:
        connection = FakeConnection(
            [{"type": "success", "id": 2, "result": {}}]
        )
        bidi_close.send_command(connection, 2, "browser.close")
        self.assertEqual(
            connection.sent,
            [{"id": 2, "method": "browser.close", "params": {}}],
        )

    def test_send_command_rejects_bidi_error(self) -> None:
        connection = FakeConnection(
            [
                {
                    "type": "error",
                    "id": 1,
                    "error": "session not created",
                    "message": "fixture",
                }
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "session not created"):
            bidi_close.send_command(connection, 1, "session.new")

    def test_top_context_id_returns_first_top_level_context(self) -> None:
        self.assertEqual(
            bidi_close.top_context_id(
                {"contexts": [{"context": "top-1", "children": []}]}
            ),
            "top-1",
        )

    def test_top_context_id_rejects_empty_tree(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no top-level context"):
            bidi_close.top_context_id({"contexts": []})

    def test_navigation_error_still_requests_browser_close(self) -> None:
        connection = FakeConnection(
            [
                {"type": "success", "id": 1, "result": {"sessionId": "fixture"}},
                {
                    "type": "success",
                    "id": 2,
                    "result": {"contexts": [{"context": "top-1"}]},
                },
                {
                    "type": "error",
                    "id": 3,
                    "error": "unknown error",
                    "message": "navigation fixture",
                },
                {"type": "success", "id": 4, "result": {}},
            ]
        )
        with (
            mock.patch.object(bidi_close, "wait_for_port"),
            mock.patch.object(
                bidi_close.websocket,
                "create_connection",
                return_value=connection,
            ),
            self.assertRaisesRegex(RuntimeError, "navigation fixture"),
        ):
            bidi_close.close_browser(
                "127.0.0.1",
                9222,
                1,
                url="https://fixture.invalid/",
            )
        self.assertEqual(
            connection.sent[-2]["params"]["url"],
            "https://fixture.invalid/",
        )
        self.assertEqual(connection.sent[-1]["method"], "browser.close")


if __name__ == "__main__":
    unittest.main()
