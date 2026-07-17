#!/usr/bin/env python3
"""Dependency-free HeroSMS CLI for the SMS-Activate compatible API."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_LEGACY_BASE_URL = "https://hero-sms.com/stubs/handler_api.php"
DEFAULT_REST_BASE_URL = "https://hero-sms.com/api/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 2
DEFAULT_POLL_INTERVAL = 5.0
USER_AGENT = "reverse_ENV-herosms-api/1.0"

API_ERROR_MESSAGES = {
    "ACCOUNT_INACTIVE": "HeroSMS account is inactive",
    "BAD_ACTION": "Unsupported HeroSMS API action",
    "BAD_API_KEY": "Invalid HeroSMS REST API key",
    "BAD_COUNTRY": "Unknown or unsupported country",
    "BAD_KEY": "Invalid HeroSMS API key",
    "BAD_OPERATOR": "Unknown or unsupported operator",
    "BAD_SERVICE": "Unknown or unsupported service code",
    "BAD_STATUS": "Invalid activation status transition",
    "BANNED": "HeroSMS API access is temporarily banned",
    "CHANNELS_LIMIT": "HeroSMS activation channel limit reached",
    "EARLY_CANCEL_DENIED": "Activation cannot be cancelled yet",
    "ERROR_SQL": "HeroSMS internal database error",
    "NO_ACTIVATION": "Activation was not found",
    "NO_ACTIVATIONS": "No activations were found",
    "NO_BALANCE": "Insufficient HeroSMS balance",
    "NO_BALANCE_FORWARD": "Insufficient balance for forwarding",
    "NO_KEY": "HeroSMS API key is missing",
    "NO_NUMBERS": "No numbers are currently available",
    "OPERATORS_NOT_FOUND": "No matching operators were found",
    "ORDER_ALREADY_EXISTS": "A matching activation order already exists",
    "WRONG_ACTIVATION_ID": "Invalid activation ID",
    "WRONG_EXCEPTION_PHONE": "Invalid phone-exclusion prefix",
    "WRONG_MAX_PRICE": "Maximum price is below the current minimum",
}

STATUS_MESSAGES = {
    "STATUS_WAIT_CODE": "Waiting for the first SMS",
    "STATUS_WAIT_RETRY": "Waiting for a replacement SMS",
    "STATUS_WAIT_RESEND": "Waiting for the user to request another SMS",
    "STATUS_CANCEL": "Activation was cancelled",
    "STATUS_OK": "SMS code received",
}

MUTATING_STATUS_CODES = {
    "ready": 1,
    "resend": 3,
    "complete": 6,
    "cancel": 8,
}


class HeroSmsError(Exception):
    """Base error carrying a stable machine-readable code."""

    exit_code = 1

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"ok": False, "error": error}


class HeroSmsConfigError(HeroSmsError):
    exit_code = 3


class HeroSmsApiError(HeroSmsError):
    exit_code = 4


class HeroSmsPollTimeout(HeroSmsError):
    exit_code = 5


class HeroSmsTransportError(HeroSmsError):
    exit_code = 6


def _compact_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def _decode_body(raw: bytes, content_type: str | None = None) -> str:
    charset = "utf-8"
    if content_type:
        match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
        if match:
            charset = match.group(1).strip('"\'')
    try:
        return raw.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def parse_payload(text: str) -> Any:
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        return None
    if stripped[:1] in {"{", "["}:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return stripped


def redact_text(value: str, secrets: Iterable[str] = ()) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(
        r"(?i)(api_key=)[^&\s]+",
        r"\1<redacted>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*)(?:apikey\s+)?[^\s,;]+",
        r"\1<redacted>",
        redacted,
    )
    return redacted


def redact_value(value: Any, secrets: Iterable[str] = ()) -> Any:
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {
            key: redact_value(item, secrets)
            for key, item in value.items()
            if str(key).lower() not in {"api_key", "token", "authorization"}
        }
    if isinstance(value, list):
        return [redact_value(item, secrets) for item in value]
    return value


def _body_excerpt(payload: Any, *, secrets: Iterable[str]) -> str:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return redact_text(text, secrets)[:500]


def api_error_from_payload(
    payload: Any,
    *,
    secrets: Iterable[str] = (),
) -> HeroSmsApiError | None:
    if isinstance(payload, str):
        prefix = payload.split(":", 1)[0].strip().upper()
        if prefix in API_ERROR_MESSAGES:
            details: dict[str, Any] = {"response": redact_text(payload, secrets)}
            if ":" in payload:
                details["value"] = redact_text(payload.split(":", 1)[1], secrets)
            return HeroSmsApiError(
                prefix,
                API_ERROR_MESSAGES[prefix],
                details=details,
            )
        return None

    if not isinstance(payload, dict):
        return None

    candidates = [payload.get("title"), payload.get("error"), payload.get("code")]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        code = candidate.strip().upper()
        if code in API_ERROR_MESSAGES:
            details = redact_value(payload, secrets)
            return HeroSmsApiError(
                code,
                redact_text(
                    str(payload.get("details") or API_ERROR_MESSAGES[code]),
                    secrets,
                ),
                details=details,
            )
    return None


def parse_balance(payload: Any) -> float:
    if isinstance(payload, (int, float)):
        return float(payload)
    if isinstance(payload, str) and payload.startswith("ACCESS_BALANCE:"):
        try:
            return float(payload.split(":", 1)[1])
        except ValueError as exc:
            raise HeroSmsApiError(
                "UNEXPECTED_RESPONSE",
                "HeroSMS returned an invalid balance",
                details={"response": payload},
            ) from exc
    if isinstance(payload, dict):
        for key in ("amount", "balance"):
            if key in payload:
                try:
                    return float(payload[key])
                except (TypeError, ValueError) as exc:
                    raise HeroSmsApiError(
                        "UNEXPECTED_RESPONSE",
                        "HeroSMS returned an invalid balance",
                        details={"response": payload},
                    ) from exc
    raise HeroSmsApiError(
        "UNEXPECTED_RESPONSE",
        "HeroSMS balance response was not recognized",
        details={"response": payload},
    )


def parse_number_v1(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, str):
        raise HeroSmsApiError(
            "UNEXPECTED_RESPONSE",
            "HeroSMS getNumber response was not text",
            details={"response": payload},
        )
    match = re.fullmatch(r"ACCESS_NUMBER:([^:]+):(.+)", payload)
    if not match:
        raise HeroSmsApiError(
            "UNEXPECTED_RESPONSE",
            "HeroSMS getNumber response was not recognized",
            details={"response": payload},
        )
    return {"activation_id": match.group(1), "phone_number": match.group(2)}


def parse_status(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, str):
        raise HeroSmsApiError(
            "UNEXPECTED_RESPONSE",
            "HeroSMS getStatus response was not text",
            details={"response": payload},
        )
    status, separator, value = payload.partition(":")
    status = status.strip().upper()
    if status not in STATUS_MESSAGES:
        raise HeroSmsApiError(
            "UNEXPECTED_RESPONSE",
            "HeroSMS getStatus response was not recognized",
            details={"response": payload},
        )
    parsed: dict[str, Any] = {
        "status": status,
        "message": STATUS_MESSAGES[status],
    }
    if separator and value:
        if status in {"STATUS_OK", "STATUS_WAIT_RETRY"}:
            parsed["code"] = value
        else:
            parsed["value"] = value
    return parsed


def credentials_path() -> Path:
    override = os.environ.get("HEROSMS_CREDENTIALS_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".herosms" / "credentials.json"


def windows_user_environment_api_key() -> str:
    """Read HEROSMS_API_KEY from HKCU for already-running Windows sessions."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "HEROSMS_API_KEY")
    except (FileNotFoundError, OSError):
        return ""
    return value.strip() if isinstance(value, str) else ""


def _read_key_from_file(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise HeroSmsConfigError(
            "API_KEY_MISSING",
            "HeroSMS API key is not configured",
            details={"credentials_file": str(path)},
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HeroSmsConfigError(
            "CREDENTIALS_INVALID",
            "HeroSMS credentials file is unreadable or invalid JSON",
            details={"credentials_file": str(path)},
        ) from exc
    key = payload.get("api_key") if isinstance(payload, dict) else None
    if not isinstance(key, str) or not key.strip():
        raise HeroSmsConfigError(
            "CREDENTIALS_INVALID",
            "HeroSMS credentials file does not contain api_key",
            details={"credentials_file": str(path)},
        )
    return key.strip()


def load_api_key() -> tuple[str, str]:
    environment_key = os.environ.get("HEROSMS_API_KEY", "").strip()
    if environment_key:
        return environment_key, "process_environment"
    user_environment_key = windows_user_environment_api_key()
    if user_environment_key:
        return user_environment_key, "windows_user_environment"
    path = credentials_path()
    return _read_key_from_file(path), "credentials_file"


def save_api_key(api_key: str) -> Path:
    key = api_key.strip()
    if not key:
        raise HeroSmsConfigError("API_KEY_EMPTY", "HeroSMS API key cannot be empty")
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="credentials-",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"api_key": key}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        try:
            os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return path


def clear_api_key() -> tuple[Path, bool]:
    path = credentials_path()
    if not path.exists():
        return path, False
    path.unlink()
    return path, True


class HeroSmsClient:
    """Small HTTP client for HeroSMS legacy and REST catalog endpoints."""

    def __init__(
        self,
        api_key: str,
        *,
        legacy_base_url: str = DEFAULT_LEGACY_BASE_URL,
        rest_base_url: str = DEFAULT_REST_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        if timeout <= 0:
            raise HeroSmsConfigError("BAD_TIMEOUT", "HTTP timeout must be positive")
        if retries < 0:
            raise HeroSmsConfigError("BAD_RETRIES", "HTTP retries cannot be negative")
        self.api_key = api_key
        self.legacy_base_url = legacy_base_url.rstrip("?")
        self.rest_base_url = rest_base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def _request(self, request: Request) -> Any:
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    text = _decode_body(raw, response.headers.get("Content-Type"))
                    payload = parse_payload(text)
                    api_error = api_error_from_payload(
                        payload,
                        secrets=(self.api_key,),
                    )
                    if api_error:
                        raise api_error
                    return payload
            except HeroSmsApiError:
                raise
            except HTTPError as exc:
                raw = exc.read()
                payload = parse_payload(_decode_body(raw, exc.headers.get("Content-Type")))
                api_error = api_error_from_payload(
                    payload,
                    secrets=(self.api_key,),
                )
                if api_error:
                    raise api_error from exc

                retry_after = exc.headers.get("Retry-After")
                retry_delay = 0.0
                if retry_after:
                    try:
                        retry_delay = max(0.0, float(retry_after))
                    except ValueError:
                        retry_delay = 0.0
                retryable_400 = exc.code == 400 and re.search(
                    r"1020|rate|too many",
                    str(payload),
                    flags=re.IGNORECASE,
                )
                retryable = exc.code in {429, 500, 502, 503, 504} or bool(retryable_400)
                if retryable and attempt < self.retries:
                    time.sleep(max(retry_delay, min(10.0, 2.0**attempt)))
                    continue

                raise HeroSmsTransportError(
                    "HTTP_ERROR",
                    f"HeroSMS returned HTTP {exc.code}",
                    details={
                        "status": exc.code,
                        "response_excerpt": _body_excerpt(
                            payload,
                            secrets=(self.api_key,),
                        ),
                    },
                ) from exc
            except URLError as exc:
                reason = redact_text(str(exc.reason), (self.api_key,))
                if attempt < self.retries:
                    time.sleep(min(10.0, 2.0**attempt))
                    continue
                raise HeroSmsTransportError(
                    "NETWORK_ERROR",
                    "Could not reach the HeroSMS API",
                    details={"reason": reason[:500]},
                ) from exc
            except TimeoutError as exc:
                if attempt < self.retries:
                    time.sleep(min(10.0, 2.0**attempt))
                    continue
                raise HeroSmsTransportError(
                    "NETWORK_TIMEOUT",
                    "HeroSMS API request timed out",
                ) from exc

        raise AssertionError("unreachable")

    def legacy(self, action: str, **params: Any) -> Any:
        query = urlencode(
            {
                "api_key": self.api_key,
                "action": action,
                **_compact_params(params),
            },
            doseq=True,
        )
        separator = "&" if "?" in self.legacy_base_url else "?"
        request = Request(
            f"{self.legacy_base_url}{separator}{query}",
            headers={
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.1",
                "User-Agent": USER_AGENT,
            },
            method="GET",
        )
        return self._request(request)

    def rest_get(self, path: str, **params: Any) -> Any:
        query = urlencode(_compact_params(params), doseq=True)
        url = f"{self.rest_base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"ApiKey {self.api_key}",
                "User-Agent": USER_AGENT,
            },
            method="GET",
        )
        return self._request(request)


def poll_for_code(
    client: HeroSmsClient,
    activation_id: str,
    *,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    if timeout <= 0:
        raise HeroSmsConfigError("BAD_POLL_TIMEOUT", "Poll timeout must be positive")
    if interval < 1.0:
        raise HeroSmsConfigError(
            "BAD_POLL_INTERVAL",
            "Poll interval must be at least 1 second",
        )

    deadline = time.monotonic() + timeout
    attempts = 0
    last_status: dict[str, Any] | None = None
    while True:
        attempts += 1
        last_status = parse_status(client.legacy("getStatus", id=activation_id))
        status = last_status["status"]
        if status == "STATUS_OK":
            return {
                "activation_id": activation_id,
                "attempts": attempts,
                **last_status,
            }
        if status == "STATUS_CANCEL":
            raise HeroSmsApiError(
                "ACTIVATION_CANCELLED",
                "Activation was cancelled before an SMS code arrived",
                details={"activation_id": activation_id, "last_status": last_status},
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HeroSmsPollTimeout(
                "POLL_TIMEOUT",
                "Timed out waiting for a HeroSMS code",
                details={
                    "activation_id": activation_id,
                    "attempts": attempts,
                    "last_status": last_status,
                },
            )
        time.sleep(min(interval, remaining))


def _emit(payload: dict[str, Any], *, pretty: bool, stream: Any | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    json.dump(
        payload,
        stream,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    stream.write("\n")


def _require_yes(args: argparse.Namespace, operation: str) -> None:
    if not getattr(args, "yes", False):
        raise HeroSmsConfigError(
            "CONFIRMATION_REQUIRED",
            f"{operation} changes account state; rerun with --yes",
        )


def _client_from_args(args: argparse.Namespace) -> tuple[HeroSmsClient, str]:
    api_key, source = load_api_key()
    return (
        HeroSmsClient(
            api_key,
            legacy_base_url=args.base_url,
            rest_base_url=args.rest_base_url,
            timeout=args.timeout,
            retries=args.retries,
        ),
        source,
    )


def command_config_path(args: argparse.Namespace) -> dict[str, Any]:
    return {"ok": True, "credentials_file": str(credentials_path())}


def command_config_show(args: argparse.Namespace) -> dict[str, Any]:
    path = credentials_path()
    process_environment_configured = bool(
        os.environ.get("HEROSMS_API_KEY", "").strip()
    )
    user_environment_configured = bool(windows_user_environment_api_key())
    file_configured = False
    file_valid = None
    if path.exists():
        try:
            _read_key_from_file(path)
            file_configured = True
            file_valid = True
        except HeroSmsConfigError:
            file_valid = False
    if process_environment_configured:
        source = "process_environment"
    elif user_environment_configured:
        source = "windows_user_environment"
    elif file_configured:
        source = "credentials_file"
    else:
        source = None
    return {
        "ok": True,
        "configured": bool(source),
        "source": source,
        "environment_configured": (
            process_environment_configured or user_environment_configured
        ),
        "process_environment_configured": process_environment_configured,
        "windows_user_environment_configured": user_environment_configured,
        "credentials_file": str(path),
        "credentials_file_exists": path.exists(),
        "credentials_file_valid": file_valid,
    }


def command_config_set(args: argparse.Namespace) -> dict[str, Any]:
    if args.stdin:
        key = sys.stdin.readline().strip()
    else:
        key = getpass.getpass("HeroSMS API key: ").strip()
        confirmation = getpass.getpass("Repeat HeroSMS API key: ").strip()
        if key != confirmation:
            raise HeroSmsConfigError("API_KEY_MISMATCH", "API key values did not match")
    path = save_api_key(key)
    return {"ok": True, "configured": True, "credentials_file": str(path)}


def command_config_clear(args: argparse.Namespace) -> dict[str, Any]:
    _require_yes(args, "Clearing the HeroSMS API key")
    path, removed = clear_api_key()
    return {
        "ok": True,
        "credentials_file": str(path),
        "removed": removed,
        "environment_key_still_set": bool(
            os.environ.get("HEROSMS_API_KEY", "").strip()
            or windows_user_environment_api_key()
        ),
    }


def command_health(args: argparse.Namespace) -> dict[str, Any]:
    client, source = _client_from_args(args)
    balance = parse_balance(client.legacy("getBalance"))
    return {
        "ok": True,
        "credential_source": source,
        "legacy_base_url": redact_text(args.base_url, (client.api_key,)),
        "balance": balance,
    }


def command_balance(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {"ok": True, "balance": parse_balance(client.legacy("getBalance"))}


def command_countries(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {"ok": True, "data": client.legacy("getCountries")}


def command_services(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "data": client.legacy("getServicesList", country=args.country, lang=args.lang),
    }


def command_operators(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {"ok": True, "data": client.legacy("getOperators", country=args.country)}


def command_prices(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "data": client.legacy("getPrices", service=args.service, country=args.country),
    }


def command_top_countries(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    action = "getTopCountriesByServiceRank" if args.rank else "getTopCountriesByService"
    return {
        "ok": True,
        "data": client.legacy(
            action,
            service=args.service,
            freePrice="true" if args.free_price else None,
        ),
    }


def command_offers(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "data": client.rest_get(
            "activations/offers",
            services=args.services,
            countries=args.countries,
        ),
    }


def command_buy(args: argparse.Namespace) -> dict[str, Any]:
    _require_yes(args, "Buying a HeroSMS number")
    client, _ = _client_from_args(args)
    params = {
        "service": args.service,
        "country": args.country,
        "operator": args.operator,
        "maxPrice": args.max_price,
        "fixedPrice": 1 if args.fixed_price else None,
        "phoneException": args.phone_exception,
        "ref": args.ref,
    }
    if args.v1:
        activation = parse_number_v1(client.legacy("getNumber", **params))
        protocol = "legacy-v1"
    else:
        activation = client.legacy("getNumberV2", **params)
        protocol = "legacy-v2"
    return {"ok": True, "protocol": protocol, "activation": activation}


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    if args.v2:
        return {
            "ok": True,
            "activation_id": args.id,
            "data": client.legacy("getStatusV2", id=args.id),
        }
    return {
        "ok": True,
        "activation_id": args.id,
        **parse_status(client.legacy("getStatus", id=args.id)),
    }


def command_poll(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {"ok": True, **poll_for_code(
        client,
        args.id,
        timeout=args.poll_timeout,
        interval=args.interval,
    )}


def command_set_status(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.activation_command
    _require_yes(args, f"HeroSMS activation {operation}")
    client, _ = _client_from_args(args)
    result = client.legacy(
        "setStatus",
        id=args.id,
        status=MUTATING_STATUS_CODES[operation],
    )
    return {
        "ok": True,
        "activation_id": args.id,
        "operation": operation,
        "result": result,
    }


def command_active(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "data": client.legacy(
            "getActiveActivations",
            start=args.start,
            limit=args.limit,
        ),
    }


def command_history(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "data": client.legacy(
            "getHistory",
            start=args.start,
            end=args.end,
            offset=args.offset,
            size=args.size,
        ),
    }


def command_sms(args: argparse.Namespace) -> dict[str, Any]:
    client, _ = _client_from_args(args)
    return {
        "ok": True,
        "activation_id": args.id,
        "data": client.legacy(
            "getAllSms",
            id=args.id,
            page=args.page,
            size=args.size,
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HeroSMS API CLI with explicit spend/state-change confirmation",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HEROSMS_BASE_URL", DEFAULT_LEGACY_BASE_URL),
        help="SMS-Activate compatible endpoint",
    )
    parser.add_argument(
        "--rest-base-url",
        default=os.environ.get("HEROSMS_REST_BASE_URL", DEFAULT_REST_BASE_URL),
        help="HeroSMS REST API v1 base URL",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    groups = parser.add_subparsers(dest="group", required=True)

    config = groups.add_parser("config", help="Manage local API-key configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path").set_defaults(handler=command_config_path)
    config_commands.add_parser("show").set_defaults(handler=command_config_show)
    config_set = config_commands.add_parser("set")
    config_set.add_argument(
        "--stdin",
        action="store_true",
        help="Read one API-key line from stdin instead of prompting",
    )
    config_set.set_defaults(handler=command_config_set)
    config_clear = config_commands.add_parser("clear")
    config_clear.add_argument("--yes", action="store_true")
    config_clear.set_defaults(handler=command_config_clear)

    groups.add_parser("health", help="Validate credentials by reading balance").set_defaults(
        handler=command_health
    )

    account = groups.add_parser("account")
    account_commands = account.add_subparsers(dest="account_command", required=True)
    account_commands.add_parser("balance").set_defaults(handler=command_balance)

    catalog = groups.add_parser("catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_commands.add_parser("countries").set_defaults(handler=command_countries)

    services = catalog_commands.add_parser("services")
    services.add_argument("--country", type=int)
    services.add_argument("--lang")
    services.set_defaults(handler=command_services)

    operators = catalog_commands.add_parser("operators")
    operators.add_argument("--country", type=int)
    operators.set_defaults(handler=command_operators)

    prices = catalog_commands.add_parser("prices")
    prices.add_argument("--service")
    prices.add_argument("--country", type=int)
    prices.set_defaults(handler=command_prices)

    top = catalog_commands.add_parser("top-countries")
    top.add_argument("--service", required=True)
    top.add_argument("--free-price", action="store_true")
    top.add_argument("--rank", action="store_true")
    top.set_defaults(handler=command_top_countries)

    offers = catalog_commands.add_parser("offers")
    offers.add_argument("--services", help="Comma-separated service codes")
    offers.add_argument("--countries", help="Comma-separated numeric country IDs")
    offers.set_defaults(handler=command_offers)

    activation = groups.add_parser("activation")
    activation_commands = activation.add_subparsers(
        dest="activation_command",
        required=True,
    )

    buy = activation_commands.add_parser("buy")
    buy.add_argument("--service", required=True)
    buy.add_argument("--country", required=True, type=int)
    buy.add_argument("--operator")
    buy.add_argument("--max-price", required=True, type=float)
    buy.add_argument("--fixed-price", action="store_true")
    buy.add_argument("--phone-exception")
    buy.add_argument("--ref")
    buy.add_argument("--v1", action="store_true", help="Use getNumber instead of getNumberV2")
    buy.add_argument("--yes", action="store_true")
    buy.set_defaults(handler=command_buy)

    status_parser = activation_commands.add_parser("status")
    status_parser.add_argument("--id", required=True)
    status_parser.add_argument("--v2", action="store_true")
    status_parser.set_defaults(handler=command_status)

    poll = activation_commands.add_parser("poll")
    poll.add_argument("--id", required=True)
    poll.add_argument("--poll-timeout", type=float, default=120.0)
    poll.add_argument("--interval", type=float, default=DEFAULT_POLL_INTERVAL)
    poll.set_defaults(handler=command_poll)

    for operation in MUTATING_STATUS_CODES:
        status_change = activation_commands.add_parser(operation)
        status_change.add_argument("--id", required=True)
        status_change.add_argument("--yes", action="store_true")
        status_change.set_defaults(handler=command_set_status)

    active = activation_commands.add_parser("active")
    active.add_argument("--start", type=int, default=0)
    active.add_argument("--limit", type=int, default=100)
    active.set_defaults(handler=command_active)

    history = activation_commands.add_parser("history")
    history.add_argument("--start")
    history.add_argument("--end")
    history.add_argument("--offset", type=int, default=0)
    history.add_argument("--size", type=int, default=100)
    history.set_defaults(handler=command_history)

    sms = activation_commands.add_parser("sms")
    sms.add_argument("--id", required=True)
    sms.add_argument("--page", type=int)
    sms.add_argument("--size", type=int)
    sms.set_defaults(handler=command_sms)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except HeroSmsError as exc:
        _emit(exc.as_payload(), pretty=args.pretty, stream=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        error = HeroSmsError("INTERRUPTED", "Operation interrupted")
        _emit(error.as_payload(), pretty=args.pretty, stream=sys.stderr)
        return 130
    _emit(payload, pretty=args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
