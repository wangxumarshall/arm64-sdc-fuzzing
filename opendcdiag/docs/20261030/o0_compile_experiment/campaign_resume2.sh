#!/bin/bash
# CORE179 -O0 vs -O3 campaign CONTINUATION 2 (2026-10-30, ~03:25)
# Context: original campaign + resume1 aborted 03:00:32 by thermal watchdog
# (CPU2 97C > 95C) 2min into run 4 (O3 sub). All 12 fans verified healthy
# at 100% (19.5-20.2k RPM); temps recovered to baseline within 10min.
# Valid data banked: run1 O3-rowmajor 400f; run2 O0-rowmajor 0f (exit:pass,
# 1516 loops @ 1186.71ms avg); run3 O0-sub 0f. Run4 truncated (log kept as
# .truncated-0300, summary rc=143 row excluded from analysis).
# Hardening vs resume1: per-run thermal abort (STOPRUN, not whole-campaign
# ABORT); pre-run CPU2<=70C gate (max 10min wait); thermal-aborted runs get
# exactly one retry then are recorded thermal-skip; O3-sub redo moved LAST
# so a possible steady-state >95C cannot cost the six never-started runs.
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/o0_compile_experiment
RUNS=$D/runs
SUMMARY=$D/summary.csv
MONLOG=$D/monitor.log
O3BIN=$R/builddir/opendcdiag
O0BIN=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag-O0/builddir/opendcdiag
STOP=$D/STOPRUN

if pgrep -x opendcdiag >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] RESUME2 ABORT: an opendcdiag process is already running" >> "$MONLOG"; exit 1
fi

cpu2() { timeout 12 sudo ipmitool sensor reading CPU2_TEMP 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)?[[:space:]]*$' | tr -d '[:space:]'; }

wait_cool() {
  local waited=0 t
  while [ "$waited" -lt 600 ]; do
    t=$(cpu2); [ -n "$t" ] || t=999
    if [ "${t%%.*}" -le 70 ]; then return 0; fi
    sleep 30; waited=$((waited+30))
  done
  echo "[$(date '+%F %T')] COOLDOWN TIMEOUT after 10min, proceeding" >> "$MONLOG"
}

# --- continuous monitor + watchdog (95C, per-run STOPRUN semantics) ---
(
  while true; do
    ts=$(date '+%F %T')
    t=$(timeout 12 sudo ipmitool sensor reading CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP 2>/dev/null | grep -oE 'CPU[0-9]_TEMP[ |]+[0-9]+' | tr -s ' ' | tr '\n' ';')
    echo "$ts | $t" >> "$MONLOG"
    hot=$(echo "$t" | grep -oE '[0-9]+' | sort -rn | head -1)
    if [ -n "$hot" ] && [ "$hot" -gt 95 ]; then
      echo "$ts WATCHDOG: max CPU temp ${hot}C > 95C -> kill current run, continue campaign" >> "$MONLOG"
      touch "$STOP"
      pkill -x opendcdiag 2>/dev/null
    fi
    sleep 60
  done
) &
MONPID=$!
taskset -pc 8 "$MONPID" >/dev/null 2>&1
echo "[$(date '+%F %T')] RESUME2 START (per-run thermal abort; CPU2 gate 70C; O3-sub redo last)" >> "$MONLOG"

run_one() {
    arm=$1; test=$2; bin=$3
    wait_cool
    rm -f "$STOP"
    log=$RUNS/${arm}_${test}.log
    start=$(date '+%F %T')
    taskset -c 24-191 "$bin" -e "$test" -T 30m -n 168 --ignore-os-error --ignore-timeout -o "$log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    if [ -f "$STOP" ]; then rc=thermal; fi
    fails=$(grep -c 'result: fail' "$log" 2>/dev/null); fails=${fails:-0}
    passes=$(grep -c 'result: pass' "$log" 2>/dev/null); passes=${passes:-0}
    loops=$(grep -c '# Loop iteration' "$log" 2>/dev/null); loops=${loops:-0}
    echo "${arm},${test},${start},${end},${rc},${fails},${passes},${loops}" >> "$SUMMARY"
    echo "[$end] RUN DONE ${arm} ${test} rc=${rc} fails=$fails passes=$passes loops=$loops" >> "$MONLOG"
    [ "$rc" = thermal ] && return 1
    return 0
}

# --- pass 1: six never-started runs (original order), then O3-sub redo last ---
RETRY=""
run_one O3 mrn_reloaded_2src_alu    "$O3BIN" || RETRY="$RETRY O3:mrn_reloaded_2src_alu"
run_one O0 mrn_reloaded_2src_alu    "$O0BIN" || RETRY="$RETRY O0:mrn_reloaded_2src_alu"
run_one O0 neon_rot_ldr_at_top_str3 "$O0BIN" || RETRY="$RETRY O0:neon_rot_ldr_at_top_str3"
run_one O3 neon_rot_ldr_at_top_str3 "$O3BIN" || RETRY="$RETRY O3:neon_rot_ldr_at_top_str3"
run_one O3 movbe                    "$O3BIN" || RETRY="$RETRY O3:movbe"
run_one O0 movbe                    "$O0BIN" || RETRY="$RETRY O0:movbe"
run_one O3 neon_rot_ldr_at_top_sub  "$O3BIN" || RETRY="$RETRY O3:neon_rot_ldr_at_top_sub"

# --- pass 2: one retry round for thermal-aborted runs ---
for entry in $RETRY; do
  arm=${entry%%:*}; test=${entry##*:}
  bin=$O3BIN; [ "$arm" = O0 ] && bin=$O0BIN
  if ! run_one "$arm" "$test" "$bin"; then
    echo "${arm},${test},,,thermal-skip,,," >> "$SUMMARY"
    echo "[$(date '+%F %T')] RUN SKIP ${arm} ${test} (thermal x2)" >> "$MONLOG"
  fi
done

kill "$MONPID" 2>/dev/null
rm -f "$STOP"
echo "[$(date '+%F %T')] CAMPAIGN COMPLETE (resume2)" >> "$MONLOG"
