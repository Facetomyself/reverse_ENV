#!/bin/bash
# 持续采集：流式抓取内核日志，期间你在手机上手动操作目标 App。
# 作者：小肩膀   微信：xiaojianbang8888
# 用法:
#   ./capture_live.sh cbgc start    启动目标App并开始后台采集（你随后手动操作手机）
#   ./capture_live.sh cbgc stop     停止采集并分类汇总
#   ./capture_live.sh m1905 start
#   ./capture_live.sh m1905 stop
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
  *) echo "用法: $0 {cbgc|m1905|sig|khapp|tuhu} {start|stop}"; exit 1 ;;
esac

# maps 快照间隔（秒）。秒闪退的 App 进程极短命，用 0.1s 高频抓。
SNAP_INTERVAL="${SNAP_INTERVAL:-0.1}"
SNAP_ROUNDS="${SNAP_ROUNDS:-6000}"

PIDFILE="/tmp/scf_live_${TAG}.pid"
RAW="$OUT/${TAG}_live_raw.log"

if [ "$2" = "start" ]; then
  dev "am force-stop $PKG"
  sleep 1
  # 清内核环形缓冲（去掉历史旧行，避免上一轮日志混入），并启动流式采集
  dev "dmesg -C" 2>/dev/null
  : > "$RAW"
  # 后台 adb 流式 dmesg -w（follow）
  (adb_cmd shell su -c "dmesg -w 2>/dev/null | grep --line-buffered '\[scfilter\]'" >> "$RAW" 2>/dev/null) &
  echo $! > "$PIDFILE"
  echo "采集已启动 (pid $(cat $PIDFILE)) -> $RAW"

  # 设备端 maps 快照器：高频(默认100ms)抓目标进程 maps。
  # 快照逻辑写在 scf_snap.sh，push 到设备后台运行（避免内联命令的多层引号解析问题）。
  # 用 pgrep 精准定位目标包进程（含子进程），一轮极快，秒闪退也能抓到。
  DEV_MAPDIR="/data/local/tmp/scf_maps_${TAG}"
  SNAP_US=$(awk "BEGIN{printf \"%d\", $SNAP_INTERVAL*1000000}")
  dev "rm -rf $DEV_MAPDIR; mkdir -p $DEV_MAPDIR"
  adb_cmd push "$DIR/scf_snap.sh" /data/local/tmp/scf_snap.sh >/dev/null 2>&1
  dev "chmod 755 /data/local/tmp/scf_snap.sh"
  dev "nohup /data/local/tmp/scf_snap.sh '$PKG' '$DEV_MAPDIR' '$SNAP_US' '$SNAP_ROUNDS' >/dev/null 2>&1 &" 2>/dev/null
  echo "maps 快照间隔: ${SNAP_INTERVAL}s (usleep ${SNAP_US}us, pgrep 精准定位)"

  echo "正在冷启动 $PKG ..."
  dev "monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1"
  echo ""
  echo ">>> 现在去手机上操作 App：同意隐私协议、进主页、点开几个功能、看视频/文章 <<<"
  echo ">>> 操作够了就运行:  ./capture_live.sh $TAG stop"
elif [ "$2" = "stop" ]; then
  if [ -f "$PIDFILE" ]; then
    kill "$(cat $PIDFILE)" 2>/dev/null
    # 同时杀掉设备端的 dmesg -w 和 maps 快照器
    dev "pkill -f 'dmesg -w'" 2>/dev/null
    dev "pkill -f scf_snap.sh" 2>/dev/null
    rm -f "$PIDFILE"
  fi
  sleep 1
  # 命中日志：含 [分类/关键词] 标签 + FAKE 行，保留完整行
  grep "uid:$APPUID" "$RAW" | grep -v ' DUMP ' > "$OUT/${TAG}_hits.log" || true
  # 全量日志：保留完整格式(syscall名 + [分类/关键词] 或 DUMP)，去掉时间戳和FAKE行后整行去重
  grep "uid:$APPUID" "$RAW" \
    | grep -v ' -> FAKE ' \
    | sed -E 's/^\[[0-9.]+\] //' \
    | sort -u > "$OUT/${TAG}_allpaths.log" || true

  if grep -q 'lrsym:' "$OUT/${TAG}_hits.log" 2>/dev/null; then
    # ---- 内核态解析模式(resolve=on)：日志里已带 pcsym/lrsym，直接提取，无需 maps ----
    "$DIR/resolve.py" --kresolve "$OUT/${TAG}_hits.log" > "$OUT/${TAG}_resolved.log"
    "$DIR/resolve.py" --kresolve "$OUT/${TAG}_allpaths.log" > "$OUT/${TAG}_allpaths_resolved.log"
    echo "命中解析:     $OUT/${TAG}_resolved.log (内核态解析, 无需 maps)"
    echo "全量解析:     $OUT/${TAG}_allpaths_resolved.log"
  else
    # ---- PC 端 maps 解析模式(resolve=off)：按 tgid 取 maps 解析 ----
    MAPSDIR="$OUT/${TAG}_maps"
    rm -rf "$MAPSDIR"; mkdir -p "$MAPSDIR"
    DEV_MAPDIR="/data/local/tmp/scf_maps_${TAG}"
    adb_cmd pull "$DEV_MAPDIR" "$MAPSDIR/_dev" >/dev/null 2>&1 && mv "$MAPSDIR/_dev"/maps_*.txt "$MAPSDIR/" 2>/dev/null
    rm -rf "$MAPSDIR/_dev"
    for tg in $(grep -hoE 'tgid:[0-9]+' "$OUT/${TAG}_hits.log" "$OUT/${TAG}_allpaths.log" 2>/dev/null | sed 's/tgid://' | sort -un); do
      [ -s "$MAPSDIR/maps_$tg.txt" ] && continue
      dev "cat /proc/$tg/maps" > "$MAPSDIR/maps_$tg.txt" 2>/dev/null || true
      [ -s "$MAPSDIR/maps_$tg.txt" ] || rm -f "$MAPSDIR/maps_$tg.txt"
    done
    dev "rm -rf $DEV_MAPDIR" 2>/dev/null
    ntg=$(ls "$MAPSDIR"/maps_*.txt 2>/dev/null | wc -l)
    if [ "$ntg" -gt 0 ]; then
      "$DIR/resolve.py" --mapsdir "$MAPSDIR" "$OUT/${TAG}_hits.log" > "$OUT/${TAG}_resolved.log" 2>/dev/null \
        && echo "命中解析:     $OUT/${TAG}_resolved.log (PC端 maps 解析, ${ntg} 个进程)"
      "$DIR/resolve.py" --mapsdir "$MAPSDIR" "$OUT/${TAG}_allpaths.log" > "$OUT/${TAG}_allpaths_resolved.log" 2>/dev/null \
        && echo "全量解析:     $OUT/${TAG}_allpaths_resolved.log"
    else
      echo "(resolve=off 且无 maps 快照，未解析；建议 ./load.sh ctl 'resolve=on' 用内核态解析)"
    fi
  fi
  echo "采集停止。"
  echo "原始:         $RAW ($(wc -l < "$RAW") 行)"
  echo "命中(含FAKE): $OUT/${TAG}_hits.log ($(wc -l < "$OUT/${TAG}_hits.log") 行)"
  echo "全量路径:     $OUT/${TAG}_allpaths.log ($(wc -l < "$OUT/${TAG}_allpaths.log") 行)"
  echo ""
  echo "命中分类:"
  grep -oE '\[(ROOT|FRIDA|XPOSED|AOSP)/' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
  echo "退出/信号事件:"
  grep -oE '\[(EXIT|SIGNAL)/[^]]+\]' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
  echo "内存/线程/调试事件:"
  grep -oE '\[(MEM|MEMFD|THREAD|DEBUG)[^]]*\]' "$OUT/${TAG}_hits.log" 2>/dev/null | sort | uniq -c || echo "  (无)"
else
  echo "用法: $0 {cbgc|m1905|sig|khapp|tuhu} {start|stop}"; exit 1
fi
