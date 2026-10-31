#!/bin/bash
# CORE179 readpath 7 valid SDC testcases re-run (2026-09-14 night)
# 7 cells x 30min, full-core 192 (incl. 179), auto seed.
# ORDER REVERSED vs 2026-09-13 campaign (user directive) to decouple
#   trigger rate from wall-clock position (last night's order was
#   k5far, std, k4gap, k4bgap, k2pureload, k5ir, k7p_rand, k7p_zero,
#   k7p_one, k7p_hiham, k3res).
# Logs -> builddir/campaign_p0/runs/<cell>_rerun2.log
# Monitor: pinned off 179 (core 178), samples every 5 min, log on DISK
#   (not /tmp-only) per dump-campaign lesson.

set -u
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag

LOGDIR=builddir/campaign_p0/runs
mkdir -p "$LOGDIR"
MONLOG=$LOGDIR/rerun7_monitor.log
: > "$MONLOG"

# ---- monitor (pinned off 179) ----
(
while true; do
    ts=$(date '+%F %H:%M:%S')
    alive=$(pgrep -c -x opendcdiag 2>/dev/null || echo 0)
    cur=$(cat /tmp/rerun7_current 2>/dev/null || echo "-")
    ndump=$(ls movbe_log/gps_rowmajor/ 2>/dev/null | wc -l)
    ipmi=$(ipmitool sdr type temperature 2>/dev/null | grep -oE '[0-9]+ degrees C' | head -1 || echo "n/a")
    echo "$ts cell=$cur alive=$alive dumps=$ndump temp=$ipmi" >> "$MONLOG"
    sleep 300
done
) &
MONPID=$!
taskset -pc 178 $MONPID > /dev/null 2>&1

run_cell() {
    local name=$1; shift
    echo "$name" > /tmp/rerun7_current
    echo "[$(date '+%F %H:%M:%S')] START $name" >> "$MONLOG"
    taskset -c 0-191 ./builddir/opendcdiag -T 30m -n 192 "$@" \
        -o "$LOGDIR/${name}_rerun2.log" -q > /dev/null 2>&1
    local rc=$?
    local fails=$(grep -c '  result: fail' "$LOGDIR/${name}_rerun2.log" 2>/dev/null || echo 0)
    local passes=$(grep -c '  result: pass' "$LOGDIR/${name}_rerun2.log" 2>/dev/null || echo 0)
    echo "[$(date '+%F %H:%M:%S')] END $name rc=$rc pass=$passes fail=$fails" >> "$MONLOG"
}

# reversed order vs 2026-09-13 night
run_cell k3res            -e neon_rot_ldr_at_top_rowmajor_k3res
run_cell k7p_hiham        -e neon_rot_ldr_at_top_rowmajor_k7p_hiham
run_cell k7p_one          -e neon_rot_ldr_at_top_rowmajor_k7p_one
run_cell k7p_rand         -e neon_rot_ldr_at_top_rowmajor_k7p_rand
run_cell k5inter_rand     -e neon_rot_ldr_at_top_rowmajor_k5inter_rand
run_cell std_rowmajor     -e neon_rot_ldr_at_top_rowmajor
run_cell k5far            -e neon_rot_ldr_at_top_rowmajor_k5far

kill $MONPID 2>/dev/null
echo "[$(date '+%F %H:%M:%S')] RERUN7 COMPLETE" >> "$MONLOG"
