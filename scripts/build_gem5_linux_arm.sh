#!/bin/bash
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: build_gem5_linux_arm.sh must run on Linux."
    exit 1
fi

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: build_gem5_linux_arm.sh is intended for Linux ARM hosts."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEM5_DIR="$REPO_ROOT/gem5"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
NUM_JOBS="${NUM_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 8)}"

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 is required to build gem5."
    exit 1
fi

if [ ! -f "$GEM5_DIR/SConstruct" ]; then
    echo "ERROR: gem5 source tree not found at $GEM5_DIR"
    exit 1
fi

echo "=========================================="
echo "gem5 Linux ARM Build"
echo "=========================================="
echo "Source: $GEM5_DIR"
echo "Python: $PYTHON_BIN"
echo "Jobs: $NUM_JOBS"
echo ""

cd "$GEM5_DIR"
"$PYTHON_BIN" -m SCons -j "$NUM_JOBS" build/ARM/gem5.opt

if [ ! -x "$GEM5_DIR/build/ARM/gem5.opt" ]; then
    echo "ERROR: Expected gem5 binary at $GEM5_DIR/build/ARM/gem5.opt"
    exit 1
fi

echo ""
echo "Build complete."
echo "Binary: $GEM5_DIR/build/ARM/gem5.opt"
