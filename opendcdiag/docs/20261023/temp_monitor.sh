#!/bin/bash
# BMC 温度/功耗定点监控 (2026-10-23 movbe 温度测量)
# 用法: temp_monitor.sh <输出日志> [总时长秒,默认1320] [采样间隔秒,默认10]
# 绑核建议: taskset -c 190 (用户预留的守护进程核)
OUT="${1:?need output log path}"
DURATION="${2:-1320}"
INTERVAL="${3:-10}"
end=$((SECONDS + DURATION))
echo "# ts CPUx_TEMP=degC CPUx_MEM=degC Power=W Power2=W (interval=${INTERVAL}s)" >> "$OUT"
while [ $SECONDS -lt $end ]; do
    ts=$(date '+%F %T')
    line=$(sudo ipmitool sensor reading "CPU1_TEMP" "CPU2_TEMP" "CPU3_TEMP" "CPU4_TEMP" \
          "CPU1 MEM Temp" "CPU2 MEM Temp" "CPU3 MEM Temp" "CPU4 MEM Temp" \
          "Power" "Power2" 2>/dev/null | awk -F'|' '{
              n=$1; gsub(/[ \t]/,"",n); v=$2; gsub(/[ \t]/,"",v);
              if (n ~ /^CPU[1-4]MEMTemp$/) sub(/MEMTemp/,"_MEM",n);
              printf "%s=%s ", n, v }')
    echo "$ts $line" >> "$OUT"
    sleep "$INTERVAL"
done
echo "$(date '+%F %T') MONITOR_DONE" >> "$OUT"
