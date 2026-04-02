#!/bin/bash
set -e

echo "=========================================="
echo "gem5 ARM64 Build Script for macOS"
echo "=========================================="

GEM5_DIR="$(cd "$(dirname "$0")/../gem5" && pwd)"
BUILD_TARGET="${1:-ARM}"
BUILD_TYPE="${2:-opt}"
NUM_JOBS="${3:-$(sysctl -n hw.ncpu)}"

echo "GEM5_DIR: $GEM5_DIR"
echo "BUILD_TARGET: $BUILD_TARGET"
echo "BUILD_TYPE: $BUILD_TYPE"
echo "NUM_JOBS: $NUM_JOBS"
echo ""

echo "=== Step 1: Checking dependencies ==="

check_and_install_brew() {
    local pkg=$1
    if ! brew list "$pkg" &>/dev/null; then
        echo "Installing $pkg via Homebrew..."
        brew install "$pkg"
    else
        echo "$pkg is already installed."
    fi
}

check_and_install_pip() {
    local pkg=$1
    if ! pip3 show "$pkg" &>/dev/null; then
        echo "Installing $pkg via pip3..."
        pip3 install "$pkg"
    else
        echo "$pkg is already installed."
    fi
}

if command -v brew &>/dev/null; then
    check_and_install_brew "scons"
    check_and_install_brew "swig"
    check_and_install_brew "protobuf"
else
    echo "Homebrew not found. Please install Homebrew first:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

check_and_install_pip "six"
check_and_install_pip "protobuf"

echo ""
echo "=== Step 2: Verifying gem5 source ==="
if [ ! -f "$GEM5_DIR/SConstruct" ]; then
    echo "ERROR: SConstruct not found in $GEM5_DIR"
    exit 1
fi
echo "SConstruct found."

if [ ! -f "$GEM5_DIR/build_opts/$BUILD_TARGET" ]; then
    echo "ERROR: Build target $BUILD_TARGET not found in build_opts/"
    exit 1
fi
echo "Build target $BUILD_TARGET configuration found."

echo ""
echo "=== Step 3: Building gem5 ==="
echo "This may take 1-2 hours depending on your system..."
echo ""

cd "$GEM5_DIR"

BUILD_DIR="build/$BUILD_TARGET"
echo "Build directory: $BUILD_DIR"

scons -j "$NUM_JOBS" "$BUILD_DIR/gem5.$BUILD_TYPE" || {
    echo ""
    echo "=== Build failed! ==="
    echo "Common issues:"
    echo "  1. Missing dependencies - run: brew install scons swig protobuf"
    echo "  2. Python version mismatch - gem5 requires Python 3.8+"
    echo "  3. Memory issues - try reducing NUM_JOBS"
    echo ""
    echo "For verbose output, run:"
    echo "  scons -j $NUM_JOBS $BUILD_DIR/gem5.$BUILD_TYPE --verbose"
    exit 1
}

echo ""
echo "=== Step 4: Verifying build ==="
if [ -f "$BUILD_DIR/gem5.$BUILD_TYPE" ]; then
    echo "SUCCESS: gem5.$BUILD_TYPE built successfully!"
    echo ""
    echo "Binary location: $GEM5_DIR/$BUILD_DIR/gem5.$BUILD_TYPE"
    echo ""
    echo "To test the build:"
    echo "  $GEM5_DIR/$BUILD_DIR/gem5.$BUILD_TYPE --help"
else
    echo "ERROR: Build completed but binary not found!"
    exit 1
fi

echo ""
echo "=========================================="
echo "gem5 ARM64 Build Complete!"
echo "=========================================="
