#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT/gem5"

echo "Starting gem5 ARM64 compilation..."
echo "This will take 1-2 hours. Progress will be logged."
echo ""

# Auto-confirm git hooks installation by pressing enter
echo "" | /opt/homebrew/bin/scons -j 8 build/ARM/gem5.opt 2>&1 | tee /tmp/gem5_build.log

echo ""
echo "Build complete. Check /tmp/gem5_build.log for details."
