#!/usr/bin/env python3
"""快代理 API 提取器 — 多产品提取 + 诊断 + 可选验证。

支持产品: dps(私密代理) / kps(独享代理) / tps(隧道代理) / ops(开放代理)

用法:
    # 先诊断账号状态 (推荐第一步)
    python kuaidaili_extract.py --diagnose

    # 提取私密代理
    python kuaidaili_extract.py --product dps --count 3 --check

    # 提取隧道代理
    python kuaidaili_extract.py --product tps --count 1

    # 提取开放代理 (无需签名)
    python kuaidaili_extract.py --product ops --count 5

凭证方式 (优先级: 命令行 > .env > 环境变量):
    $env:KDL_SECRET_ID = "xxx"
    $env:KDL_SECRET_KEY = "yyy"
    python kuaidaili_extract.py --product dps --count 3 --check
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# 产品 → (SDK方法名, 显示名, 描述)
PRODUCT_MAP = {
    "dps":  ("get_dps",  "私密代理", "独享IP, 需手动提取, HTTP/HTTPS/SOCKS5"),
    "kps":  ("get_kps",  "独享代理", "独占端口, 长期持有, HTTP/HTTPS"),
    "tps":  ("get_tps",  "隧道代理", "自动轮换, 固定隧道地址, HTTP/HTTPS"),
    "ops":  ("get_proxy","开放代理", "共享IP池, 低成本, HTTP/HTTPS"),
}


def _load_env_file(path: str):
    """加载 .env 文件。"""
    if load_dotenv:
        load_dotenv(path)
    else:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")


def _get_client(secret_id: str, secret_key: str):
    """获取 kdl Client 实例。"""
    try:
        import kdl
    except ImportError:
        print("ERR  需要安装快代理 SDK: pip install kdl", file=sys.stderr)
        sys.exit(1)
    return kdl.Client(kdl.Auth(secret_id, secret_key))


def diagnose(secret_id: str, secret_key: str) -> dict:
    """诊断账号状态：哪些产品可用、余额、白名单。"""
    import kdl
    client = _get_client(secret_id, secret_key)
    report = {
        "secret_id": secret_id[:8] + "***",
        "diagnosed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "balance": None,
        "ip_whitelist": None,
        "products": {},
        "recommendation": "",
    }

    # 1. 账户余额
    try:
        report["balance"] = client.get_account_balance()
        print(f"   账户余额: {report['balance']}", file=sys.stderr)
    except Exception as e:
        print(f"  WARN: 账户余额查询失败: {e}", file=sys.stderr)
        report["balance"] = f"查询失败: {e}"

    # 2. IP 白名单
    try:
        report["ip_whitelist"] = client.get_ip_whitelist()
        print(f"   IP白名单: {report['ip_whitelist']}", file=sys.stderr)
    except Exception as e:
        report["ip_whitelist"] = f"查询失败(可能需要订单): {e}"

    # 3. 各产品探测
    print("\n   产品可用性探测:", file=sys.stderr)
    for code, (method, name, desc) in PRODUCT_MAP.items():
        try:
            fn = getattr(client, method)
            if code == "ops":
                from kdl.utils import OpsOrderLevel
                fn(num=1, order_level=OpsOrderLevel.NORMAL, format="json", sign_type="token")
            else:
                fn(num=1, format="json", sign_type="token")
            report["products"][code] = {"name": name, "desc": desc, "status": "PASS 可用"}
            print(f"    PASS {name} ({code}): 可用 — {desc}", file=sys.stderr)
        except Exception as e:
            msg = str(e)
            # 解析错误码，给出明确提示
            if "-5" in msg and "余额充值" in msg:
                hint = "余额充值账号需先购买代理套餐 → https://www.kuaidaili.com/uc/overview/"
                report["products"][code] = {"name": name, "desc": desc, "status": "ERR  余额充值订单不支持此产品", "hint": hint}
                print(f"    ERR  {name} ({code}): 余额充值订单不支持 — 需购买套餐", file=sys.stderr)
            elif "-123" in msg:
                hint = "此密钥无权访问该产品API，可能需要购买对应套餐"
                report["products"][code] = {"name": name, "desc": desc, "status": "ERR  secret type error (无权限)", "hint": hint}
                print(f"    ERR  {name} ({code}): 无权限 — 可能需要购买套餐", file=sys.stderr)
            elif "余额" in msg:
                report["products"][code] = {"name": name, "desc": desc, "status": f"ERR  {msg}", "hint": "检查账户余额是否充足"}
                print(f"    ERR  {name} ({code}): {msg}", file=sys.stderr)
            else:
                report["products"][code] = {"name": name, "desc": desc, "status": f"ERR  {msg}"}
                print(f"    ERR  {name} ({code}): {msg}", file=sys.stderr)

    # 4. 推荐
    available = [k for k, v in report["products"].items() if v["status"].startswith("PASS")]
    if available:
        report["recommendation"] = f"可用产品: {', '.join(available)}。运行 --product <产品> --count N 提取"
    else:
        report["recommendation"] = "无可用产品。请确认已购买代理套餐: https://www.kuaidaili.com/uc/overview/"
    print(f"\n   {report['recommendation']}", file=sys.stderr)
    return report


def extract(secret_id: str, secret_key: str, product: str, count: int = 1,
            sign_type: str = "token", fmt: str = "json",
            pt: int = 1, area: str = "", **kwargs) -> list[str]:
    """提取代理 IP 列表。"""
    client = _get_client(secret_id, secret_key)
    method, name, _ = PRODUCT_MAP[product]

    params = {"num": count, "format": fmt, "sign_type": sign_type}
    if product != "tps":  # 隧道代理不支持 pt 参数
        params["pt"] = pt
    if area:
        params["area"] = area
    params.update(kwargs)

    fn = getattr(client, method)
    if product == "ops":
        import kdl.utils
        params.setdefault("order_level", kdl.utils.OpsOrderLevel.NORMAL)

    try:
        result = fn(**params)
        return result if isinstance(result, list) else [result]
    except Exception as e:
        print(f"ERR  {name}提取失败: {e}", file=sys.stderr)
        return []


def get_auth_info(secret_id: str, secret_key: str) -> dict:
    """获取代理鉴权信息（用户名/密码）。"""
    try:
        client = _get_client(secret_id, secret_key)
        return client.get_proxy_authorization(plain_text=1)
    except Exception as e:
        return {"error": str(e)}


def build_proxy_url(ip_port: str, username: str = "", password: str = "") -> str:
    """将 IP:PORT + 账密拼接为标准代理 URL。"""
    if username and password:
        return f"http://{username}:{password}@{ip_port}"
    return f"http://{ip_port}"


def check_proxies(proxy_urls: list[str], timeout: int = 10) -> list[dict]:
    """验证代理列表（调用 proxy_check.py 的 check_proxy）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from proxy_check import check_proxy
    return [check_proxy(url, timeout=timeout) for url in proxy_urls]


def main():
    parser = argparse.ArgumentParser(description="快代理 API 提取器")
    parser.add_argument("--secret-id", help="快代理 Secret ID (或设 KDL_SECRET_ID 环境变量)")
    parser.add_argument("--secret-key", help="快代理 Secret Key (或设 KDL_SECRET_KEY 环境变量)")
    parser.add_argument("--env", help=".env 文件路径 (从文件读取凭证)")
    parser.add_argument("--diagnose", action="store_true", help="诊断账号状态: 余额、可用产品、白名单")
    parser.add_argument("--product", default="dps", choices=list(PRODUCT_MAP.keys()),
                        help=f"产品类型: {', '.join(f'{k}({v[1]})' for k,v in PRODUCT_MAP.items())} (默认 dps)")
    parser.add_argument("--count", type=int, default=1, help="提取数量 (默认 1)")
    parser.add_argument("--pt", type=int, default=1, help="协议: 1=HTTP 2=HTTPS 3=SOCKS5 (默认 1, 隧道代理忽略此参数)")
    parser.add_argument("--area", default="", help="地区筛选, 如'北京,上海'")
    parser.add_argument("--sign-type", default="token", choices=["token", "hmacsha1"])
    parser.add_argument("--check", action="store_true", help="提取后验证代理可用性")
    parser.add_argument("--with-auth", action="store_true", help="同时获取鉴权信息(用户名密码)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--timeout", type=int, default=10, help="验证超时秒数")

    args = parser.parse_args()

    # 加载凭证
    if args.env:
        _load_env_file(args.env)

    secret_id = args.secret_id or os.environ.get("KDL_SECRET_ID", "")
    secret_key = args.secret_key or os.environ.get("KDL_SECRET_KEY", "")

    if not secret_id or not secret_key:
        print("ERR  需要提供凭证。方式:", file=sys.stderr)
        print("  1. 命令行: --secret-id xxx --secret-key yyy", file=sys.stderr)
        print("  2. 环境变量: KDL_SECRET_ID + KDL_SECRET_KEY", file=sys.stderr)
        print("  3. .env 文件: --env path/to/.env", file=sys.stderr)
        sys.exit(1)

    # 诊断模式
    if args.diagnose:
        print(" 快代理账号诊断", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        result = diagnose(secret_id, secret_key)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\nTIP: 确认产品可用后，运行:", file=sys.stderr)
        print("   python kuaidaili_extract.py --product <产品> --count N --check", file=sys.stderr)
        # 如果全部不可用，exit 1
        available = [k for k, v in result["products"].items() if v["status"].startswith("PASS")]
        sys.exit(0 if available else 1)

    # 提取代理
    name = PRODUCT_MAP[args.product][1]
    if not args.json:
        print(f" 正在提取 {name} x{args.count}...", file=sys.stderr)

    proxy_list = extract(
        secret_id, secret_key,
        product=args.product,
        count=args.count,
        sign_type=args.sign_type,
        fmt="json",
        pt=args.pt,
        area=args.area,
    )

    if not proxy_list:
        print(f"ERR  未提取到{name}", file=sys.stderr)
        print(f"TIP: 建议先运行 --diagnose 诊断账号状态", file=sys.stderr)
        sys.exit(1)

    # 获取鉴权信息
    auth_info = {}
    if args.with_auth:
        auth_info = get_auth_info(secret_id, secret_key)

    # 拼接代理 URL
    username = auth_info.get("username", "")
    password = auth_info.get("password", "")
    if "error" in auth_info:
        print(f"WARN: 获取鉴权信息失败: {auth_info['error']}", file=sys.stderr)
        print("  代理可能使用白名单认证，直接 ip:port 连接", file=sys.stderr)
    proxy_urls = [build_proxy_url(ip, username, password) for ip in proxy_list]

    # 验证
    validation = []
    if args.check:
        if not args.json:
            print(f" 验证 {len(proxy_urls)} 个代理...", file=sys.stderr)
        validation = check_proxies(proxy_urls, args.timeout)
        for v in validation:
            status = "PASS" if v["ok"] else "ERR "
            print(f"  {status} {v['proxy']} → {v.get('exit_ip', 'N/A')} ({v.get('latency_ms', '?')}ms)", file=sys.stderr)

    # 输出
    output = {
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "product": args.product,
        "product_name": name,
        "count": len(proxy_list),
        "proxies": proxy_list,
        "proxy_urls": proxy_urls,
    }
    if auth_info and "error" not in auth_info:
        output["auth"] = {"username": username, "password": password}
    if validation:
        output["validation"] = {
            "total": len(validation),
            "ok": len([v for v in validation if v["ok"]]),
            "results": validation,
        }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\nPASS 提取到 {len(proxy_list)} 个{name}:", file=sys.stderr)
        for url in proxy_urls:
            print(f"  {url}", file=sys.stderr)
        print(file=sys.stderr)


if __name__ == "__main__":
    main()
