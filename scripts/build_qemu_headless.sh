#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QEMU_DIR="$REPO_ROOT/qemu"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
NUM_JOBS="${NUM_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 8)}"
COMMON_PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
USER_LOCAL_BIN="${HOME}/.local/bin"

if [ -d "$USER_LOCAL_BIN" ]; then
    COMMON_PATH="$USER_LOCAL_BIN:$COMMON_PATH"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 is required to configure QEMU."
    exit 1
fi

cd "$QEMU_DIR"

echo "=========================================="
echo "QEMU Headless ARM64 System Build"
echo "=========================================="
echo "Source: $QEMU_DIR"
echo "Python: $PYTHON_BIN"
echo "PATH: $COMMON_PATH"
echo ""

rm -rf build GNUmakefile

env \
    -u CC -u CXX -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS \
    CC=cc \
    CXX=c++ \
    AR=ar \
    NM=nm \
    RANLIB=ranlib \
    PATH="$COMMON_PATH" \
    ./configure \
        --python="$PYTHON_BIN" \
        --target-list=aarch64-softmmu,aarch64-linux-user \
        --disable-cocoa \
        --disable-coreaudio \
        --disable-sdl \
        --disable-gtk \
        --disable-curses \
        --disable-docs \
        --disable-plugins

echo ""
echo "Configure complete. Starting build..."
echo ""

env \
    AR=ar \
    NM=nm \
    RANLIB=ranlib \
    PATH="$COMMON_PATH" \
    make -C build -j"$NUM_JOBS"

TARGET_DIRS="$(grep '^TARGET_DIRS=' build/config-host.mak 2>/dev/null | cut -d= -f2- || true)"
USER_BINARY="$QEMU_DIR/build/qemu-aarch64"
SYSTEM_BINARY="$QEMU_DIR/build/qemu-system-aarch64"
SYSTEM_BINARY_UNSIGNED="$QEMU_DIR/build/qemu-system-aarch64-unsigned"

if [ -z "$TARGET_DIRS" ] || [[ "$TARGET_DIRS" != *"aarch64-linux-user"* ]]; then
    echo "ERROR: QEMU was not configured with the aarch64-linux-user target."
    echo "TARGET_DIRS=$TARGET_DIRS"
    exit 1
fi

if [ ! -x "$USER_BINARY" ]; then
    echo "ERROR: Expected user-mode binary at $USER_BINARY"
    exit 1
fi

if [ ! -x "$SYSTEM_BINARY" ] && [ ! -x "$SYSTEM_BINARY_UNSIGNED" ]; then
    echo "ERROR: Expected system-mode binary at $SYSTEM_BINARY or $SYSTEM_BINARY_UNSIGNED"
    exit 1
fi

echo ""
echo "Build complete."
echo "User binary: $USER_BINARY"
if [ -x "$SYSTEM_BINARY" ]; then
    echo "System binary: $SYSTEM_BINARY"
else
    echo "System binary: $SYSTEM_BINARY_UNSIGNED"
fi
