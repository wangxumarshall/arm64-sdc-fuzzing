#!/bin/bash
# build_engine.sh - build the shared sdc-fuzzing trigger engine.
#
# Produces engine/mrueig: a SINGLE parameterized binary shared by all 100
# cases (DESIGN.md section 6). The Eigen machine code (eigen_cabidrv.o) is
# compiled ONCE and is constant across all cases (F1: trigger signature
# invariance). ldd mrueig must show only libc + libm (libc-only, F8).
#
# Run:   ./scripts/build_engine.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
ENGINE="$ROOT/engine"
EIG=${EIG:-$HOME/arm64-sdc-fuzzing/opendcdiag/third-part}

if [ ! -d "$EIG/Eigen" ]; then
    echo "ERROR: Eigen 5.0 not found at $EIG/Eigen"
    echo "  Run: cd $HOME/arm64-sdc-fuzzing/opendcdiag && git submodule update --init third-part"
    exit 1
fi

echo "== 1. compile Eigen machine-code object C-ABI wrapper, -fno-exceptions -fno-rtti =="
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I"$EIG" \
    -fno-exceptions -fno-rtti -fPIC -c \
    "$ENGINE/eigen_cabidrv.cpp" -o "$ENGINE/eigen_cabidrv.o"

echo "== 2. link parameterized C driver + Eigen object -> libc-only binary =="
gcc -O2 -march=armv8.1-a+crc+crypto -std=gnu17 -ffp-contract=fast \
    "$ENGINE/mru_driver.c" "$ENGINE/eigen_cabidrv.o" -o "$ENGINE/mrueig" -lm

echo "== built: $ENGINE/mrueig =="
echo "ldd:"; ldd "$ENGINE/mrueig"
echo ""
echo "smoke single-core cpu 0, expect 0 fails - single-core never triggers:"
timeout 60 taskset -c 0 "$ENGINE/mrueig" 200 12345 99999 256 0.10 2.0 1 2>&1 | tail -4 || true
