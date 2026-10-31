#!/bin/bash
# CORE179 readpath K-cells unified campaign run (2026-09-13 night)
# Runs all 11 cells + interleaved standard cell, 30min each, full-core
# 192 (incl. 179), auto seed. Logs to builddir/campaign_p0/runs/,
# dumps accumulate in movbe_log/gps_rowmajor/ (per-cell prefixes).
# Monitor: pinned off 179, samples every 5 min.

set -u
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag

LOGDIR=builddir/campaign_p0/runs
mkdir -p "$LOGDIR"
MONLOG=/tmp/kcells_monitor.log
: > "$MONLOG"

# ---- monitor (pinned off 179) ----
(
while true; do
    ts=$(date +%H:%M:%S)
    alive=$(pgrep -c -x opendcdiag 2>/dev/null || echo 0)
    cur=$(cat /tmp/kcells_current 2>/dev/null || echo "-")
    ndump=$(ls movbe_log/gps_rowmajor/ 2>/dev/null | wc -l)
    ipmi=$(ipmitool sdr type temperature 2>/dev/null | grep -oE '[0-9]+ degrees C' | head -1 || echo "n/a")
    echo "$ts cell=$cur alive=$alive dumps=$ndump temp=$ipmi" >> "$MONLOG"
    sleep 300
done
) &
MONPID=$!
taskset -pc 178 $MONPID > /dev/null 2>&1

# ---- cell schedule (design doc §13 order, standard cell interleaved) ----
run_cell() {
    local name=$1; shift
    echo "$name" > /tmp/kcells_current
    echo "[$(date +%H:%M:%S)] START $name" >> "$MONLOG"
    taskset -c 0-191 ./builddir/opendcdiag -T 30m -n 192 "$@" \
        -o "$LOGDIR/${name}.log" -q > /dev/null 2>&1
    local rc=$?
    local fails=$(grep -c 'result: fail' "$LOGDIR/${name}.log" 2>/dev/null || echo 0)
    local passes=$(grep -c 'result: pass' "$LOGDIR/${name}.log" 2>/dev/null || echo 0)
    echo "[$(date +%H:%M:%S)] END $name rc=$rc pass=$passes fail=$fails" >> "$MONLOG"
}

# P1: decisive cell first
run_cell k5far            -e neon_rot_ldr_at_top_rowmajor_k5far
# interleaved standard cell (drift baseline, natural data)
run_cell std_rowmajor     -e neon_rot_ldr_at_top_rowmajor
# P3: gap cells
run_cell k4gap            -e neon_rot_ldr_at_top_rowmajor_k4gap
run_cell k4bgap           -e neon_rot_ldr_at_top_rowmajor_k4bgap
# P2: store geometry
run_cell k2pureload       -e neon_rot_ldr_at_top_rowmajor_k2pureload
# A-track pair
run_cell k5inter_rand     -e neon_rot_ldr_at_top_rowmajor_k5inter_rand
run_cell k7p_rand         -e neon_rot_ldr_at_top_rowmajor_k7p_rand
# pattern gradient
run_cell k7p_zero         -e neon_rot_ldr_at_top_rowmajor_k7p_zero
run_cell k7p_one          -e neon_rot_ldr_at_top_rowmajor_k7p_one
run_cell k7p_hiham        -e neon_rot_ldr_at_top_rowmajor_k7p_hiham
# residency
run_cell k3res            -e neon_rot_ldr_at_top_rowmajor_k3res

kill $MONPID 2>/dev/null
echo "[$(date +%H:%M:%S)] CAMPAIGN COMPLETE" >> "$MONLOG"
