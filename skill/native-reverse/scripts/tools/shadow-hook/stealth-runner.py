#!/usr/bin/env python3
"""Shadow Hook 隐身编排器 — 统一加载 Frida JS 隐身 agent。

用法:
  # 完整隐身（信号链 + soinfo 隐藏 + VMA 重命名）
  python stealth-runner.py --package com.target.app --mode all

  # 仅信号链（最轻量，不影响稳定性）
  python stealth-runner.py --package com.target.app --mode signal

  # 仅 soinfo 隐藏（过滤 dl_iterate_phdr + /proc/maps）
  python stealth-runner.py --pid 12345 --mode stealth

  # Gadget 模式（push gadget + config 后自动加载）
  python stealth-runner.py --gadget --mode all

  # 列出可用模式
  python stealth-runner.py --list-modes

依赖: Python frida 模块 (pip install frida-tools)
参考: rust-frida-shadow-hook / agent/src/lib.rs (process_cmd 路由)
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Optional

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]  # skill/native-reverse/scripts/tools/ → 项目根

# Agent 脚本路径
AGENTS = {
    "signal": SCRIPT_DIR / "signal-chain-agent.js",
    "stealth": SCRIPT_DIR / "hide-soinfo-agent.js",
    "vma": SCRIPT_DIR / "vma-hide-agent.js",
    "all": SCRIPT_DIR / "shadow-agent-gadget.js",
}

# 查找 frida 可执行文件
def find_frida() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "frida.exe",
        PROJECT_ROOT / ".venv" / "Scripts" / "frida",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # 回退到 PATH
    return "frida"


def find_adb() -> str:
    candidates = [
        PROJECT_ROOT / "tools" / "adb" / "adb.exe",
        PROJECT_ROOT / "tools" / "adb" / "adb",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "adb"


FRIDA = find_frida()
ADB = find_adb()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"[+] {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str) -> subprocess.CompletedProcess:
    return run([ADB, *args])


def list_modes():
    print("可用模式:")
    print("  signal   — 仅信号链处理（ART FaultManager 兼容 + OAT NULL header fix）")
    print("  stealth  — dl_iterate_phdr + /proc/maps 过滤，隐藏 Frida agent SO")
    print("  vma      — prctl PR_SET_VMA 重命名匿名 RWX 映射")
    print("  all      — 完整隐身（上述三项的复合，按 signal→stealth→vma 顺序执行）")
    print()
    print("用法示例:")
    print(f"  python {sys.argv[0]} --package com.example --mode stealth")
    print(f"  python {sys.argv[0]} --pid 12345 --mode all")
    print(f"  python {sys.argv[0]} --package com.example --mode all --extra-patterns 'baidu,tencent'")


def inject_agent(
    package: Optional[str] = None,
    pid: Optional[int] = None,
    gadget: bool = False,
    mode: str = "all",
    extra_patterns: Optional[str] = None,
    spawn: bool = False,
    timeout: int = 10,
    verbose: bool = False,
) -> int:
    """通过 frida CLI 加载隐身 agent 到目标进程。

    Args:
        package: Android 包名
        pid: 目标进程 PID
        gadget: 是否 gadget 模式
        mode: stealth/signal/vma/all
        extra_patterns: 逗号分隔的额外隐藏模式
        spawn: 是否 spawn 注入
        timeout: frida 连接超时
        verbose: 详细输出
    """
    agent_path = AGENTS.get(mode)
    if not agent_path or not agent_path.exists():
        print(f"[-] 未知模式 '{mode}' 或 agent 文件不存在: {agent_path}", file=sys.stderr)
        print(f"    可用模式: {', '.join(AGENTS.keys())}", file=sys.stderr)
        return 1

    # 构建 frida 命令
    cmd = [FRIDA]

    if gadget:
        cmd.extend(["-U", "-n", "Gadget"])
    elif package:
        if spawn:
            cmd.extend(["-U", "-f", package])
        else:
            cmd.extend(["-U", package])
    elif pid:
        cmd.extend(["-U", "-p", str(pid)])
    else:
        print("[-] 必须指定 --package、--pid 或 --gadget", file=sys.stderr)
        return 1

    # 注入前暂停（spawn 模式确保 agent 在进程初始化阶段加载）
    if spawn and package:
        cmd.append("--pause")

    # 加载 agent 脚本
    cmd.extend(["-l", str(agent_path)])

    # 额外参数通过环境变量传递（Frida CLI 无 --args 时兼容方案）
    env = os.environ.copy()
    if extra_patterns:
        env["SHADOW_EXTRA_PATTERNS"] = extra_patterns
    if verbose:
        env["SHADOW_VERBOSE"] = "1"

    print(f"[*] 模式: {mode}")
    print(f"[*] Agent: {agent_path.name}")
    if extra_patterns:
        print(f"[*] 额外隐藏模式: {extra_patterns}")
    print()
    print("┌" + "─" * 48 + "┐")
    print("│  连接 Frida 后，agent 将自动初始化并输出日志   │")
    print("│  按 Ctrl+C 退出                                 │")
    print("└" + "─" * 48 + "┘")
    print()

    try:
        result = run(cmd, env=env)
        return result.returncode
    except KeyboardInterrupt:
        print("\n[*] 用户中断")
        return 0


def gadget_deploy(package: str, mode: str = "all"):
    """将 agent 脚本 + frida-gadget 部署到设备。

    Frida gadget 配置文件格式:
    {
      "interaction": {
        "type": "script",
        "path": "/data/local/tmp/shadow-agent.js",
        "on_change": "reload"
      }
    }

    注意：此功能需要额外步骤将 gadget 注入 APK，不在本脚本范围内。
    此处仅将 agent 脚本 push 到设备供 gadget 使用。
    """
    agent_path = AGENTS.get(mode)
    if not agent_path:
        print(f"[-] 未知模式: {mode}", file=sys.stderr)
        return 1

    remote_path = "/data/local/tmp/shadow-agent.js"

    # Push agent
    pushed = adb("push", str(agent_path), remote_path)
    if pushed.returncode != 0:
        print("[-] adb push 失败", file=sys.stderr)
        return pushed.returncode

    print(f"[+] Agent 已推送到 {remote_path}")

    # 生成 gadget 配置示例
    gadget_config = {
        "interaction": {
            "type": "script",
            "path": remote_path,
            "on_change": "reload",
        }
    }
    config_path = SCRIPT_DIR / "gadget.config.example.json"
    config_path.write_text(json.dumps(gadget_config, indent=2) + "\n", encoding="utf-8")
    print(f"[+] 示例 gadget 配置已保存到: {config_path}")
    print(f"[*] 将上述配置放入 APK 的 lib/<abi>/libgadget.config.so 即可启用")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Shadow Hook 隐身编排器 — 统一加载 Frida JS 隐身 agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --package com.example --mode all
  %(prog)s --package com.example --mode stealth --spawn
  %(prog)s --pid 12345 --mode signal
  %(prog)s --gadget --package com.example --mode all
  %(prog)s --list-modes
""",
    )

    # 模式选择
    parser.add_argument("--list-modes", action="store_true", help="列出可用模式")

    # 目标选择（互斥组）
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--package", help="Android 包名")
    target.add_argument("--pid", type=int, help="目标进程 PID")
    target.add_argument("--gadget", action="store_true", help="Gadget 模式（连接 Gadget 命名管道）")

    # Agent 选择
    parser.add_argument(
        "--mode", choices=list(AGENTS.keys()), default="all",
        help="隐身模式 (default: all)"
    )
    parser.add_argument(
        "--extra-patterns",
        help="额外需要隐藏的 SO 名/路径子串（逗号分隔）",
    )

    # 高级选项
    parser.add_argument("--spawn", action="store_true", help="Spawn 注入（暂停进程，初始化后 resume）")
    parser.add_argument("--timeout", type=int, default=10, help="连接超时秒数 (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--deploy-gadget-config", action="store_true",
                        help="仅生成并推送到设备的 gadget 配置（不注入）")

    args = parser.parse_args(argv)

    # --list-modes
    if args.list_modes:
        list_modes()
        return 0

    # --deploy-gadget-config
    if args.deploy_gadget_config:
        if not args.package:
            print("[-] --deploy-gadget-config 需要 --package", file=sys.stderr)
            return 1
        return gadget_deploy(args.package, args.mode)

    # 需要目标
    if not args.package and not args.pid and not args.gadget:
        print("[-] 必须指定 --package、--pid 或 --gadget", file=sys.stderr)
        print("[*] 使用 --help 查看完整用法", file=sys.stderr)
        return 1

    return inject_agent(
        package=args.package,
        pid=args.pid,
        gadget=args.gadget,
        mode=args.mode,
        extra_patterns=args.extra_patterns,
        spawn=args.spawn,
        timeout=args.timeout,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
