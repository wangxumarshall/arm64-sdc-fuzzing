#!/bin/bash
# CORE179 -O0 vs -O3 campaign CONTINUATION (2026-10-30, ~01:42)
# Original campaign.sh (harness-tracked background task) was killed at
# ~01:34:35 when the CLI session died on an API error; its monitor
# subshell died with it (monitor.log stops at 01:34:19). Run 1 (O3
# rowmajor, PID 1545189) survived as an orphan and is left to finish
# on its own (-T 30m self-terminates ~01:58:33; affinity 24-191
# verified). This script restarts the monitor/watchdog, waits for
# run 1, records its summary row (rc=orphan), then executes runs 2-10
# exactly as originally scheduled.
# Launched with setsid+nohup so it is NOT tied to the CLI session.
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/o0_compile_experiment
RUNS=$D/runs
SUMMARY=$D/summary.csv
MONLOG=$D/monitor.log
O3BIN=$R/builddir/opendcdiag
O0BIN=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag-O0/builddir/opendcdiag
RUN1_PID=1545189

# --- preflight ---
if [ -f "$D/ABORT" ]; then
  echo "[$(date '+%F %T')] RESUME ABORT: stale ABORT file present" >> "$MONLOG"; exit 1
fi
if ! grep -q opendcdiag /proc/$RUN1_PID/cmdline 2>/dev/null; then
  echo "[$(date '+%F %T')] RESUME NOTE: run1 already gone, proceeding to runs 2-10" >> "$MONLOG"
fi
echo "[$(date '+%F %T')] RESUME START (continuation script; monitor gap was 01:34:19 -> now)" >> "$MONLOG"

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

# --- wait for orphaned run 1 to finish (it self-terminates via -T 30m) ---
deadline=$(( $(date +%s) + 2400 ))
while [ -d /proc/$RUN1_PID ] && grep -q opendcdiag /proc/$RUN1_PID/cmdline 2>/dev/null; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "[$(date '+%F %T')] RUN1 WATCHDOG: still alive 40min after resume start, killing" >> "$MONLOG"
    kill -9 "$RUN1_PID" 2>/dev/null; sleep 2; break
  fi
  sleep 10
done
log=$RUNS/O3_neon_rot_ldr_at_top_rowmajor.log
fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
passes=$(grep -c 'result: pass' "$log" 2>/dev/null); passes=${passes:-0}
loops=$(grep -c '# Loop iteration' "$log" 2>/dev/null); loops=${loops:-0}
echo "O3,neon_rot_ldr_at_top_rowmajor,2026-10-30 01:28:33,$(date '+%F %T'),orphan,${fails},${passes},${loops}" >> "$SUMMARY"
echo "[$(date '+%F %T')] RUN DONE O3 neon_rot_ldr_at_top_rowmajor rc=orphan fails=$fails passes=$passes loops=$loops" >> "$MONLOG"

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

# --- remaining schedule (unchanged from campaign.sh) ---
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
