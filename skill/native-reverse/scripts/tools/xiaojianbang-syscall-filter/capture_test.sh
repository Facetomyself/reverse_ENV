#!/bin/bash
# 单 App 测试：冷启动一个目标 App，抓内核 dmesg 里的 [scfilter] 日志
# 作者：小肩膀   微信：xiaojianbang8888
#
# 用法:
#   ./capture_test.sh cbgc          测川观新闻 (uid 10236)
#   ./capture_test.sh m1905         测1905电影 (uid 10240)
#   ./capture_test.sh tuhu          测 signed.apk / 途虎 (uid 10239)
#   ./capture_test.sh cbgc 20       启动后采集 20 秒（默认 12 秒）
#
# 会同时保存「命中」和「全量 DUMP」两份日志（需先 ./load.sh ctl 'dump=on'）
set -e
ADB="${XJB_ADB:-${ADB:-adb}}"
DIR="$(dirname "$0")"
OUT="$DIR/logs"
mkdir -p "$OUT"
adb_cmd() { "$ADB" "$@"; }
dev() { adb_cmd shell su -c "$*"; }

case "$1" in
  cbgc)   PKG=com.sichuanol.cbgc;          APPUID=10236; TAG=cbgc ;;
  m1905)  PKG=com.m1905.mobilefree;        APPUID=10240; TAG=m1905 ;;
  sig)    PKG=com.dheaven.mscapp.SIGFFCNFN; APPUID=10237; TAG=sig ;;
  khapp)  PKG=com.sinosig.khapp;           APPUID=10238; TAG=khapp ;;
  tuhu)   PKG=cn.TuHu.android;             APPUID=10239; TAG=tuhu ;;
  *) echo "用法: $0 {cbgc|m1905|sig|khapp|tuhu} [采集秒数]"; exit 1 ;;
esac
WAIT="${2:-12}"

echo "目标: $PKG (uid $APPUID), 采集 ${WAIT}s"
# 关闭所有App，只启目标，保证日志干净
dev "am force-stop $PKG"
sleep 1
# 清内核环形缓冲，避免历史日志和 dmesg 时间戳格式影响本轮结果
dev "dmesg -C" 2>/dev/null || true
echo "冷启动 ..."
dev "monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1"
sleep "$WAIT"

dev "dmesg 2>/dev/null | grep '\[scfilter\]'" > "$OUT/${TAG}_raw.log" || true

# 命中（含 FAKE 行）
grep "uid:$APPUID" "$OUT/${TAG}_raw.log" | grep -v ' DUMP ' > "$OUT/${TAG}_hits.log" || true
# 全量（保留 syscall名 + [分类/关键词] 或 DUMP 标签，去时间戳和FAKE行后整行去重）
grep "uid:$APPUID" "$OUT/${TAG}_raw.log" \
  | grep -v ' -> FAKE ' \
  | sed -E 's/^\[[0-9.]+\] //' \
  | sort -u > "$OUT/${TAG}_allpaths.log" || true

if grep -q 'lrsym:' "$OUT/${TAG}_hits.log" 2>/dev/null; then
  "$DIR/resolve.py" --kresolve "$OUT/${TAG}_hits.log" > "$OUT/${TAG}_resolved.log"
  "$DIR/resolve.py" --kresolve "$OUT/${TAG}_allpaths.log" > "$OUT/${TAG}_allpaths_resolved.log"
fi

echo "----"
echo "原始:            $OUT/${TAG}_raw.log       ($(wc -l < "$OUT/${TAG}_raw.log") 行)"
echo "命中(含FAKE):    $OUT/${TAG}_hits.log      ($(wc -l < "$OUT/${TAG}_hits.log") 行)"
echo "全量去重路径:    $OUT/${TAG}_allpaths.log  ($(wc -l < "$OUT/${TAG}_allpaths.log") 行)"
[ -f "$OUT/${TAG}_resolved.log" ] && echo "命中解析:        $OUT/${TAG}_resolved.log"
echo ""
echo "命中分类统计:"
grep -oE '\[(ROOT|FRIDA|XPOSED|AOSP)/' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
echo "退出/信号事件:"
grep -oE '\[(EXIT|SIGNAL)/[^]]+\]' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
echo "内存/线程/调试事件:"
grep -oE '\[(MEM|MEMFD|THREAD|DEBUG)[^]]*\]' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
