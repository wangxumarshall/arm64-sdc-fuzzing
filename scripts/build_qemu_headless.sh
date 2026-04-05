#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QEMU_DIR="$REPO_ROOT/qemu"
PYTHON_BIN="${PYTHON_BIN:-/Users/wangxu/anaconda3/bin/python3}"
COMMON_PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/wangxu/anaconda3/bin"

cd "$QEMU_DIR"

echo "=========================================="
echo "QEMU Headless ARM64 System Build"
echo "=========================================="
echo "Source: $QEMU_DIR"
echo "Python: $PYTHON_BIN"
echo ""

rm -rf build GNUmakefile

env \
    -u CC -u CXX -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS \
    CC=cc \
    CXX=c++ \
    OBJC=/usr/bin/clang \
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
    make -C build -j8

echo ""
echo "Build complete."
echo "Expected binary: $QEMU_DIR/build/qemu-system-aarch64"
echo "Expected binary: $QEMU_DIR/build/qemu-aarch64"
