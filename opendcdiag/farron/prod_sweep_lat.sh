#!/bin/bash
# FARRON 生产节奏评估·时延版 (2026-10-27): 每30min一轮 + 探针随应用迁移
# 窗口协议与 prod_sweep.sh 完全一致(逐插槽独占30s窗, 检出/记账不变);
# 新增探针策略 (probe_pids.txt 每行 "PID 插槽名"):
#   本座被测   -> 该座探针迁出(与应用同 REST 掩码) —— 测"被迁出方"的延迟代价
#   他座被测   -> 本座探针留守原核(经受应用迁入者竞争) —— 测"被迁入方"的延迟代价
#   窗口结束   -> 探针回到本座钉核
# 用法: prod_sweep_lat.sh <总秒数> <输出目录名> [周期秒=1800]
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/farron/state/sweep/$2"
BIN="$REPO/builddir/opendcdiag"
PIDFILE="$REPO/farron/state/sweep/app.pid"
PIDLIST="$REPO/farron/state/sweep/probe_pids.txt"
APP_MASK="0-178,180-191"
PERIOD="${3:-1800}"
WIN=30
END=$(( $(date +%s) + $1 ))

mkdir -p "$OUT"
declare -A SOCK=( [CPU1]=0-47 [CPU2]=48-95 [CPU3]=96-143 [CPU4]=144-191 )
declare -A REST=( [CPU1]=48-191 [CPU2]=0-47,96-191 [CPU3]=0-95,144-191 [CPU4]=0-143 )

log(){ echo "[$(date '+%F %T')] $*" >> "$OUT/events.log"; }
ensure_app(){
  local pid=$(cat "$PIDFILE" 2>/dev/null)
  if ! kill -0 "$pid" 2>/dev/null; then
    log "stress-ng 不存活, 重启"
    nohup taskset -c "$APP_MASK" stress-ng --cpu 191 --timeout 8h -q >> "$OUT/stress_ng.log" 2>&1 &
    echo $! > "$PIDFILE"; sleep 8
  fi
}
set_app_mask(){
  local app=$(cat "$PIDFILE")
  for p in $app $(pgrep -P $app); do taskset -pc "$1" "$p" >/dev/null 2>&1; done
}
set_probe_masks(){   # $1 = 正在被测的插槽名; "" = 恢复
  [ -f "$PIDLIST" ] || return 0
  local arg="$1" pid home
  while read -r pid home; do
    [ -z "${pid:-}" ] && continue
    kill -0 "$pid" 2>/dev/null || continue
    if [ -z "$arg" ] || [ "$arg" = "$home" ]; then
      taskset -pc "${SOCK[$home]}" "$pid" >/dev/null 2>&1      # 回家/留守
    else
      taskset -pc "${REST[$home]}" "$pid" >/dev/null 2>&1       # 本座被测, 迁出
    fi
  done < "$PIDLIST"
}

echo "ts,sweep,socket,fails,cores,dur_s" > "$OUT/sweeps.csv"
echo "ts,sweep,socket,failn,elapsed_s" > "$OUT/fail_times.csv"
sw=0
log "生产节奏·时延版评估开始(总时长$1s, 周期${PERIOD}s): 每轮CPU1->CPU4各${WIN}s窗, 探针随应用迁移"
while [ $(date +%s) -lt $END ]; do
  RT0=$(date +%s)
  ensure_app
  sw=$((sw+1))
  for S in CPU1 CPU2 CPU3 CPU4; do
    [ $(date +%s) -ge $END ] && break
    t0=$(date +%s)
    set_app_mask "${REST[$S]}"
    set_probe_masks "$S"
    taskset -c "${SOCK[$S]}" "$BIN" -e neon_rot_ldr_at_top_rowmajor -n 48 -T ${WIN}s \
      --ignore-os-error --ignore-timeout \
      -o "$OUT/s${sw}_${S}.log" > "$OUT/s${sw}_${S}.stdout" 2>&1
    f=$(grep -c 'result: fail' "$OUT/s${sw}_${S}.log" 2>/dev/null); f=${f:-0}
    cores=$(grep -o 'logical: [0-9]*' "$OUT/s${sw}_${S}.stdout" 2>/dev/null | sort -u | tr '\n' ';' | sed 's/;$//;s/logical: //g')
    d=$(( $(date +%s) - t0 ))
    echo "$(date '+%F %T'),$sw,$S,$f,${cores},$d" >> "$OUT/sweeps.csv"
    if [ "$f" -gt 0 ]; then
      awk -v sw="$sw" -v S="$S" -v t0="$t0" '
        /^  time-at-start: \{ elapsed:/ { match($0,/elapsed: [0-9]+/); el=substr($0,RSTART+9,RLENGTH-9)+0 }
        /^  result: fail/ { pend=1 }
        /^  time-at-end:/ { if (pend) { pend=0; match($0,/elapsed: [0-9]+/); en=substr($0,RSTART+9,RLENGTH-9)+0
            printf "%s,%s,%s,%d,%.1f\n", strftime("%F %T"), sw, S, ++n, (el+en)/2000 } }' \
        "$OUT/s${sw}_${S}.log" >> "$OUT/fail_times.csv"
      cp "$OUT/s${sw}_${S}.stdout" "$OUT/keep_s${sw}_${S}.stdout"
    fi
    set_app_mask "$APP_MASK"
    set_probe_masks ""
    rm -f "$OUT/s${sw}_${S}.log" "$OUT/s${sw}_${S}.stdout"
  done
  RD=$(( $(date +%s) - RT0 ))
  NOW=$(date +%s); NEXT=$(( RT0 + PERIOD ))
  if [ $NOW -lt $NEXT ]; then
    log "轮$sw完成(耗时${RD}s), 休眠$(( NEXT - NOW ))s至下轮"
    sleep $(( NEXT - NOW ))
  else
    log "轮$sw完成(耗时${RD}s)超出周期, 立即开始下轮"
  fi
done
log "评估结束, 共 ${sw} 轮"
