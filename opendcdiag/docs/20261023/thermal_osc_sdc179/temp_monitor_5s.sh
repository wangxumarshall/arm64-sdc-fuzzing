#!/bin/bash
# 温度监控 ~5s 采样 (2026-10-23 热震荡-SDC 实验, 探针=179/CPU4插槽)
# 用法: temp_monitor_5s.sh <输出日志> [总时长秒,默认3960]
OUT="${1:?need output log path}"
DURATION="${2:-3960}"
end=$((SECONDS + DURATION))
echo "# ts CPU1_TEMP..CPU4_TEMP(degC) Power(W) 目标5s采样" >> "$OUT"
while [ $SECONDS -lt $end ]; do
    t0=$SECONDS
    ts=$(date '+%F %T')
    line=$(sudo ipmitool sensor reading "CPU1_TEMP" "CPU2_TEMP" "CPU3_TEMP" "CPU4_TEMP" "Power" 2>/dev/null | awk -F'|' '{n=$1; gsub(/[ \t]/,"",n); v=$2; gsub(/[ \t]/,"",v); printf "%s=%s ", n, v}')
    echo "$ts $line" >> "$OUT"
    d=$((SECONDS - t0))
    s=$((5 - d))
    if [ $s -gt 0 ]; then sleep $s; fi
done
echo "$(date '+%F %T') MONITOR_DONE" >> "$OUT"
