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
GEM5_VARIANT="${GEM5_VARIANT:-auto}"
SCONS_EXTRA_ARGS=("--limit-ld-memory-usage")

if command -v ld.gold >/dev/null 2>&1; then
    SCONS_EXTRA_ARGS+=("--linker=gold")
fi

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
echo "Variant: $GEM5_VARIANT"
echo ""

cd "$GEM5_DIR"

build_variant() {
    local variant="$1"
    local jobs="$2"

    echo "Building gem5.${variant} with -j${jobs}"
    "$PYTHON_BIN" -m SCons "${SCONS_EXTRA_ARGS[@]}" -j "$jobs" "build/ARM/gem5.${variant}"
}

BUILT_VARIANT=""

if [ "$GEM5_VARIANT" = "auto" ]; then
    if build_variant opt "$NUM_JOBS"; then
        BUILT_VARIANT="opt"
    else
        echo ""
        echo "gem5.opt build failed. Falling back to gem5.debug with -j1."
        echo ""
        if build_variant debug 1; then
            BUILT_VARIANT="debug"
        else
            echo "ERROR: Failed to build gem5.opt and gem5.debug."
            exit 1
        fi
    fi
else
    build_variant "$GEM5_VARIANT" "$NUM_JOBS"
    BUILT_VARIANT="$GEM5_VARIANT"
fi

BUILT_BINARY="$GEM5_DIR/build/ARM/gem5.${BUILT_VARIANT}"

if [ ! -x "$BUILT_BINARY" ]; then
    echo "ERROR: Expected gem5 binary at $BUILT_BINARY"
    exit 1
fi

echo ""
echo "Build complete."
echo "Binary: $BUILT_BINARY"
