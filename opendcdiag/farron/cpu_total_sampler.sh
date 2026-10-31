#!/bin/bash
# 全机总CPU采样: 每15s记录/proc/stat聚合行 busy ticks与total ticks
OUT="$1"; mkdir -p "$OUT"
END=$(( $(date +%s) + ${2:-10800} + 300 ))
echo "ts,busy_ticks,total_ticks" > "$OUT/cpu_total.csv"
while [ $(date +%s) -lt $END ]; do
  read -r _ u n s i w irq sirq st _ < /proc/stat
  echo "$(date +%s),$((u+n+s+irq+sirq+st)),$((u+n+s+i+w+irq+sirq+st))" >> "$OUT/cpu_total.csv"
  sleep 15
done
