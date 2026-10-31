#!/bin/bash
# 连续热保护看门狗 (2026-10-24 风扇扫描阶段)
# 任一插槽温度 >=98°C 连续2次采样 -> 杀掉 opendcdiag 并记录; 长时运行(24h)
LOG="${1:?need monitor log path}"
OUT="$(dirname "$LOG")/watchdog.log"
echo "$(date '+%F %T') WATCHDOG_START 阈值98°C x2连续 (连续模式)" >> "$OUT"
hot=0
end=$((SECONDS + 86400))
while [ $SECONDS -lt $end ]; do
    t=$(grep -v '^#' "$LOG" 2>/dev/null | grep 'CPU4_TEMP' | tail -1)
    if [ -n "$t" ]; then
        over=""
        for s in CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP; do
            v=$(echo "$t" | grep -o "$s=[0-9]*" | cut -d= -f2)
            [ -n "$v" ] && [ "$v" -ge 98 ] && over="$over $s=$v"
        done
        if [ -n "$over" ]; then
            hot=$((hot+1))
            echo "$(date '+%F %T') HOT#$hot:$over" >> "$OUT"
            if [ $hot -ge 2 ]; then
                echo "$(date '+%F %T') ABORT: killing opendcdiag" >> "$OUT"
                pkill -x opendcdiag
                echo "$(date '+%F %T') KILLED" >> "$OUT"
                exit 0
            fi
        else
            hot=0
        fi
    fi
    sleep 5
done
