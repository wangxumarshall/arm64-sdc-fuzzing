#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCPAT_DIR="$REPO_ROOT/mcpat"
NUM_JOBS="${1:-$(sysctl -n hw.ncpu)}"

echo "=========================================="
echo "McPAT Build Script"
echo "=========================================="
echo "Source: $MCPAT_DIR"
echo "Jobs: $NUM_JOBS"
echo ""

cd "$MCPAT_DIR"
mkdir -p obj_opt
make -j "$NUM_JOBS" opt NTHREADS="$NUM_JOBS"

if [ ! -x "$MCPAT_DIR/mcpat" ]; then
    echo "ERROR: Expected McPAT binary at $MCPAT_DIR/mcpat"
    exit 1
fi

echo ""
echo "Build complete."
echo "Binary: $MCPAT_DIR/mcpat"
