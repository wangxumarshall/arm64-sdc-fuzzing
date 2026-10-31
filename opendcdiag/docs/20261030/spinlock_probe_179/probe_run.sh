#!/bin/bash
# CORE179 spinlock_add probe positive-control (2026-10-30)
# Question (user): does core 179's known read-path defect trigger the
# spinlock stale-read probes?  "本机器可能没有这类sdc，但是试试也可以。"
#
# Phases (mask 144-191, 48 cores incl 179, -n 48, auto seed):
#   1. spinlock_stale_read      30m   (probe, CAS arm; builddir-spinlock-add)
#   2. spinlock_stale_read_xchg 30m   (probe, xchg arm; builddir-spinlock-add)
#   3. neon_rot_ldr_at_top_rowmajor 15m  (activity check; BASELINE binary
#      a05c1763 - NOT the fresh build: relinking shifts code layout and
#      rowmajor's trigger is layout-sensitive; the baseline is the only
#      binary with a known rate reference, ~14/min CPU4-only)
# Interpretation: rowmajor>0 & probes 0  -> 179 active, probes don't catch
# its pattern; probe fail -> validated on the positive control.
# Monitor pinned to core 8; watchdog 95C; voltage logger from t0.
# Launched setsid+nohup (NOT tied to the CLI session).
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/spinlock_probe_179
RUNS=$D/runs
SUMMARY=$D/summary.csv
MONLOG=$D/monitor.log
BIN=$R/builddir-spinlock-add/opendcdiag
BASEBIN=$R/builddir/opendcdiag

mkdir -p "$RUNS"
if [ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" != "1" ]; then
  echo "[$(date '+%F %T')] ABORT: cpu179 offline" >> "$MONLOG"; exit 1
fi
if pgrep -x opendcdiag >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] ABORT: an opendcdiag process is already running" >> "$MONLOG"; exit 1
fi
taskset -c 144-191 true 2>/dev/null || { echo "[$(date '+%F %T')] ABORT: mask 144-191 unusable" >> "$MONLOG"; exit 1; }
echo 'test,duration,start,end,rc,fails,streak_telemetry' > "$SUMMARY"
echo "[$(date '+%F %T')] PROBE RUN START | probebin=$(sha256sum "$BIN" | cut -c1-16) basebin=$(sha256sum "$BASEBIN" | cut -c1-16) | cpu179=online | mask=144-191 n=48 | fans=manual-100%" >> "$MONLOG"

# --- monitor (pinned to core 8: outside test mask, away from 179) ---
(
  while true; do
    ts=$(date '+%F %T')
    t=$(timeout 12 sudo ipmitool sensor reading CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP 2>/dev/null | grep -oE 'CPU[0-9]_TEMP[ |]+[0-9]+' | tr -s ' ' | tr '\n' ';')
    echo "$ts | $t" >> "$MONLOG"
    hot=$(echo "$t" | grep -oE '[0-9]+' | sort -rn | head -1)
    if [ -n "$hot" ] && [ "$hot" -gt 95 ]; then
      echo "$ts WATCHDOG ABORT: max CPU temp ${hot}C > 95C" >> "$MONLOG"
      touch "$D/ABORT"
      pkill -x opendcdiag 2>/dev/null
      exit 9
    fi
    sleep 60
  done
) &
MONPID=$!
taskset -pc 8 "$MONPID" >/dev/null 2>&1

run_phase() {
    test=$1; dur=$2; bin=$3
    log=$RUNS/${test}.log
    start=$(date '+%F %T')
    taskset -c 144-191 "$bin" -e "$test" -T "$dur" -n 48 --ignore-os-error --ignore-timeout -o "$log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
    tele=$(grep -c 'stale streak' "$log" 2>/dev/null); tele=${tele:-0}
    echo "${test},${dur},${start},${end},${rc},${fails},${tele}" >> "$SUMMARY"
    echo "[$end] PHASE DONE ${test} rc=$rc fails=$fails telemetry=$tele" >> "$MONLOG"
}

run_phase spinlock_stale_read 30m "$BIN"
run_phase spinlock_stale_read_xchg 30m "$BIN"
run_phase neon_rot_ldr_at_top_rowmajor 15m "$BASEBIN"

kill "$MONPID" 2>/dev/null
echo "[$(date '+%F %T')] PROBE RUN COMPLETE" >> "$MONLOG"
