#!/bin/bash
# CORE179 CPU4-only rowmajor 1h - O0 ARM (2026-10-30 late morning)
# Paired with the -O3 run that just finished (docs/20261030/cpu4_rowmajor_1h:
# 885 fails / 14.75 min, all logical 179). Question (user): does the -O0
# binary stay at ZERO detection in the CPU4-only configuration?
# (Last night, full mask: O0 rowmajor = 0 fail / 1516 loops / 30min.)
# Mask 144-191 (48 cores incl 179), -n 48, -T 1h, auto seed,
# fans manual 99999s + 100% (standing). Voltage/power logger runs
# from t0 (separate detached process).
# Launched setsid+nohup (NOT tied to the CLI session).
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/cpu4_rowmajor_1h_O0
RUNS=$D/runs
SUMMARY=$D/summary.csv
MONLOG=$D/monitor.log
O0BIN=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag-O0/builddir/opendcdiag
TEST=neon_rot_ldr_at_top_rowmajor

mkdir -p "$RUNS"
if [ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" != "1" ]; then
  echo "[$(date '+%F %T')] ABORT: cpu179 offline" >> "$MONLOG"; exit 1
fi
if pgrep -x opendcdiag >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] ABORT: an opendcdiag process is already running" >> "$MONLOG"; exit 1
fi
taskset -c 144-191 true 2>/dev/null || { echo "[$(date '+%F %T')] ABORT: mask 144-191 unusable" >> "$MONLOG"; exit 1; }
echo 'arm,test,start,end,rc,fails,passes,loops' > "$SUMMARY"
echo "[$(date '+%F %T')] RUN START | O0=$(sha256sum "$O0BIN" | cut -c1-16) | cpu179=online | mask=144-191 n=48 | -T 1h auto seed | fans=manual-100%(standing) | paired-O3-arm=885f/14.75min" >> "$MONLOG"

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

log=$RUNS/O0_rowmajor_cpu4only_1h.log
start=$(date '+%F %T')
taskset -c 144-191 "$O0BIN" -e "$TEST" -T 1h -n 48 --ignore-os-error --ignore-timeout -o "$log" -q >/dev/null 2>&1
rc=$?
end=$(date '+%F %T')
fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
passes=$(grep -c 'result: pass' "$log" 2>/dev/null); passes=${passes:-0}
loops=$(grep -c '# Loop iteration' "$log" 2>/dev/null); loops=${loops:-0}
echo "O0,${TEST},${start},${end},${rc},${fails},${passes},${loops}" >> "$SUMMARY"
echo "[$end] RUN DONE rc=$rc fails=$fails passes=$passes loops=$loops" >> "$MONLOG"

kill "$MONPID" 2>/dev/null
if [ -f "$D/ABORT" ]; then
  echo "[$(date '+%F %T')] RUN ABORTED (watchdog)" >> "$MONLOG"
else
  echo "[$(date '+%F %T')] RUN COMPLETE" >> "$MONLOG"
fi
