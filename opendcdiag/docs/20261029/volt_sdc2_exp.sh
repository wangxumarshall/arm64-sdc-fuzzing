#!/bin/bash
# SDC 时刻电压实验 v2 (2026-10-29): CPU4-only 版
# v1 全核版因 CPU2 冲 96°C 被热保护中止(54s, 3 fail 已留存 volt_sdc/)
# 本版: 60s 空载基线 → 600s CPU4-only neon (144-191, 48 核含 179) → 80s 恢复
#   CPU4 电压轨只由 CPU4 自身负载决定 → 对 179/CPU4 轨电压问题电气等效
# 采样: ~1s, 4×N_VDDAVS + 4×VDDAVS + 2×1.8V + 4×温度 + 功耗; 热保护 ≥96°C×2
set -u
REPO=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
OUT="$REPO/docs/20261029/volt_sdc2"
BIN="$REPO/builddir/opendcdiag"
mkdir -p "$OUT"
DUR=740
SENS=(N_VDDAVS_CPU1 N_VDDAVS_CPU2 N_VDDAVS_CPU3 N_VDDAVS_CPU4 "CPU1 VDDAVS" "CPU2 VDDAVS" "CPU3 VDDAVS" "CPU4 VDDAVS" V_1V8_CPU_1 V_1V8_CPU_2 CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP Power)

echo "[$(date '+%F %T')] 实验v2开始: 60s基线 + 600s CPU4-only负载(48核) + 80s恢复" >> "$OUT/events.log"
(
  end=$((SECONDS + DUR)); hot=0
  while [ $SECONDS -lt $end ]; do
    t0=$SECONDS
    ts=$(date '+%F %T.%3N')
    vals=$(sudo ipmitool sensor reading "${SENS[@]}" 2>/dev/null | awk -F'|' '{gsub(/[ \t]/,"",$1); gsub(/[ \t]/,"",$2); printf "%s=%s ", $1, $2}')
    echo "$ts ${vals% }" >> "$OUT/sensors.log"
    t1=$(echo "$vals" | grep -o 'CPU1_TEMP=[0-9]*' | cut -d= -f2)
    t2=$(echo "$vals" | grep -o 'CPU2_TEMP=[0-9]*' | cut -d= -f2)
    t3=$(echo "$vals" | grep -o 'CPU3_TEMP=[0-9]*' | cut -d= -f2)
    t4=$(echo "$vals" | grep -o 'CPU4_TEMP=[0-9]*' | cut -d= -f2)
    over=0
    for tv in "$t1" "$t2" "$t3" "$t4"; do
      [ -n "$tv" ] && [ "$tv" -ge 96 ] && over=1
    done
    if [ "$over" -eq 1 ]; then
      hot=$((hot+1))
      if [ "$hot" -ge 2 ]; then
        echo "[$(date '+%F %T')] !! 热保护触发 (CPU1=$t1 CPU2=$t2 CPU3=$t3 CPU4=$t4), 杀测试" >> "$OUT/events.log"
        pkill -f "opendcdiag -e neon_rot" 2>/dev/null
        hot=0
      fi
    else
      hot=0
    fi
    el=$((SECONDS - t0)); [ "$el" -lt 1 ] && sleep 0.2
  done
  echo "$(date '+%F %T') MONITOR_DONE" >> "$OUT/sensors.log"
) &
MON=$!

sleep 60
echo "[$(date '+%F %T')] 启动 CPU4-only neon (144-191 含179), 600s" >> "$OUT/events.log"
taskset -c 144-191 "$BIN" -e neon_rot_ldr_at_top_rowmajor -n 48 -T 600s \
  --ignore-os-error --ignore-timeout -o "$OUT/run.log" > "$OUT/run.stdout" 2>&1
EC=$?
echo "[$(date '+%F %T')] 测试结束 exit=$EC, fail块=$(grep -c 'result: fail' "$OUT/run.log" 2>/dev/null)" >> "$OUT/events.log"
wait $MON
echo "[$(date '+%F %T')] 实验完成" >> "$OUT/events.log"
