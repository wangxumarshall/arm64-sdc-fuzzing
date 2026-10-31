#!/bin/bash
# 连续混合负载运行器 (2026-10-24 风扇扫描阶段: 用户逐档调风扇, 记录各配置稳态)
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
DIR=docs/20261024/mixed_continuous
date '+%F %T %s' > $DIR/LOAD_START
taskset -c 24-95 ./builddir/opendcdiag -e movbe -n 72 -T 24h --ignore-os-error --ignore-timeout \
    -o $DIR/movbe72.log > $DIR/movbe72.stdout 2>&1 &
MPID=$!
taskset -c 96-191 ./builddir/opendcdiag -e neon_rot_ldr_at_top_rowmajor -n 96 -T 24h --ignore-os-error --ignore-timeout \
    -o $DIR/neon96.log > $DIR/neon96.stdout 2>&1 &
NPID=$!
echo "MPID=$MPID NPID=$NPID" > $DIR/PIDS
wait $MPID; MEC=$?
wait $NPID; NEC=$?
date '+%F %T %s' > $DIR/LOAD_END
echo "movbe72 EXIT=$MEC" >> $DIR/LOAD_END
echo "neon96 EXIT=$NEC" >> $DIR/LOAD_END
