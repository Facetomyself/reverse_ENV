#!/system/bin/sh
# 设备端 maps 快照器（被 capture_live.sh push 到设备后台运行）
# 参数: $1=包名  $2=输出目录  $3=usleep微秒  $4=轮数
# 作者：小肩膀   微信：xiaojianbang8888
PKG="$1"
OUTDIR="$2"
US="$3"
ROUNDS="$4"
mkdir -p "$OUTDIR"
i=0
while [ "$i" -lt "$ROUNDS" ]; do
  for p in $(pgrep -f "$PKG" 2>/dev/null); do
    if [ ! -f "$OUTDIR/maps_$p.txt" ]; then
      cat "/proc/$p/maps" > "$OUTDIR/maps_$p.txt" 2>/dev/null
    fi
  done
  usleep "$US"
  i=$((i+1))
done
