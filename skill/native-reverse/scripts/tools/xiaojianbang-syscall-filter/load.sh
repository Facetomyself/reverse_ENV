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
#   KP_SUPERKEY=your_superkey        KernelPatch/APatch superkey
#   XJB_KP_SUPERKEY=your_superkey    兼容旧变量，优先级低于 KP_SUPERKEY

set -e
ADB="${XJB_ADB:-${ADB:-adb}}"
KP="/data/local/tmp/kpatch"
SK=""
if [ "${1:-}" = "--superkey" ] || [ "${1:-}" = "-k" ]; then
  if [ -z "${2:-}" ]; then
    echo "--superkey/-k 需要 superkey 参数" >&2
    exit 1
  fi
  SK="$2"
  shift 2
else
  SK="${KP_SUPERKEY:-${XJB_KP_SUPERKEY:-}}"
fi
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
KPM_LOCAL="$SCRIPT_DIR/syscallhook.kpm"
KPM_DEV=/data/local/tmp/scfilter.kpm
NAME=xiaojianbang-syscall-filter

adb_cmd() { "$ADB" "$@"; }
dev() { adb_cmd shell su -c "$*"; }
sq() { printf "'%s'" "$(printf "%s" "$1" | sed "s/'/'\\\\''/g")"; }
need_superkey() {
  if [ -z "$SK" ]; then
    echo "KernelPatch superkey 不能为空；请使用 --superkey <key> 或设置 KP_SUPERKEY / XJB_KP_SUPERKEY" >&2
    exit 1
  fi
}

case "$1" in
  load)
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm load $(sq "$KPM_DEV")"
    ;;
  unload)
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm unload $(sq "$NAME")"
    ;;
  status)
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm ctl0 $(sq "$NAME") status >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
    echo
    ;;
  list)
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm list"
    echo
    ;;
  info)
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm info $(sq "$NAME")"
    ;;
  ctl)
    need_superkey
    if [ -z "${2:-}" ]; then
      echo "ctl 需要一个无空格控制命令，例如: $0 ctl 'resolve=on'" >&2
      exit 1
    fi
    dev "$(sq "$KP") $(sq "$SK") kpm ctl0 $(sq "$NAME") $(sq "$2") >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
    echo
    ;;
  push)
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    echo "pushed"
    ;;
  reload)
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    need_superkey
    dev "$(sq "$KP") $(sq "$SK") kpm unload $(sq "$NAME") 2>/dev/null; $(sq "$KP") $(sq "$SK") kpm load $(sq "$KPM_DEV")"
    ;;
  *)
    echo "用法: $0 [--superkey <key>|-k <key>] {load|unload|status|list|info|push|reload|ctl '<cmd>'}"
    exit 1
    ;;
esac
