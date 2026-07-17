from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import parse_qs, urlsplit


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "herosms.py"
SPEC = importlib.util.spec_from_file_location("herosms_cli", MODULE_PATH)
assert SPEC and SPEC.loader
herosms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(herosms)


class FakeHeroSmsHandler(BaseHTTPRequestHandler):
    server: "FakeHeroSmsServer"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _text(self, body: str, status: int = 200) -> None:
        self._write(status, body, "text/plain; charset=utf-8")

    def _json(self, payload: Any, status: int = 200) -> None:
        self._write(
            status,
            json.dumps(payload, ensure_ascii=False),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/stubs/handler_api.php":
            self.server.legacy_queries.append(query)
            if query.get("api_key") != ["test-key"]:
                self._text("BAD_KEY")
                return
            action = query.get("action", [""])[0]
            if action == "getBalance":
                self._text("ACCESS_BALANCE:12.34")
            elif action == "getCountries":
                self._json({"0": {"id": 0, "name": "Russia"}})
            elif action == "getServicesList":
                self._json({"services": [{"code": "tg", "name": "Telegram"}]})
            elif action == "getPrices":
                self._json({"6": {"tg": {"cost": 0.25, "count": 4}}})
            elif action == "getNumber":
                self._text("ACCESS_NUMBER:1001:79990001122")
            elif action == "getNumberV2":
                self._json(
                    {
                        "activationId": "1002",
                        "phoneNumber": "79990002233",
                        "activationCost": 0.25,
                    }
                )
            elif action == "getStatus":
                self.server.status_calls += 1
                if self.server.status_calls == 1:
                    self._text("STATUS_WAIT_CODE")
                else:
                    self._text("STATUS_OK:654321")
            elif action == "getStatusV2":
                self._json({"sms": {"code": "654321", "text": "Code 654321"}})
            elif action == "setStatus":
                status_code = query.get("status", [""])[0]
                responses = {
                    "1": "ACCESS_READY",
                    "3": "ACCESS_RETRY_GET",
                    "6": "ACCESS_ACTIVATION",
                    "8": "ACCESS_CANCEL",
                }
                self._text(responses.get(status_code, "BAD_STATUS"))
            elif action == "getActiveActivations":
                self._json({"data": [{"activationId": "1002"}]})
            elif action == "getHistory":
                self._json([{"id": "1002", "phone": "79990002233"}])
            elif action == "getAllSms":
                self._json([{"code": "654321", "text": "Code 654321"}])
            elif action == "explode":
                self._text("request failed for api_key=test-key", status=500)
            else:
                self._text("BAD_ACTION")
            return

        if parsed.path == "/api/v1/activations/offers":
            authorization = self.headers.get("Authorization")
            self.server.rest_authorizations.append(authorization)
            if authorization != "ApiKey test-key":
                self._json({"title": "BAD_API_KEY", "details": "invalid"}, status=403)
                return
            self._json(
                {
                    "data": [
                        {
                            "service": "tg",
                            "country": 6,
                            "price": 0.25,
                            "count": 4,
                        }
                    ]
                }
            )
            return

        self._text("not found", status=404)


class FakeHeroSmsServer(ThreadingHTTPServer):
    legacy_queries: list[dict[str, list[str]]]
    rest_authorizations: list[str | None]
    status_calls: int


class HeroSmsCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FakeHeroSmsServer(("127.0.0.1", 0), FakeHeroSmsHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.legacy_base = f"http://{host}:{port}/stubs/handler_api.php"
        cls.rest_base = f"http://{host}:{port}/api/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self) -> None:
        self.server.legacy_queries = []
        self.server.rest_authorizations = []
        self.server.status_calls = 0
        self.client = herosms.HeroSmsClient(
            "test-key",
            legacy_base_url=self.legacy_base,
            rest_base_url=self.rest_base,
            retries=0,
        )

    def test_balance_and_number_parsing(self) -> None:
        balance = herosms.parse_balance(self.client.legacy("getBalance"))
        number = herosms.parse_number_v1(
            self.client.legacy("getNumber", service="tg", country=6, maxPrice=0.3)
        )
        self.assertEqual(balance, 12.34)
        self.assertEqual(number["activation_id"], "1001")
        self.assertEqual(number["phone_number"], "79990001122")
        self.assertEqual(self.server.legacy_queries[-1]["maxPrice"], ["0.3"])

    def test_json_catalog_and_v2_number(self) -> None:
        countries = self.client.legacy("getCountries")
        activation = self.client.legacy("getNumberV2", service="tg", country=6)
        self.assertEqual(countries["0"]["name"], "Russia")
        self.assertEqual(activation["activationId"], "1002")

    def test_poll_waits_until_code(self) -> None:
        with mock.patch.object(herosms.time, "sleep", return_value=None):
            result = herosms.poll_for_code(
                self.client,
                "1002",
                timeout=30,
                interval=1,
            )
        self.assertEqual(result["status"], "STATUS_OK")
        self.assertEqual(result["code"], "654321")
        self.assertEqual(result["attempts"], 2)

    def test_rest_offers_uses_api_key_header(self) -> None:
        payload = self.client.rest_get("activations/offers", services="tg", countries="6")
        self.assertEqual(payload["data"][0]["count"], 4)
        self.assertEqual(self.server.rest_authorizations, ["ApiKey test-key"])

    def test_api_error_is_typed(self) -> None:
        bad_client = herosms.HeroSmsClient(
            "wrong-key",
            legacy_base_url=self.legacy_base,
            rest_base_url=self.rest_base,
            retries=0,
        )
        with self.assertRaises(herosms.HeroSmsApiError) as captured:
            bad_client.legacy("getBalance")
        self.assertEqual(captured.exception.code, "BAD_KEY")
        with self.assertRaises(herosms.HeroSmsApiError) as captured_rest:
            bad_client.rest_get("activations/offers", services="tg", countries="6")
        self.assertEqual(captured_rest.exception.code, "BAD_API_KEY")

    def test_transport_error_redacts_api_key(self) -> None:
        with self.assertRaises(herosms.HeroSmsTransportError) as captured:
            self.client.legacy("explode")
        serialized = json.dumps(captured.exception.as_payload())
        self.assertNotIn("test-key", serialized)
        self.assertIn("<redacted>", serialized)

    def test_credentials_file_round_trip_and_env_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "credentials.json"
            with mock.patch.dict(
                os.environ,
                {
                    "HEROSMS_CREDENTIALS_FILE": str(path),
                    "HEROSMS_API_KEY": "",
                },
                clear=False,
            ):
                with mock.patch.object(
                    herosms,
                    "windows_user_environment_api_key",
                    return_value="",
                ):
                    herosms.save_api_key("file-key")
                    key, source = herosms.load_api_key()
                    self.assertEqual((key, source), ("file-key", "credentials_file"))
                    with mock.patch.dict(
                        os.environ,
                        {"HEROSMS_API_KEY": "env-key"},
                        clear=False,
                    ):
                        key, source = herosms.load_api_key()
                        self.assertEqual(
                            (key, source),
                            ("env-key", "process_environment"),
                        )

    def test_windows_user_environment_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "missing.json"
            with mock.patch.dict(
                os.environ,
                {
                    "HEROSMS_CREDENTIALS_FILE": str(path),
                    "HEROSMS_API_KEY": "",
                },
                clear=False,
            ):
                with mock.patch.object(
                    herosms,
                    "windows_user_environment_api_key",
                    return_value="user-env-key",
                ):
                    key, source = herosms.load_api_key()
        self.assertEqual(
            (key, source),
            ("user-env-key", "windows_user_environment"),
        )

    def test_cli_refuses_purchase_without_confirmation(self) -> None:
        stderr = io.StringIO()
        argv = [
            "--base-url",
            self.legacy_base,
            "--rest-base-url",
            self.rest_base,
            "activation",
            "buy",
            "--service",
            "tg",
            "--country",
            "6",
            "--max-price",
            "0.3",
        ]
        with mock.patch.dict(os.environ, {"HEROSMS_API_KEY": "test-key"}, clear=False):
            with contextlib.redirect_stderr(stderr):
                exit_code = herosms.main(argv)
        self.assertEqual(exit_code, 3)
        self.assertIn("CONFIRMATION_REQUIRED", stderr.getvalue())
        self.assertEqual(self.server.legacy_queries, [])

    def test_cli_purchase_sends_price_ceiling(self) -> None:
        stdout = io.StringIO()
        argv = [
            "--base-url",
            self.legacy_base,
            "--rest-base-url",
            self.rest_base,
            "activation",
            "buy",
            "--service",
            "tg",
            "--country",
            "6",
            "--max-price",
            "0.3",
            "--yes",
        ]
        with mock.patch.dict(os.environ, {"HEROSMS_API_KEY": "test-key"}, clear=False):
            with contextlib.redirect_stdout(stdout):
                exit_code = herosms.main(argv)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["activation"]["activationId"], "1002")
        self.assertEqual(self.server.legacy_queries[-1]["maxPrice"], ["0.3"])


if __name__ == "__main__":
    unittest.main()
