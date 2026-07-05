#!/usr/bin/env python3
"""Cliproxy HTTP 代理测试工具 — 验证连接、Sticky/Rotating 模式、地区出口。

用法:
    python cliproxy_test.py --full
    python cliproxy_test.py --region US --state California --sticky 30
"""

import argparse
import json
import os
import sys
import time

CLIPROXY_HOST = "us.cliproxy.io"
CLIPROXY_PORT = 3010
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 30


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
            sid = f"test-{int(time.time())}"
        parts.append(f"sid-{sid}")
        parts.append(f"t-{sticky_min}")
    return "-".join(parts)


def test_proxy(account: str, password: str, host: str = CLIPROXY_HOST,
               port: int = CLIPROXY_PORT, target: str = TEST_URL,
               timeout: int = TIMEOUT) -> dict:
    """通过 HTTP 代理请求目标 URL，返回结果。"""
    proxy_url = f"http://{account}:{password}@{host}:{port}"
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
        result["error"] = "需要 requests: pip install requests"
        return result

    try:
        start = time.perf_counter()
        resp = requests.get(target, proxies=proxies, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000
        result["ok"] = True
        result["latency_ms"] = round(elapsed, 1)
        result["exit_ip"] = resp.json().get("origin", "unknown")
        result["status_code"] = resp.status_code
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(description="Cliproxy HTTP 代理测试工具")
    parser.add_argument("--user", help="Cliproxy 用户名 (或设 CLIPROXY_USER 环境变量)")
    parser.add_argument("--pass", dest="password", help="Cliproxy 密码 (或设 CLIPROXY_PASS 环境变量)")
    parser.add_argument("--host", default=CLIPROXY_HOST, help=f"HTTP 代理主机 (默认 {CLIPROXY_HOST})")
    parser.add_argument("--port", type=int, default=CLIPROXY_PORT, help=f"HTTP 代理端口 (默认 {CLIPROXY_PORT})")
    parser.add_argument("--region", default="US", help="国家代码 (默认 US)")
    parser.add_argument("--state", default="", help="州/省, 如 California")
    parser.add_argument("--sticky", type=int, default=0, help="Sticky 分钟数 (0=Rotating)")
    parser.add_argument("--sid", default="", help="自定义 Session ID (默认自动生成)")
    parser.add_argument("--full", action="store_true", help="完整测试: Rotating + Sticky 对比")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    user = args.user or os.environ.get("CLIPROXY_USER", "")
    password = args.password or os.environ.get("CLIPROXY_PASS", "")

    if not user or not password:
        print("ERR  需要提供凭证。方式:", file=sys.stderr)
        print("  1. 命令行: --user xxx --pass yyy", file=sys.stderr)
        print("  2. 环境变量: CLIPROXY_USER + CLIPROXY_PASS", file=sys.stderr)
        sys.exit(1)

    # 单次测试
    if not args.full:
        account = build_account(user, args.region, args.state, args.sticky, args.sid)
        mode = f"Sticky {args.sticky}min" if args.sticky else "Rotating"
        print(f"[{mode}] {account[:50]}...", file=sys.stderr)
        result = test_proxy(account, password, args.host, args.port)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["ok"]:
                print(f"  PASS 出口 IP: {result['exit_ip']} 延迟: {result['latency_ms']}ms")
            else:
                print(f"  ERR  {result['error']}")
        sys.exit(0 if result["ok"] else 1)

    # 完整测试: Rotating 3次 + Sticky 3次
    print("=" * 60)
    print("Cliproxy 完整测试 (HTTP 代理)")
    print(f"  主机: {args.host}:{args.port}  用户: {user}")
    print(f"  地区: {args.region}" + (f"  州: {args.state}" if args.state else ""))
    print("=" * 60)

    # Test 1: Rotating (3 requests)
    print("\n[Test 1] Rotating IP -- 预期每次不同:")
    rot_account = build_account(user, args.region, args.state)
    rot_ips = []
    for i in range(3):
        print(f"  Request {i+1}...", end=" ", flush=True, file=sys.stderr)
        r = test_proxy(rot_account, password, args.host, args.port)
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
        r = test_proxy(sticky_account, password, args.host, args.port)
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


if __name__ == "__main__":
    main()
