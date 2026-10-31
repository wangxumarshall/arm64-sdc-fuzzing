#!/bin/bash
# 混合负载运行器 (2026-10-23 60%风扇版: CPU1+CPU2跑movbe轻载, CPU3+CPU4跑neon_rot满载, 主测CPU4稳态)
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
DIR=docs/20261023/mixed_fan60_15min
date '+%F %T %s' > $DIR/TEST_START
taskset -c 24-95 ./builddir/opendcdiag -e movbe -n 72 -T 15m --ignore-os-error --ignore-timeout \
    -o $DIR/movbe72.log > $DIR/movbe72.stdout 2>&1 &
MPID=$!
taskset -c 96-191 ./builddir/opendcdiag -e neon_rot_ldr_at_top_rowmajor -n 96 -T 15m --ignore-os-error --ignore-timeout \
    -o $DIR/neon96.log > $DIR/neon96.stdout 2>&1 &
NPID=$!
wait $MPID; MEC=$?
wait $NPID; NEC=$?
date '+%F %T %s' > $DIR/TEST_END
echo "movbe72 EXIT=$MEC" >> $DIR/TEST_END
echo "neon96 EXIT=$NEC" >> $DIR/TEST_END
cat $DIR/TEST_END
