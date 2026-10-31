#!/bin/bash
# 应用影响采样器: 每15s记录stress-ng全体进程的CPU时间(utime+stime, ticks)
# 用途: 从CPU时间斜率看出每次插槽窗口对应用的吞吐损失
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?outdir}"
PIDFILE="$REPO/farron/state/sweep/app.pid"
mkdir -p "$OUT"
END=$(( $(date +%s) + ${2:-10800} + 300 ))
echo "ts,cpu_ticks" > "$OUT/app_cpu.csv"
while [ $(date +%s) -lt $END ]; do
  APP=$(cat "$PIDFILE" 2>/dev/null)
  if [ -n "$APP" ] && kill -0 "$APP" 2>/dev/null; then
    u=$(for p in $APP $(pgrep -P $APP); do awk '{print $14+$15}' /proc/$p/stat 2>/dev/null; done | awk '{s+=$1} END{print s+0}')
    echo "$(date +%s),$u" >> "$OUT/app_cpu.csv"
  fi
  sleep 15
done
