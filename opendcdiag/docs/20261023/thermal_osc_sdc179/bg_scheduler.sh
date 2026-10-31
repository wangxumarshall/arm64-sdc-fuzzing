#!/bin/bash
# 背景热震荡调度器 (2026-10-23 热震荡-SDC 实验)
# 164核(24-178,180-188, 不含179) 交替 movbe <-> neon_rot_ldr_at_top_rowmajor 各5min x6轮
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
DIR=docs/20261023/thermal_osc_sdc179
MASK=24-178,180-188
for i in 1 2 3 4 5 6; do
    echo "$(date '+%F %T %s') ROUND$i movbe START" >> "$DIR/scheduler.log"
    taskset -c $MASK ./builddir/opendcdiag -e movbe -n 164 -T 5m --ignore-os-error --ignore-timeout \
        -o "$DIR/bg_movbe_r${i}.log" > "$DIR/bg_movbe_r${i}.stdout" 2>&1
    echo "$(date '+%F %T %s') ROUND$i movbe END ec=$?" >> "$DIR/scheduler.log"
    echo "$(date '+%F %T %s') ROUND$i neon_rot START" >> "$DIR/scheduler.log"
    taskset -c $MASK ./builddir/opendcdiag -e neon_rot_ldr_at_top_rowmajor -n 164 -T 5m --ignore-os-error --ignore-timeout \
        -o "$DIR/bg_neon_r${i}.log" > "$DIR/bg_neon_r${i}.stdout" 2>&1
    echo "$(date '+%F %T %s') ROUND$i neon_rot END ec=$?" >> "$DIR/scheduler.log"
done
echo "$(date '+%F %T %s') SCHEDULER_DONE" >> "$DIR/scheduler.log"
