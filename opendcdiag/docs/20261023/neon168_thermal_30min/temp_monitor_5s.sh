#!/bin/bash
# 温度监控 ~5s 采样 (2026-10-23 neon168 满载热测试, 目标=CPU4能否到70°C)
# 用法: temp_monitor_5s.sh <输出日志> [总时长秒,默认2200]
OUT="${1:?need output log path}"
DURATION="${2:-2200}"
end=$((SECONDS + DURATION))
echo "# ts CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP(degC) Power(W) ~5s采样" >> "$OUT"
while [ $SECONDS -lt $end ]; do
    t0=$SECONDS
    ts=$(date '+%F %T')
    vals=$(sudo ipmitool sensor reading "CPU1_TEMP" "CPU2_TEMP" "CPU3_TEMP" "CPU4_TEMP" "Power" 2>/dev/null \
      | awk -F'|' '{gsub(/[ \t]/,"",$1); gsub(/[ \t]/,"",$2); printf "%s=%s ", $1, $2}')
    echo "$ts ${vals% }" >> "$OUT"
    el=$((SECONDS - t0)); [ $el -lt 5 ] && sleep $((5 - el))
done
echo "$(date '+%F %T') MONITOR_DONE" >> "$OUT"
