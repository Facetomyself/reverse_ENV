#!/bin/bash
# xiaojianbang-syscall-filter KPM 加载/控制脚本（在 PC 上通过 adb 操作设备）
#
# 作者：小肩膀   微信：xiaojianbang8888
#
# 用法:
#   ./load.sh load            加载模块
#   ./load.sh unload          卸载模块
#   ./load.sh status          查看运行状态
#   ./load.sh list            列出已加载模块
#   ./load.sh ctl 'AOSP=off'  运行时控制（参数必须无空格）
#   ./load.sh reload          重新推送并加载（改完代码后用）
#
# 控制命令(单 token，无空格):
#   trace=on|off  fake=on|off  dump=on|off  exitmon=on|off
#   memmon=on|off  memdump=on|off  resolve=on|off
#   ROOT=on|off  FRIDA=on|off  XPOSED=on|off  AOSP=on|off
#   uidadd=10299  uiddel=10299  uidclear  status
#
# 环境变量:
#   XJB_ADB=/path/to/adb             覆盖 adb；未设置时用 ADB，再回退 PATH 中的 adb
#   XJB_KP_SUPERKEY=your_superkey    覆盖 KernelPatch/APatch superkey

set -e
ADB="${XJB_ADB:-${ADB:-adb}}"
KP="/data/local/tmp/kpatch"
SK="${XJB_KP_SUPERKEY:-xiaojianbang8888}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
KPM_LOCAL="$SCRIPT_DIR/syscallhook.kpm"
KPM_DEV=/data/local/tmp/scfilter.kpm
NAME=xiaojianbang-syscall-filter

adb_cmd() { "$ADB" "$@"; }
dev() { adb_cmd shell su -c "$*"; }

case "$1" in
  load)
    dev "$KP $SK kpm load $KPM_DEV"
    ;;
  unload)
    dev "$KP $SK kpm unload $NAME"
    ;;
  status)
    dev "$KP $SK kpm ctl0 $NAME status >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
    echo
    ;;
  list)
    dev "$KP $SK kpm list"
    echo
    ;;
  info)
    dev "$KP $SK kpm info $NAME"
    ;;
  ctl)
    if [ -z "${2:-}" ]; then
      echo "ctl 需要一个无空格控制命令，例如: $0 ctl 'resolve=on'" >&2
      exit 1
    fi
    dev "$KP $SK kpm ctl0 $NAME '$2' >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
    echo
    ;;
  push)
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    echo "pushed"
    ;;
  reload)
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    dev "$KP $SK kpm unload $NAME 2>/dev/null; $KP $SK kpm load $KPM_DEV"
    ;;
  *)
    echo "用法: $0 {load|unload|status|list|info|push|reload|ctl '<cmd>'}"
    exit 1
    ;;
esac
