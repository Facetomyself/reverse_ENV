#!/usr/bin/env python3
r"""Cliproxy HTTP 代理测试工具 — 验证连接、Sticky/Rotating 模式、地区出口。

用法:
    D:\reverse_ENV\.venv\Scripts\python.exe cliproxy_test.py --full
    D:\reverse_ENV\.venv\Scripts\python.exe cliproxy_test.py --region US --state California --sticky 30
"""

import argparse
import ipaddress
import json
import os
import re
import sys
import time
import urllib.parse

CLIPROXY_HOST = "us.cliproxy.io"
CLIPROXY_PORT = 3010
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 30
PYTHON_EXE = r"D:\reverse_ENV\.venv\Scripts\python.exe"
SID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_env_file(path: str) -> None:
    """加载 .env 文件。"""
    if load_dotenv:
        load_dotenv(path, encoding="utf-8-sig")
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip().lstrip("\ufeff")] = val.strip().strip('"').strip("'")


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"WARN: {name} 不是整数，使用默认端口 {default}", file=sys.stderr)
        return default


def _mask_host(host: str) -> str:
    if not host:
        return host
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        parts = host.split(".")
        if len(parts) >= 3:
            return ".".join([parts[0], "***", parts[-1]])
        return "***"
    if ip.version == 4:
        octets = host.split(".")
        return ".".join(octets[:2] + ["*", "*"])
    exploded = ip.exploded.split(":")
    return ":".join(exploded[:2] + ["****"] * 6)


def redact_proxy_url(proxy_url: str) -> str:
    parsed = urllib.parse.urlparse(proxy_url)
    if not parsed.scheme or not parsed.netloc:
        return re.sub(r"://([^:@/\s]+):([^@/\s]+)@", r"://***:***@", proxy_url)

    host = _mask_host(parsed.hostname or "")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    auth = "***:***@" if parsed.username or parsed.password else ""
    return urllib.parse.urlunparse((parsed.scheme, f"{auth}{host}{port}", "", "", "", ""))


def _redact_text(text: str, proxy_url: str = "") -> str:
    if proxy_url:
        text = text.replace(proxy_url, redact_proxy_url(proxy_url))
    return re.sub(r"://([^:@/\s]+):([^@/\s]+)@", r"://***:***@", text)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _extract_exit_ip(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    candidates = []
    for key in ("origin", "ip", "query", "remote_addr"):
        value = payload.get(key)
        if isinstance(value, str):
            candidates.extend(part.strip() for part in value.split(","))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return None


def result_for_output(result: dict, show_secret: bool = False) -> dict:
    output = dict(result)
    proxy_url = str(output.get("proxy_url") or "")
    if output.get("error"):
        output["error"] = _redact_text(str(output["error"]), proxy_url)
    if proxy_url and not show_secret:
        output["proxy_url"] = redact_proxy_url(proxy_url)
    return output


def build_account(user: str, region: str = "US", state: str = "",
                  sticky_min: int = 0, sid: str = "") -> str:
    """拼接 Cliproxy 用户名参数。

    Rotating: myuser-region-US-st-California
    Sticky:   myuser-region-US-st-Texas-sid-sess1-t-30
    """
    parts = [user, f"region-{region}"]
    if state:
        parts.append(f"st-{state}")
    if sticky_min > 0:
        if not sid:
            sid = f"test{int(time.time())}"
        if not SID_PATTERN.fullmatch(sid):
            raise ValueError(
                "Cliproxy SID 只允许 ASCII 字母、数字、下划线；"
                "禁止 '-'，否则用户名分段可能截断 SID 并造成会话碰撞"
            )
        parts.append(f"sid-{sid}")
        parts.append(f"t-{sticky_min}")
    return "-".join(parts)


def build_proxy_url(account: str, password: str, host: str, port: int) -> str:
    """拼接代理 URL，用户名/密码必须 URL encode。"""
    username = urllib.parse.quote(account, safe="")
    secret = urllib.parse.quote(password, safe="")
    return f"http://{username}:{secret}@{host}:{port}"


def test_proxy(account: str, password: str, host: str = CLIPROXY_HOST,
               port: int = CLIPROXY_PORT, target: str = TEST_URL,
               timeout: int = TIMEOUT) -> dict:
    """通过 HTTP 代理请求目标 URL，返回结果。"""
    proxy_url = build_proxy_url(account, password, host, port)
    proxies = {"http": proxy_url, "https": proxy_url}

    result = {
        "proxy_url": proxy_url,
        "ok": False,
        "latency_ms": None,
        "exit_ip": None,
        "error": None,
    }

    try:
        import requests
    except ImportError:
        result["error"] = f"需要 requests: {PYTHON_EXE} -m pip install requests"
        return result

    try:
        start = time.perf_counter()
        resp = requests.get(target, proxies=proxies, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000
        result["latency_ms"] = round(elapsed, 1)
        result["status_code"] = resp.status_code
        if not 200 <= resp.status_code < 300:
            result["error"] = f"HTTP 状态码异常: {resp.status_code}"
            return result
        try:
            payload = resp.json()
        except ValueError as e:
            result["error"] = f"响应不是可解析 JSON: {e}"
            return result
        exit_ip = _extract_exit_ip(payload)
        if not exit_ip:
            result["error"] = "响应 JSON 中没有可信公网出口 IP"
            return result
        result["exit_ip"] = exit_ip
        result["ok"] = True
    except Exception as e:
        result["error"] = _redact_text(f"{type(e).__name__}: {e}", proxy_url)

    return result


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env", help=".env 文件路径 (从文件读取凭证和 CLIPROXY_HOST/PORT)")
    pre_args, _ = pre_parser.parse_known_args()
    if pre_args.env:
        _load_env_file(pre_args.env)

    env_host = os.environ.get("CLIPROXY_HOST", CLIPROXY_HOST)
    env_port = _env_int("CLIPROXY_PORT", CLIPROXY_PORT)

    parser = argparse.ArgumentParser(description="Cliproxy HTTP 代理测试工具")
    parser.add_argument("--env", default=pre_args.env, help=".env 文件路径 (从文件读取凭证和 CLIPROXY_HOST/PORT)")
    parser.add_argument("--user", help="Cliproxy 用户名 (或设 CLIPROXY_USER 环境变量)")
    parser.add_argument("--pass", dest="password", help="Cliproxy 密码 (或设 CLIPROXY_PASS 环境变量)")
    parser.add_argument("--host", default=env_host, help=f"HTTP 代理主机 (默认 {env_host})")
    parser.add_argument("--port", type=int, default=env_port, help=f"HTTP 代理端口 (默认 {env_port})")
    parser.add_argument("--region", default="US", help="国家代码 (默认 US)")
    parser.add_argument("--state", default="", help="州/省, 如 California")
    parser.add_argument("--sticky", type=int, default=0, help="Sticky 分钟数 (0=Rotating)")
    parser.add_argument(
        "--sid", default="",
        help="自定义 Session ID，仅限 ASCII 字母/数字/下划线，禁止连字符 (默认自动生成)",
    )
    parser.add_argument("--full", action="store_true", help="完整测试: Rotating + Sticky 对比")
    parser.add_argument("--target", default=TEST_URL, help=f"测试目标 URL (默认 {TEST_URL})")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"超时秒数 (默认 {TIMEOUT})")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--show-secret", action="store_true", help="输出完整代理 URL、用户名和密码")
    parser.add_argument("--print-raw", action="store_true", help="等同 --show-secret，用于明文输出")
    args = parser.parse_args()
    show_secret = args.show_secret or args.print_raw

    user = args.user or os.environ.get("CLIPROXY_USER", "")
    password = args.password or os.environ.get("CLIPROXY_PASS", "")

    if not user or not password:
        print("ERR  需要提供凭证。方式:", file=sys.stderr)
        print("  1. 命令行: --user xxx --pass yyy", file=sys.stderr)
        print("  2. 环境变量: CLIPROXY_USER + CLIPROXY_PASS", file=sys.stderr)
        sys.exit(1)

    if args.sid and not SID_PATTERN.fullmatch(args.sid):
        parser.error("--sid 仅允许 ASCII 字母、数字、下划线；禁止使用 '-'")

    # 单次测试
    if not args.full:
        account = build_account(user, args.region, args.state, args.sticky, args.sid)
        mode = f"Sticky {args.sticky}min" if args.sticky else "Rotating"
        display_account = account if show_secret else f"{_mask_secret(user)}-region-{args.region}"
        print(f"[{mode}] {display_account}", file=sys.stderr)
        result = test_proxy(account, password, args.host, args.port, args.target, args.timeout)
        output = result_for_output(result, show_secret)
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            if output["ok"]:
                print(f"  PASS 出口 IP: {output['exit_ip']} 延迟: {output['latency_ms']}ms")
            else:
                print(f"  ERR  {output['error']}")
        sys.exit(0 if result["ok"] else 1)

    # 完整测试: Rotating 3次 + Sticky 3次
    print("=" * 60)
    print("Cliproxy 完整测试 (HTTP 代理)")
    print(f"  主机: {args.host}:{args.port}  用户: {user if show_secret else _mask_secret(user)}")
    print(f"  地区: {args.region}" + (f"  州: {args.state}" if args.state else ""))
    print("=" * 60)

    # Test 1: Rotating (3 requests)
    print("\n[Test 1] Rotating IP -- 预期每次不同:")
    rot_account = build_account(user, args.region, args.state)
    rot_ips = []
    for i in range(3):
        print(f"  Request {i+1}...", end=" ", flush=True, file=sys.stderr)
        r = test_proxy(rot_account, password, args.host, args.port, args.target, args.timeout)
        if r["ok"]:
            rot_ips.append(r["exit_ip"])
            print(f"PASS {r['exit_ip']} ({r['latency_ms']}ms)")
        else:
            print(f"ERR  {r['error']}")

    unique_rot = len(set(rot_ips))
    rot_status = "PASS" if unique_rot >= 2 else "可能服务端缓存了"
    print(f"  Result: {unique_rot}/3 unique IPs ({rot_status})")

    # Test 2: Sticky (3 requests)
    sticky_min = args.sticky if args.sticky else 15
    print(f"\n[Test 2] Sticky IP {sticky_min}min -- 预期 3 次相同:")
    sticky_account = build_account(user, args.region, args.state, sticky_min, args.sid)
    sticky_ips = []
    for i in range(3):
        print(f"  Request {i+1}...", end=" ", flush=True, file=sys.stderr)
        r = test_proxy(sticky_account, password, args.host, args.port, args.target, args.timeout)
        if r["ok"]:
            sticky_ips.append(r["exit_ip"])
            print(f"PASS {r['exit_ip']} ({r['latency_ms']}ms)")
        else:
            print(f"ERR  {r['error']}")

    unique_sticky = len(set(sticky_ips))
    if unique_sticky == 1:
        sticky_status = "PASS"
    elif unique_sticky > 1:
        sticky_status = "IP变了, 检查 sid"
    else:
        sticky_status = "全部失败"
    print(f"  Result: {unique_sticky}/3 unique IPs ({sticky_status})")

    # Summary
    all_ok = len(rot_ips) == 3 and len(sticky_ips) == 3
    print(f"\n[Summary] {'ALL PASS' if all_ok else 'SOME FAILED'}")
    print(f"  Rotating: {rot_ips}")
    print(f"  Sticky:   {sticky_ips}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
