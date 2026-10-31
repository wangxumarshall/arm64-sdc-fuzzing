#!/bin/bash
# CORE179 -O0 vs -O3 compile-strategy campaign (night of 2026-10-30)
# 5 tests x 2 arms x 30min per run, alternating first arm per test.
# Mask 24-191 (168 cores incl 179), -n 168, auto seed.
# Monitor: 60s temp/fan sampling pinned to core 8 (outside test mask);
# watchdog aborts the campaign if any CPU temp exceeds 95C.
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/o0_compile_experiment
RUNS=$D/runs
SUMMARY=$D/summary.csv
MONLOG=$D/monitor.log
O3BIN=$R/builddir/opendcdiag
O0BIN=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag-O0/builddir/opendcdiag

# --- preflight ---
if [ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" != "1" ]; then
    echo "[$(date '+%F %T')] ABORT: cpu179 is offline" >> "$MONLOG"; exit 1
fi
if pgrep -x opendcdiag >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] ABORT: an opendcdiag process is already running" >> "$MONLOG"; exit 1
fi
taskset -c 24-191 true 2>/dev/null || { echo "[$(date '+%F %T')] ABORT: mask 24-191 unusable" >> "$MONLOG"; exit 1; }
[ -f "$SUMMARY" ] || echo 'arm,test,start,end,rc,fails,passes,loops' > "$SUMMARY"
echo "[$(date '+%F %T')] CAMPAIGN START | O3=$(sha256sum "$O3BIN" | cut -c1-16) O0=$(sha256sum "$O0BIN" | cut -c1-16) | cpu179=online | mask=24-191 n=168 | fans=manual-100%" >> "$MONLOG"

# --- monitor (pinned to core 8: outside test mask, away from 179) ---
(
  while true; do
    ts=$(date '+%F %T')
    t=$(timeout 12 sudo ipmitool sensor reading CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP 2>/dev/null | grep -oE 'CPU[0-9]_TEMP[ |]+[0-9]+' | tr -s ' ' | tr '\n' ';')
    f=$(timeout 12 sudo ipmitool sensor reading "FAN1 F Speed" "FAN4 F Speed" "FAN6 F Speed" 2>/dev/null | grep -oE '[0-9]+ RPM' | tr '\n' ' ')
    echo "$ts | $t| fans: $f" >> "$MONLOG"
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

run_one() {
    arm=$1; test=$2; bin=$3
    if [ -f "$D/ABORT" ]; then return 9; fi
    log=$RUNS/${arm}_${test}.log
    start=$(date '+%F %T')
    taskset -c 24-191 "$bin" -e "$test" -T 30m -n 168 --ignore-os-error --ignore-timeout -o "$log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
    passes=$(grep -c 'result: pass' "$log" 2>/dev/null); passes=${passes:-0}
    loops=$(grep -c '# Loop iteration' "$log" 2>/dev/null); loops=${loops:-0}
    echo "${arm},${test},${start},${end},${rc},${fails},${passes},${loops}" >> "$SUMMARY"
    echo "[$end] RUN DONE ${arm} ${test} rc=$rc fails=$fails passes=$passes loops=$loops" >> "$MONLOG"
}

# --- schedule: alternate first arm per test (drift cancellation) ---
run_one O3 neon_rot_ldr_at_top_rowmajor "$O3BIN"
run_one O0 neon_rot_ldr_at_top_rowmajor "$O0BIN"
run_one O0 neon_rot_ldr_at_top_sub      "$O0BIN"
run_one O3 neon_rot_ldr_at_top_sub      "$O3BIN"
run_one O3 mrn_reloaded_2src_alu        "$O3BIN"
run_one O0 mrn_reloaded_2src_alu        "$O0BIN"
run_one O0 neon_rot_ldr_at_top_str3     "$O0BIN"
run_one O3 neon_rot_ldr_at_top_str3     "$O3BIN"
run_one O3 movbe                        "$O3BIN"
run_one O0 movbe                        "$O0BIN"

kill "$MONPID" 2>/dev/null
if [ -f "$D/ABORT" ]; then
  echo "[$(date '+%F %T')] CAMPAIGN ABORTED (watchdog)" >> "$MONLOG"
else
  echo "[$(date '+%F %T')] CAMPAIGN COMPLETE" >> "$MONLOG"
fi
