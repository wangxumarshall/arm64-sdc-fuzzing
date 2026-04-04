#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/Users/wangxu/anaconda3/bin/python3}"
PYTHON_CONFIG_BIN="${PYTHON_CONFIG_BIN:-/Users/wangxu/anaconda3/bin/python3-config}"
PYTHON_LIBDIR="${PYTHON_LIBDIR:-/Users/wangxu/anaconda3/lib}"
PYTHON_CONFIG_DIR="${PYTHON_CONFIG_DIR:-/Users/wangxu/anaconda3/lib/python3.12/config-3.12-darwin}"

cd "$REPO_ROOT/gem5"

echo "Starting gem5 ARM64 compilation..."
echo "This will take 1-2 hours. Progress will be logged."
echo ""

# Ensure python3-config's configured library directory can actually resolve
# libpython at gem5's embed-check stage on macOS/anaconda hosts.
if [ -d "$PYTHON_CONFIG_DIR" ] && [ -f "$PYTHON_LIBDIR/libpython3.12.dylib" ]; then
    ln -sf ../../libpython3.12.dylib "$PYTHON_CONFIG_DIR/libpython3.12.dylib"
fi

env \
    -u CC -u CXX -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS \
    CC=cc \
    CXX=c++ \
    PYTHON_CONFIG="$PYTHON_CONFIG_BIN" \
    DYLD_LIBRARY_PATH="$PYTHON_LIBDIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" \
    GEM5PY_LINKFLAGS_EXTRA="-L$PYTHON_LIBDIR -Wl,-rpath,$PYTHON_LIBDIR" \
    LINKFLAGS_EXTRA="-L$PYTHON_LIBDIR -Wl,-rpath,$PYTHON_LIBDIR" \
    "$PYTHON_BIN" -m SCons -j 8 build/ARM/gem5.opt 2>&1 | tee /tmp/gem5_build.log

echo ""
echo "Build complete. Check /tmp/gem5_build.log for details."
