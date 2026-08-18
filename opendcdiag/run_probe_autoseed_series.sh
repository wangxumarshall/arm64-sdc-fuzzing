#!/bin/bash
# Run probes E, G1, G2, H(LINES=512) sequentially, each 5 min, NO -s flag
# (opendcdiag auto-seeds per thread -> diverse input patterns).
# Methodology fix: prior fixed -s LCG:1711090087 only sampled ONE input pattern;
# SDC is seed-sensitive/intermittent, so a fixed seed can mislabel a probe as
# "kills the defect" when it merely didn't hit the trigger pattern under that seed.
set -u
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
BIN=./builddir/opendcdiag
COMMON="--max-test-loop-count=0 -t 5m"

run_one () {
  local enable="$1"; local out="$2"; shift 2
  echo "=== $enable autoseed 5m start: $(date '+%H:%M:%S') ==="
  env "$@" $BIN --enable="$enable" $COMMON -o "/home/sdc/root/arm64-sdc-fuzzing/opendcdiag/$out"
  echo "=== $enable done: $(date '+%H:%M:%S') | fails=$(grep -c 'result: fail' "$out") ==="
}

run_one movbe_dump_probe_e  probe_e_autoseed.log
run_one movbe_dump_probe_g1 probe_g1_autoseed.log
run_one movbe_dump_probe_g2 probe_g2_autoseed.log
run_one movbe_dump_probe_h  probe_h_512_autoseed.log  PROBE_H_LINES=512

echo "=== SERIES COMPLETE: $(date '+%H:%M:%S') ==="
for f in probe_e_autoseed.log probe_g1_autoseed.log probe_g2_autoseed.log probe_h_512_autoseed.log; do
  echo "$f: fails=$(grep -c 'result: fail' "$f" 2>/dev/null) | seeds: $(grep -oE "seed: 'LCG:[0-9]+'" "$f" 2>/dev/null | sort -u | tr '\n' ' ')"
done
