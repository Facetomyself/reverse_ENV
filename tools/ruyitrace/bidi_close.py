#!/usr/bin/env python3
"""Drive and close a Firefox Remote Agent session through WebDriver BiDi.

The timed ruyiTrace wrapper starts Firefox on ``about:blank``, then uses this
helper to navigate after DOMTrace is initialized.  ``browser.close`` lets
parent and content processes flush their DOMTrace shards.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from typing import Any, Sequence

import websocket


def wait_for_port(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=min(0.5, timeout)):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    detail = f": {last_error}" if last_error else ""
    raise TimeoutError(f"Firefox Remote Agent did not open {host}:{port}{detail}")


def receive_response(connection: Any, command_id: int) -> dict[str, Any]:
    while True:
        raw = connection.recv()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("id") == command_id:
            return payload


def send_command(
    connection: Any,
    command_id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    connection.send(
        json.dumps(
            {"id": command_id, "method": method, "params": params or {}},
            separators=(",", ":"),
        )
    )
    response = receive_response(connection, command_id)
    if response.get("type") == "error":
        error = response.get("error", "unknown error")
        message = response.get("message", "")
        raise RuntimeError(f"{method} failed: {error}: {message}")
    if response.get("type") != "success":
        raise RuntimeError(f"{method} returned an unexpected response: {response!r}")
    return response


def top_context_id(tree_result: dict[str, Any]) -> str:
    contexts = tree_result.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise RuntimeError("browsingContext.getTree returned no top-level context")
    context = contexts[0]
    if not isinstance(context, dict) or not isinstance(context.get("context"), str):
        raise RuntimeError("browsingContext.getTree returned an invalid context")
    return context["context"]


def close_browser(
    host: str,
    port: int,
    timeout: float,
    url: str | None = None,
    duration: float = 0,
    reload: bool = False,
) -> dict[str, Any]:
    wait_for_port(host, port, timeout)
    endpoint = f"ws://{host}:{port}/session"
    connection = websocket.create_connection(
        endpoint,
        timeout=timeout,
        suppress_origin=True,
        enable_multithread=False,
    )
    lifecycle_error: Exception | None = None
    closed: dict[str, Any] | None = None
    navigation: dict[str, Any] | None = None
    try:
        session = send_command(
            connection,
            1,
            "session.new",
            {"capabilities": {}},
        )
        command_id = 2
        try:
            if url or reload:
                tree_command_id = command_id
                command_id += 1
                tree = send_command(connection, tree_command_id, "browsingContext.getTree")
                context_id = top_context_id(tree.get("result", {}))
                navigation_command_id = command_id
                command_id += 1
                if reload:
                    navigation = send_command(
                        connection,
                        navigation_command_id,
                        "browsingContext.reload",
                        {"context": context_id, "wait": "complete"},
                    )
                else:
                    navigation = send_command(
                        connection,
                        navigation_command_id,
                        "browsingContext.navigate",
                        {"context": context_id, "url": url, "wait": "complete"},
                    )
            if duration > 0:
                time.sleep(duration)
        except Exception as exc:
            lifecycle_error = exc
        try:
            closed = send_command(connection, command_id, "browser.close")
        except Exception as exc:
            if lifecycle_error is None:
                lifecycle_error = exc
    finally:
        try:
            connection.close()
        except Exception:
            pass
    if lifecycle_error is not None:
        raise lifecycle_error
    assert closed is not None
    return {
        "ok": True,
        "endpoint": endpoint,
        "session_id": session.get("result", {}).get("sessionId"),
        "navigation": navigation.get("result", {}) if navigation else None,
        "close_result": closed.get("result", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--url", help="optional URL to navigate after the session is ready")
    parser.add_argument("--reload", action="store_true", help="reload the initial top-level context")
    parser.add_argument("--duration", type=float, default=0.0, help="seconds to wait before browser.close")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    if args.duration < 0:
        raise SystemExit("--duration must be zero or greater")
    if args.url and args.reload:
        raise SystemExit("--url and --reload are mutually exclusive")
    try:
        report = close_browser(
            args.host,
            args.port,
            args.timeout,
            url=args.url,
            duration=args.duration,
            reload=args.reload,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
