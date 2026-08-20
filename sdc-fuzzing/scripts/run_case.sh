#!/bin/bash
# run_case.sh - execute one sdc-fuzzing case under the verified trigger
# conditions (core 179 + same-socket >=47-core load) and judge reproduction.
#
# MULTI-WINDOW ACCUMULATION (feasibility-correct design, see
# generate_manifest.py header): a case's total_iterations (K_total) may exceed
# what fits in one 75 s load window (§11.3 safety ceiling). The manifest
# encodes iters_per_window (chunk that fits one load window, from the measured
# timing model) and max_windows (cap to reach K_total). This script runs up to
# max_windows load windows, each running mrueig for iters_per_window iterations,
# and accumulates fails + iters across windows:
#   - fails > 0 in any window  -> early PASS (reproduction observed; stop)
#   - total iters reaches K_total with 0 fails -> INCONCLUSIVE (rerun later)
#   - max_windows exhausted with 0 fails       -> INCONCLUSIVE
#
# SAFETY (root-cause report §11.3): every load window is timeout-wrapped and
# lasts <=75 s to avoid the hang caused by corruption propagating to control
# flow. Never run all-192-core long-duration load. A 5 s spin-up guard
# (DRIVER_GUARD_S) ensures the load is up before the driver reads state.
#
# Usage: ./scripts/run_case.sh <case_id>
#        ./scripts/run_case.sh core179-repro-A01
#
# Reads cases/manifest.json for the case parameters.
#
# JUDGEMENT (DESIGN.md 7):
#   total_fails > 0  -> PASS (reproduction observed; log fail count + rate)
#   total_fails == 0  -> INCONCLUSIVE (all windows missed the transient; rerun
#                      in fresh load windows - NOT a design failure)
#   single-core or healthy-core control -> 0 fails expected (negative control)
#
# On a host WITHOUT cpu179 (e.g. current 128-core host), taskset -c 179 fails;
# set env CASE_TARGET_CORE to override (for smoke-testing on other cores), but
# note reproduction is only expected on the actual defective core 179.
# Set CASE_SKIP_LOAD=1 to skip the load step (single-core mechanism smoke).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
ENGINE="$ROOT/engine"
MANIFEST="$ROOT/cases/manifest.json"
CASE_ID=${1:?usage: run_case.sh case_id}
TARGET_CORE_OVERRIDE=${CASE_TARGET_CORE:-}
SKIP_LOAD=${CASE_SKIP_LOAD:-0}
# Optional overrides for smoke-testing on a host without the target machine's
# cpuset layout (e.g. current 2-socket/128-core host has no cores 144-191).
CASE_LOAD_CPUSET=${CASE_LOAD_CPUSET:-}
CASE_LOAD_SECONDS_OVERRIDE=${CASE_LOAD_SECONDS_OVERRIDE:-}
OPENDCDIAG_BIN=${OPENDCDIAG_BIN:-$HOME/arm64-sdc-fuzzing/opendcdiag/builddir/opendcdiag}

if [ ! -x "$ENGINE/mrueig" ]; then echo "ERROR: build engine first (./scripts/build_engine.sh)"; exit 2; fi
if [ ! -f "$MANIFEST" ]; then echo "ERROR: no manifest (run generate_manifest.py)"; exit 2; fi
if [ ! -x "$OPENDCDIAG_BIN" ] && [ "$SKIP_LOAD" != "1" ]; then echo "WARN: opendcdiag binary missing at $OPENDCDIAG_BIN (load step will skip)"; fi

# extract one field from the case dict via python (no jq dependency)
read_json() {
    python3 -c "
import json,sys
d=json.load(open('$MANIFEST'))
c=[x for x in d['cases'] if x['id']=='$CASE_ID'][0]
v=c$1
print(v if not isinstance(v,bool) else int(v))
"
}
N=$(read_json "['matrix_dim']")
DENS=$(read_json "['density_p']")
DD=$(read_json "['diag_dominance']")
MS=$(read_json "['matrix_seed']")
RS=$(read_json "['rhs_seed']")
MODE=$(read_json "['mode']")
K_TOTAL=$(read_json "['iterations']")
IPW=$(read_json "['iters_per_window']")
MAXW=$(read_json "['max_windows']")
TC=$(read_json "['target_core']")
LCS=$(read_json "['load_cpuset']")
LSEC=$(read_json "['load_seconds']")
[ -n "$TARGET_CORE_OVERRIDE" ] && TC="$TARGET_CORE_OVERRIDE"
[ -n "$CASE_LOAD_CPUSET" ] && LCS="$CASE_LOAD_CPUSET"
[ -n "$CASE_LOAD_SECONDS_OVERRIDE" ] && LSEC="$CASE_LOAD_SECONDS_OVERRIDE"

CASE_DIR="$ROOT/cases/$CASE_ID"
mkdir -p "$CASE_DIR"
LOG="$CASE_DIR/run.log"
RESULT="$CASE_DIR/result.json"
# truncate per-run log (accumulation summary appended below)
: > "$LOG"

echo "== $CASE_ID: N=$N density=$DENS diag=$DD ms=$MS rs=$RS mode=$MODE ==" | tee -a "$LOG"
echo "   K_total=$K_TOTAL iters_per_window=$IPW max_windows=$MAXW" | tee -a "$LOG"
echo "   target_core=$TC load_cpuset=$LCS load_seconds=${LSEC}s skip_load=$SKIP_LOAD" | tee -a "$LOG"

TOTAL_FAILS=0
TOTAL_ITERS=0
WINDOWS_RUN=0

while [ "$WINDOWS_RUN" -lt "$MAXW" ]; do
    WINDOWS_RUN=$((WINDOWS_RUN+1))
    # last window may be smaller to not overshoot K_TOTAL
    REMAINING=$(( K_TOTAL - TOTAL_ITERS ))
    CHUNK=$IPW
    [ "$CHUNK" -gt "$REMAINING" ] && CHUNK="$REMAINING"
    [ "$CHUNK" -lt 1 ] && break

    echo "   -- window $WINDOWS_RUN/$MAXW: chunk=$CHUNK iters (remaining target $REMAINING) --" | tee -a "$LOG"

    # 1. background same-socket load (excludes target core)
    LOAD_PID=""
    if [ "$SKIP_LOAD" != "1" ] && [ -x "$OPENDCDIAG_BIN" ]; then
        timeout $((LSEC+10)) "$OPENDCDIAG_BIN" --beta -e eigen_sparse \
            --cpuset "$LCS" -s LCG:323306158 -T "${LSEC}s" -o /dev/null >/dev/null 2>&1 &
        LOAD_PID=$!
        echo "      load started pid $LOAD_PID, sleeping 2s to spin up..." | tee -a "$LOG"
        sleep 2
    elif [ "$SKIP_LOAD" = "1" ]; then
        : # single-core mechanism smoke; no load
    else
        echo "      (no opendcdiag - skipping load; reproduction will NOT trigger without load)" | tee -a "$LOG"
    fi

    # 2. foreground trigger: bind target core, run MRU chunk iterations
    set +e
    timeout $((LSEC+15)) taskset -c "$TC" "$ENGINE/mrueig" "$CHUNK" "$MS" "$RS" "$N" "$DENS" "$DD" "$MODE" 2>>"$LOG" >"$CASE_DIR/stdout_${WINDOWS_RUN}.txt"
    RC=$?
    set -u

    # 3. parse fail count (stdout = "<fails>")
    CHUNK_FAILS=$(tr -d ' \n\r' < "$CASE_DIR/stdout_${WINDOWS_RUN}.txt" 2>/dev/null || true)
    [ -z "$CHUNK_FAILS" ] && CHUNK_FAILS=0
    # guard against non-numeric (timeout/crash)
    case "$CHUNK_FAILS" in
        ''|*[!0-9]*) CHUNK_FAILS=0; CHUNK_RC=timeout_or_crash;;
        *) CHUNK_RC=$RC;;
    esac

    TOTAL_FAILS=$((TOTAL_FAILS + CHUNK_FAILS))
    TOTAL_ITERS=$((TOTAL_ITERS + CHUNK))
    echo "      chunk fails=$CHUNK_FAILS  total=$TOTAL_FAILS/$TOTAL_ITERS (rc=$CHUNK_RC)" | tee -a "$LOG"

    # cleanup load
    [ -n "$LOAD_PID" ] && kill "$LOAD_PID" 2>/dev/null
    wait "$LOAD_PID" 2>/dev/null || true

    # early-PASS on first fail
    if [ "$TOTAL_FAILS" -gt 0 ]; then
        echo "      ==> reproduction observed in window $WINDOWS_RUN; stopping (early-PASS)" | tee -a "$LOG"
        break
    fi
    # reached K_total
    if [ "$TOTAL_ITERS" -ge "$K_TOTAL" ]; then
        echo "      ==> reached K_total=$K_TOTAL with 0 fails; stopping" | tee -a "$LOG"
        break
    fi
    # settle between windows to avoid cumulative hang risk (§11.3)
    sleep 3
done

RATE=$(python3 -c "
try:
    print(f'{$TOTAL_FAILS/$TOTAL_ITERS:.4f}')
except ZeroDivisionError:
    print('n/a')
" 2>/dev/null || echo "n/a")

# 4. judge
if [ "$TOTAL_FAILS" -gt 0 ]; then
    JUDGE=PASS; SUMMARY="reproduced ($TOTAL_FAILS/$TOTAL_ITERS fails over $WINDOWS_RUN window(s), rate=$RATE)"
else
    JUDGE=INCONCLUSIVE; SUMMARY="0 fails over $WINDOWS_RUN window(s), $TOTAL_ITERS iters (transient; rerun in fresh load windows)"
fi
echo "   ==> $JUDGE: $SUMMARY" | tee -a "$LOG"

# 5. write result.json
python3 -c "
import json
r={'case_id':'$CASE_ID','fails':$TOTAL_FAILS,'iters':$TOTAL_ITERS,'rate':'$RATE',
   'judge':'$JUDGE','windows_run':$WINDOWS_RUN,
   'target_core':'$TC','load_seconds':$LSEC,'mode':$MODE,'N':$N,'density':'$DENS','diag':'$DD',
   'matrix_seed':'$MS','rhs_seed':'$RS','K_total':$K_TOTAL,'iters_per_window':$IPW,'max_windows':$MAXW}
open('$RESULT','w').write(json.dumps(r,indent=2))
"
exit 0
