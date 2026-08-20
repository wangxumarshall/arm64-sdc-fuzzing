#!/bin/bash
# run_all.sh - execute all 100 sdc-fuzzing cases sequentially and aggregate.
#
# Each case: same-socket load + bind core 179 + MRU run + CRC judge.
# ~60-75s per case -> ~100-125 min for 100 cases. SAFETY: timeout-wrapped
# per case; pause between cases to let the machine settle (avoid cumulative
# hang risk, root-cause report 11.3).
#
# Usage: ./scripts/run_all.sh [--only A,B,D] [--target-core 179]
#   --only        family letter prefixes to run (A,B,C,D,E,F,G), default all
#   --target-core override target core (for hosts without cpu179)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
MANIFEST="$ROOT/cases/manifest.json"
ONLY=""
TC_OVERRIDE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --only) ONLY="$2"; shift 2;;
        --target-core) TC_OVERRIDE="$2"; shift 2;;
        *) echo "unknown arg: $1"; exit 2;;
    esac
done

if [ ! -f "$MANIFEST" ]; then echo "ERROR: run generate_manifest.py first"; exit 2; fi

# list of case ids, optionally filtered by family letter prefix
IDS=$(python3 -c "
import json
d=json.load(open('$MANIFEST'))
ids=[c['id'] for c in d['cases']]
only='$ONLY'.replace(' ','').split(',') if '$ONLY' else []
if only:
    # family letter is the char after 'core179-repro-'
    ids=[i for i in ids if i.split('-')[-1][0] in only]
print('\n'.join(ids))
")

echo "sdc-fuzzing run_all: $(echo "$IDS" | grep -c .) cases"
PASS=0; INCON=0; FAIL=0; N=0
for cid in $IDS; do
    N=$((N+1))
    echo "========== [$N] $cid =========="
    if [ -n "$TC_OVERRIDE" ]; then
        CASE_TARGET_CORE="$TC_OVERRIDE" "$HERE/run_case.sh" "$cid"
    else
        "$HERE/run_case.sh" "$cid"
    fi
    JUDGE=$(python3 -c "
import json,os
p=os.path.join('$ROOT','cases','$cid','result.json')
print(json.load(open(p))['judge']) if os.path.exists(p) else print('ERROR')
" 2>/dev/null)
    case "$JUDGE" in
        PASS) PASS=$((PASS+1));;
        INCONCLUSIVE) INCON=$((INCON+1));;
        *) FAIL=$((FAIL+1));;
    esac
    echo "   tally: PASS=$PASS INCON=$INCON FAIL=$FAIL / $N"
    sleep 5
done

echo ""
echo "================ sdc-fuzzing SUMMARY ================"
echo "  total:     $N"
echo "  PASS:      $PASS   (reproduced core-179 SDC)"
echo "  INCON:     $INCON  (0 fails in window - rerun to converge)"
echo "  FAIL:      $FAIL   (run errors)"
echo "====================================================="
echo "Run ./scripts/analyze_results.py for per-family breakdown"
