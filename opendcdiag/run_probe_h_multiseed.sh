#!/bin/bash
# Run probe H LINES=512 multiple times, each 5m, auto-seed (no -s).
# Each invocation = 1 fresh random seed. Purpose: distinguish "true PASS" from
# "lucky-seed PASS" for the H positive control. If H FAILs in ANY run, the
# fixed-LCG "mask-confound" conclusion is overturned (H should fail = baseline).
set -u
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
BIN=./builddir/opendcdiag
N="${1:-5}"
for i in $(seq 1 "$N"); do
  out="probe_h_512_autoseed_run${i}.log"
  echo "=== H LINES=512 autoseed run $i/$N start $(date '+%H:%M:%S') ==="
  env PROBE_H_LINES=512 $BIN --enable=movbe_dump_probe_h --max-test-loop-count=0 -t 5m -o "/home/sdc/root/arm64-sdc-fuzzing/opendcdiag/$out"
  echo "  run $i: fails=$(grep -c 'result: fail' "$out") seed=$(grep -oE "seed: 'LCG:[0-9]+'" "$out" | head -1)"
done
echo "=== H multiseed complete $(date '+%H:%M:%S') ==="
