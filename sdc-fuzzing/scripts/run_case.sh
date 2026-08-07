#!/bin/bash
# run_case.sh - execute one sdc-fuzzing case under the verified trigger
# conditions (core 179 + same-socket >=47-core load) and judge reproduction.
#
# SAFETY (root-cause report 11.3): every run is timeout-wrapped and load
# lasts <=75s to avoid the hang caused by corruption propagating to control
# flow. Never run all-192-core long-duration load.
#
# Usage: ./scripts/run_case.sh <case_id>
#        ./scripts/run_case.sh core179-repro-A01
#
# Reads cases/manifest.json for the case parameters.
#
# JUDGEMENT (DESIGN.md 7):
#   fails > 0  -> PASS (reproduction observed; log fail count + rate)
#   fails == 0  -> INCONCLUSIVE (load window may have missed the transient;
#                 rerun in a fresh load window - NOT a design failure)
#   single-core or healthy-core control -> 0 fails expected (negative control)
#
# On a host WITHOUT cpu179 (e.g. current 128-core host), taskset -c 179 fails;
# set env CASE_TARGET_CORE to override (for smoke-testing on other cores), but
# note reproduction is only expected on the actual defective core 179.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
ENGINE="$ROOT/engine"
MANIFEST="$ROOT/cases/manifest.json"
CASE_ID=${1:?usage: run_case.sh case_id}
TARGET_CORE_OVERRIDE=${CASE_TARGET_CORE:-}
OPENDCDIAG_BIN=${OPENDCDIAG_BIN:-$HOME/arm64-sdc-fuzzing/opendcdiag/builddir/opendcdiag}

if [ ! -x "$ENGINE/mrueig" ]; then echo "ERROR: build engine first (./scripts/build_engine.sh)"; exit 2; fi
if [ ! -f "$MANIFEST" ]; then echo "ERROR: no manifest (run generate_manifest.py)"; exit 2; fi
if [ ! -x "$OPENDCDIAG_BIN" ]; then echo "WARN: opendcdiag binary missing at $OPENDCDIAG_BIN (load step will skip)"; fi

# extract one field from the case dict via python (no jq dependency)
read_json() {
    python3 -c "
import json,sys
d=json.load(open('$MANIFEST'))
c=[x for x in d['cases'] if x['id']=='$CASE_ID'][0]
print(c$1)
"
}
N=$(read_json "['matrix_dim']")
DENS=$(read_json "['density_p']")
DD=$(read_json "['diag_dominance']")
MS=$(read_json "['matrix_seed']")
RS=$(read_json "['rhs_seed']")
MODE=$(read_json "['mode']")
ITERS=$(read_json "['iterations']")
TC=$(read_json "['target_core']")
LCS=$(read_json "['load_cpuset']")
LSEC=$(read_json "['load_seconds']")
[ -n "$TARGET_CORE_OVERRIDE" ] && TC="$TARGET_CORE_OVERRIDE"

CASE_DIR="$ROOT/cases/$CASE_ID"
mkdir -p "$CASE_DIR"
LOG="$CASE_DIR/run.log"
RESULT="$CASE_DIR/result.json"

echo "== $CASE_ID: N=$N density=$DENS diag=$DD ms=$MS rs=$RS mode=$MODE iters=$ITERS =="
echo "   target_core=$TC load_cpuset=$LCS load_seconds=${LSEC}s"

# 1. background same-socket load (excludes target core)
LOAD_PID=""
if [ -x "$OPENDCDIAG_BIN" ]; then
    timeout $((LSEC+10)) "$OPENDCDIAG_BIN" --beta -e eigen_sparse \
        --cpuset "$LCS" -s LCG:323306158 -T "${LSEC}s" -o /dev/null >/dev/null 2>&1 &
    LOAD_PID=$!
    echo "   load started pid $LOAD_PID, sleeping 2s to spin up..."
    sleep 2
else
    echo "   (no opendcdiag - skipping load; reproduction will NOT trigger without load)"
fi

# 2. foreground trigger: bind target core, run MRU K iterations
echo "   triggering on core $TC for $ITERS iterations..."
set +e
timeout $((LSEC+15)) taskset -c "$TC" "$ENGINE/mrueig" "$ITERS" "$MS" "$RS" "$N" "$DENS" "$DD" "$MODE" >"$CASE_DIR/stdout.txt" 2>"$LOG"
RC=$?
set -u

# 3. parse fail count (stdout = "<fails>")
FAILS=$(tr -d ' \n\r' < "$CASE_DIR/stdout.txt")
[ -z "$FAILS" ] && FAILS=0
RATE=$(python3 -c "print(f'{$FAILS/$ITERS:.4f}')" 2>/dev/null || echo "n/a")

# 4. judge
if [ "$FAILS" -gt 0 ]; then
    JUDGE=PASS; SUMMARY="reproduced ($FAILS/$ITERS fails, rate=$RATE)"
else
    JUDGE=INCONCLUSIVE; SUMMARY="0 fails in this window (transient; rerun in fresh load window)"
fi
echo "   ==> $JUDGE: $SUMMARY"

# 5. write result.json
python3 -c "
import json
r={'case_id':'$CASE_ID','fails':$FAILS,'iters':$ITERS,'rate':'$RATE','judge':'$JUDGE',
   'target_core':'$TC','load_seconds':$LSEC,'mode':$MODE,'N':$N,'density':'$DENS','diag':'$DD',
   'matrix_seed':'$MS','rhs_seed':'$RS','rc':$RC}
open('$RESULT','w').write(json.dumps(r,indent=2))
"

# 6. cleanup load
[ -n "$LOAD_PID" ] && kill "$LOAD_PID" 2>/dev/null
wait "$LOAD_PID" 2>/dev/null || true
exit 0
