#!/usr/bin/env python3
r"""代理快速验证工具 — 支持 HTTP/HTTPS/SOCKS5，单代理验证或批量检测。

用法:
    D:\reverse_ENV\.venv\Scripts\python.exe proxy_check.py --proxy "http://user:pass@1.2.3.4:5678"
    D:\reverse_ENV\.venv\Scripts\python.exe proxy_check.py --proxy "socks5://user:pass@us.cliproxy.io:3010"
    D:\reverse_ENV\.venv\Scripts\python.exe proxy_check.py --proxy "http://1.2.3.4:5678" --target "https://api.example.com"
    D:\reverse_ENV\.venv\Scripts\python.exe proxy_check.py --file proxies.txt

输出: JSON，包含可用性、延迟、出口 IP、匿名级别。
"""

import argparse
import ipaddress
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_TARGET = "https://httpbin.org/ip"
TIMEOUT = 15
PYTHON_EXE = r"D:\reverse_ENV\.venv\Scripts\python.exe"

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
    """脱敏代理 URL，默认输出不暴露完整 endpoint、用户名、密码。"""
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
    """生成适合终端/JSON 输出的结果副本。"""
    output = dict(result)
    proxy_url = str(output.get("proxy") or "")
    if output.get("error"):
        output["error"] = _redact_text(str(output["error"]), proxy_url)
    if proxy_url and not show_secret:
        output["proxy"] = redact_proxy_url(proxy_url)
    return output


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

    if scheme not in ("http", "https", "socks5", "socks5h"):
        result["error"] = f"不支持的代理协议: {scheme or '<empty>'}"
        return result
    if not parsed.hostname:
        result["error"] = "代理 URL 缺少主机"
        return result

    proxies = {"http": proxy_url, "https": proxy_url}

    # 按代理类型选择库
    if scheme in ("socks5", "socks5h"):
        try:
            import socks  # noqa: F401
        except ImportError:
            result["error"] = f"需要 PySocks: {PYTHON_EXE} -m pip install \"requests[socks]\""
            return result

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

    except requests.exceptions.ProxyError as e:
        result["error"] = _redact_text(f"代理连接失败: {e}", proxy_url)
    except requests.exceptions.ConnectTimeout:
        result["error"] = f"连接超时 ({timeout}s)"
    except requests.exceptions.ReadTimeout:
        result["error"] = f"读取超时 ({timeout}s)"
    except requests.exceptions.SSLError as e:
        result["error"] = _redact_text(f"SSL 错误: {e}", proxy_url)
    except Exception as e:
        result["error"] = _redact_text(f"未知错误: {type(e).__name__}: {e}", proxy_url)

    return result


def check_file(filepath: str, target: str = DEFAULT_TARGET, timeout: int = TIMEOUT,
               workers: int = 5) -> list[dict]:
    """从文件读取代理列表，并发验证。"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_proxy, line, target, timeout): line for line in lines}
        for future in as_completed(futures):
            results.append(future.result())

    return results


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env", help=".env 文件路径 (从文件读取环境变量)")
    pre_args, _ = pre_parser.parse_known_args()
    if pre_args.env:
        _load_env_file(pre_args.env)

    parser = argparse.ArgumentParser(description="代理快速验证工具")
    parser.add_argument("--env", default=pre_args.env, help=".env 文件路径 (从文件读取环境变量)")
    parser.add_argument("--proxy", help="单个代理 URL")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="测试目标 URL")
    parser.add_argument("--file", help="代理列表文件 (每行一个)")
    parser.add_argument("--workers", type=int, default=5, help="并发验证数 (默认 5)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"超时秒数 (默认 {TIMEOUT})")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--show-secret", action="store_true", help="输出完整代理 URL 和凭证")
    parser.add_argument("--print-raw", action="store_true", help="等同 --show-secret，用于明文输出")
    args = parser.parse_args()
    show_secret = args.show_secret or args.print_raw

    if args.proxy:
        result = check_proxy(args.proxy, args.target, args.timeout)
        output = result_for_output(result, show_secret)
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            _print_single(output)
        sys.exit(0 if result["ok"] else 1)

    if args.file:
        results = check_file(args.file, args.target, args.timeout, args.workers)
        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        output_results = [result_for_output(r, show_secret) for r in results]
        if args.json:
            print(json.dumps({"total": len(results), "ok": len(ok), "fail": len(fail), "results": output_results}, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"总计: {len(results)} | 可用: {len(ok)} | 不可用: {len(fail)}")
            print(f"{'='*60}")
            for r in output_results:
                if not r["ok"]:
                    continue
                print(f"  PASS {r['proxy']} → {r['exit_ip']} ({r['latency_ms']}ms)")
            for r in output_results:
                if r["ok"]:
                    continue
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
