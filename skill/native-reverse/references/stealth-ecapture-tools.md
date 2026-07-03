# stealth-hook 与 eCapture 工具

## 目录

- Stealth Hook
- eCapture Android arm64

## Stealth Hook

用途：

- Android 内核无痕 HWBP hook，用于强反 Frida、强 `.text` 校验或 inline hook 不稳定时的参数/返回值验证。
- 不修改目标进程用户态代码，不注入 so，不创建目标进程可疑映射。
- 支持按 `pid + so + offset` live trace、捕获返回、替换返回值、修改 X0-X7 参数、query 和 unhook。
- 适合验证 patch 候选、fatal 分支返回值、低频检测函数入参和返回状态。

设备要求：

- Android arm64。
- GKI 5.4+ 设备。
- APatch/KernelPatch 和 KPM 加载能力。
- 设备 root/su。

安装推送：

```bash
python3 scripts/stealth_hook_android.py --push-only
```

默认推送结果：

```text
/sdcard/xiaojianbang-stealth-hook.kpm
/data/local/tmp/xjb_stealth_hook/xiaojianbang_hook
/data/local/tmp/xjb_stealth_hook/kpm_loader
/data/local/tmp/xjb_stealth_hook/sh_control
```

KPM 可以通过 APatch App 加载，也可以在设备 KernelPatch supercall/superkey 匹配时尝试用项目自带 `kpm_loader` 加载。wrapper 默认只推送文件；只有显式传入 `--load-kpm` 或 `--reload-kpm` 时才尝试动态加载。

常用命令：

```bash
python3 scripts/stealth_hook_android.py --kpm-hello
python3 scripts/stealth_hook_android.py --kpm-list
python3 scripts/stealth_hook_android.py --load-kpm
python3 scripts/stealth_hook_android.py --sh-status
```

按包名解析 pid 并 live trace：

```bash
python3 scripts/stealth_hook_android.py \
  --package com.example.target \
  --so libtarget.so \
  --offset 0x41ac0,0x41d7c \
  --dump-size 96 \
  --duration 30
```

替换返回值：

```bash
python3 scripts/stealth_hook_android.py \
  --package com.example.target \
  --so libtarget.so \
  --offset 0x4161c \
  --replace-ret 0 \
  --once
```

修改参数：

```bash
python3 scripts/stealth_hook_android.py \
  --pid 12345 \
  --so libtarget.so \
  --offset 0x4161c \
  --modify-arg 0=0x100 \
  --modify-arg 1=0x200 \
  --once
```

注意：

- ARM64 硬件断点槽位有限，项目默认 offset 上限为 6 个；优先 hook 低频、明确的目标函数或基本块入口。
- 不要直接 hook `memcpy`、`malloc` 等高频通用函数，容易造成 hit_count 暴涨和卡顿。
- 使用前记录目标 pid、so、offset、KPM 加载状态、命令和回退方式。
- 使用 `--unhook` 或 Ctrl+C 停止 live trace 后确认已清理断点。
- Windows/Linux/macOS 宿主机都支持；可通过 `ADB=D:\reverse_ENV\tools\adb\adb.exe` 覆盖 adb 路径。
- `STEALTH_HOOK_ROOT=/path/to/xiaojianbang-stealth-hook-main` 可覆盖工具根目录。
- 如果需要重编译 KPM，进入 `third_party/xiaojianbang-stealth-hook-main/kpm` 后显式指定 `KP_DIR=/path/to/KernelPatch-main CLANG=/path/to/clang make`。

## eCapture Android arm64

用途：

- 基于 eBPF/uProbe/TC 抓取 TLS/SSL 明文，无需安装 CA 证书。
- 支持 OpenSSL/BoringSSL、GoTLS、GnuTLS、NSS/NSPR 等模块，具体以 `ecapture -h` 和子命令帮助为准。
- 支持 text、keylog、pcap/pcapng 模式。
- 在 Android native 分析中用于确认 App HTTPS 明文请求、服务端响应、TLS keylog 或 pcapng。

Wrapper text 模式示例：

```bash
python3 scripts/ecapture_android.py \
  --duration 60 \
  --out-dir logs/ecapture_text \
  -- tls -m text
```

pcapng 模式示例：

```bash
python3 scripts/ecapture_android.py \
  --duration 60 \
  --out-dir logs/ecapture_pcap \
  -- tls -m pcap -i wlan0 --pcapfile save_android.pcapng tcp port 443
```

keylog 模式示例：

```bash
python3 scripts/ecapture_android.py \
  --duration 60 \
  --out-dir logs/ecapture_keylog \
  -- tls -m keylog --keylogfile ecapture_masterkey.log
```

指定 Android BoringSSL 路径示例：

```bash
python3 scripts/ecapture_android.py \
  --duration 60 \
  --out-dir logs/ecapture_boringssl \
  -- tls -m pcap -i wlan0 \
  --libssl=/apex/com.android.conscrypt/lib64/libssl.so \
  --ssl_version="boringssl 1.1.1" \
  --pcapfile save_android.pcapng tcp port 443
```

注意：

- 需要 Android arm64、root 权限，且内核通常要求 aarch64 5.5+ 并支持 eBPF/BTF 能力。
- wrapper 会把 `ecapture` push 到 `/data/local/tmp/xjb_ecapture/`，运行到 `--duration` 后中断并 pull 输出目录。
- 默认会清理 `--device-dir` 后再 push；需要保留旧设备文件时用 `--no-clean-device-dir`，需要避免复用目录时用 `--timestamp-device-dir`。
- Windows/Linux/macOS 宿主机都支持；可通过 `ADB=D:\reverse_ENV\tools\adb\adb.exe` 覆盖 adb 路径。
- `ECAPTURE_ROOT=/path/to/ecapture-v2.3.0-android-arm64` 可覆盖 eCapture 根目录。
- 若目标 App 自带证书校验或自定义 TLS 栈，eCapture 负责旁路抓明文；证书 pinning/业务加密仍需结合 Frida 和静态分析定位。
