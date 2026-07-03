#!/usr/bin/env python3
"""代理快速验证工具 — 支持 HTTP/HTTPS/SOCKS5，单代理验证或批量检测。

用法:
    python proxy_check.py --proxy "http://user:pass@1.2.3.4:5678"
    python proxy_check.py --proxy "socks5://user:pass@us.cliproxy.io:1080"
    python proxy_check.py --proxy "http://1.2.3.4:5678" --target "https://api.example.com"
    python proxy_check.py --file proxies.txt --check

输出: JSON，包含可用性、延迟、出口 IP、匿名级别。
"""

import argparse
import json
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

DEFAULT_TARGET = "https://httpbin.org/ip"
TIMEOUT = 15


def check_proxy(proxy_url: str, target: str = DEFAULT_TARGET, timeout: int = TIMEOUT) -> dict:
    """验证单个代理，返回结构化结果。"""
    result = {
        "proxy": proxy_url,
        "ok": False,
        "latency_ms": None,
        "exit_ip": None,
        "error": None,
    }

    # 解析代理类型
    parsed = urllib.parse.urlparse(proxy_url)
    scheme = parsed.scheme  # http / https / socks5 / socks5h

    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        # 按代理类型选择库
        if scheme in ("socks5", "socks5h"):
            try:
                import socks  # noqa: F401
            except ImportError:
                result["error"] = "需要 PySocks: pip install 'requests[socks]'"
                return result

        import requests

        start = time.perf_counter()
        resp = requests.get(target, proxies=proxies, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000

        result["ok"] = True
        result["latency_ms"] = round(elapsed, 1)
        result["exit_ip"] = resp.json().get("origin", "unknown")
        result["status_code"] = resp.status_code

    except requests.exceptions.ProxyError as e:
        result["error"] = f"代理连接失败: {e}"
    except requests.exceptions.ConnectTimeout:
        result["error"] = f"连接超时 ({timeout}s)"
    except requests.exceptions.ReadTimeout:
        result["error"] = f"读取超时 ({timeout}s)"
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL 错误: {e}"
    except Exception as e:
        result["error"] = f"未知错误: {type(e).__name__}: {e}"

    return result


def check_file(filepath: str, target: str = DEFAULT_TARGET, workers: int = 5) -> list[dict]:
    """从文件读取代理列表，并发验证。"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_proxy, line, target): line for line in lines}
        for future in as_completed(futures):
            results.append(future.result())

    return results


def main():
    parser = argparse.ArgumentParser(description="代理快速验证工具")
    parser.add_argument("--proxy", help="单个代理 URL")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="测试目标 URL")
    parser.add_argument("--file", help="代理列表文件 (每行一个)")
    parser.add_argument("--workers", type=int, default=5, help="并发验证数 (默认 5)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"超时秒数 (默认 {TIMEOUT})")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.proxy:
        result = check_proxy(args.proxy, args.target, args.timeout)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_single(result)
        sys.exit(0 if result["ok"] else 1)

    if args.file:
        results = check_file(args.file, args.target, args.workers)
        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        if args.json:
            print(json.dumps({"total": len(results), "ok": len(ok), "fail": len(fail), "results": results}, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"总计: {len(results)} | 可用: {len(ok)} | 不可用: {len(fail)}")
            print(f"{'='*60}")
            for r in ok:
                print(f"  PASS {r['proxy']} → {r['exit_ip']} ({r['latency_ms']}ms)")
            for r in fail:
                print(f"  ERR  {r['proxy']} → {r['error']}")
            print()
        sys.exit(0 if fail == [] else 1)

    parser.print_help()
    sys.exit(1)


def _print_single(result: dict):
    """友好的单结果输出。"""
    print()
    if result["ok"]:
        print(f"  PASS 代理可用")
        print(f"  出口 IP : {result['exit_ip']}")
        print(f"  延迟    : {result['latency_ms']} ms")
    else:
        print(f"  ERR  代理不可用")
        print(f"  错误: {result['error']}")
    print()


if __name__ == "__main__":
    main()
