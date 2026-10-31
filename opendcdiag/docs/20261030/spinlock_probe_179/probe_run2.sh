#!/bin/bash
# Re-run of the spinlock stale-read probes with the BATCH-FIXED build
# (2^25 spins per framework call).  Run 1 (18:31-19:46) was disk-starved
# to ~0.3-5% duty (framework fdatasyncs the -o log on every
# test_time_condition() call; one spin per call = one journal wait per
# spin on ext4) -> phases 1/2 exposure-invalid.  See RESULTS.md.
# Activity context from run 1 phase 3 carries over: rowmajor 148 fails
# / 15min = 9.87/min, all logical 179 -> 179 ACTIVE tonight.
# Env logger (voltage + power + per-socket CPU util) runs from t0.
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/spinlock_probe_179
RUNS=$D/runs2
SUMMARY=$D/summary2.csv
MONLOG=$D/monitor.log
BIN=$R/builddir-spinlock-add/opendcdiag

mkdir -p "$RUNS"
if [ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" != "1" ]; then
  echo "[$(date '+%F %T')] RUN2 ABORT: cpu179 offline" >> "$MONLOG"; exit 1
fi
if pgrep -x opendcdiag >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] RUN2 ABORT: an opendcdiag process is already running" >> "$MONLOG"; exit 1
fi
taskset -c 144-191 true 2>/dev/null || { echo "[$(date '+%F %T')] RUN2 ABORT: mask 144-191 unusable" >> "$MONLOG"; exit 1; }
echo 'test,duration,start,end,rc,fails,streak_telemetry' > "$SUMMARY"
echo "[$(date '+%F %T')] RUN2 START (batch-fixed probes, 2^25 spins/call) | bin=$(sha256sum "$BIN" | cut -c1-16) | cpu179=online | mask=144-191 n=48 | context: 179 active tonight (rowmajor 9.87/min)" >> "$MONLOG"

# --- monitor (pinned to core 8; watchdog 95C) ---
(
  while true; do
    ts=$(date '+%F %T')
    t=$(timeout 12 sudo ipmitool sensor reading CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP 2>/dev/null | grep -oE 'CPU[0-9]_TEMP[ |]+[0-9]+' | tr -s ' ' | tr '\n' ';')
    echo "$ts | $t" >> "$MONLOG"
    hot=$(echo "$t" | grep -oE '[0-9]+' | sort -rn | head -1)
    if [ -n "$hot" ] && [ "$hot" -gt 95 ]; then
      echo "$ts RUN2 WATCHDOG ABORT: max CPU temp ${hot}C > 95C" >> "$MONLOG"
      pkill -x opendcdiag 2>/dev/null
      exit 9
    fi
    sleep 60
  done
) &
MONPID=$!
taskset -pc 8 "$MONPID" >/dev/null 2>&1

run_phase() {
    test=$1; dur=$2
    log=$RUNS/${test}.log
    start=$(date '+%F %T')
    taskset -c 144-191 "$BIN" -e "$test" -T "$dur" -n 48 --ignore-os-error --ignore-timeout -o "$log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
    tele=$(grep -c 'stale streak' "$log" 2>/dev/null); tele=${tele:-0}
    echo "${test},${dur},${start},${end},${rc},${fails},${tele}" >> "$SUMMARY"
    echo "[$end] RUN2 PHASE DONE ${test} rc=$rc fails=$fails telemetry=$tele" >> "$MONLOG"
}

run_phase spinlock_stale_read 30m
run_phase spinlock_stale_read_xchg 30m

kill "$MONPID" 2>/dev/null
echo "[$(date '+%F %T')] RUN2 COMPLETE" >> "$MONLOG"
