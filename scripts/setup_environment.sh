#!/bin/bash
set -e

echo "=========================================="
echo "ARM64 SDC Fuzzing Environment Setup"
echo "=========================================="
echo ""

PLATFORM=$(uname -s)
if [ "$PLATFORM" != "Darwin" ]; then
    echo "This script is designed for macOS. For Linux, use apt-get or yum."
    echo "Example for Ubuntu/Debian:"
    echo "  sudo apt-get install scons swig protobuf-compiler qemu-user gcc-aarch64-linux-gnu"
    exit 1
fi

echo "=== Step 1: Check Homebrew ==="
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew is installed."
fi

echo ""
echo "=== Step 2: Install gem5 build dependencies ==="
echo "Installing: scons, swig, protobuf"
brew install scons swig protobuf || {
    echo "Warning: Some packages may already be installed."
}

echo ""
echo "=== Step 3: Install QEMU ==="
echo "Installing QEMU for ARM64 user-mode emulation..."
brew install qemu || {
    echo "Warning: QEMU may already be installed."
}

echo ""
echo "=== Step 4: Install ARM64 cross-compiler ==="
echo "Checking for ARM64 cross-compiler..."

if command -v aarch64-linux-gnu-gcc &>/dev/null; then
    echo "aarch64-linux-gnu-gcc is already installed."
    aarch64-linux-gnu-gcc --version | head -1
elif command -v aarch64-unknown-elf-gcc &>/dev/null; then
    echo "Found aarch64-unknown-elf-gcc (alternative ARM64 compiler)."
    aarch64-unknown-elf-gcc --version | head -1
else
    echo "Installing ARM64 cross-compiler..."
    echo ""
    echo "Option 1: Using Homebrew cask (recommended)"
    echo "  brew install --cask gcc-aarch64-embedded"
    echo ""
    echo "Option 2: Using ARM official toolchain"
    echo "  Download from: https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a"
    echo ""
    read -p "Install via Homebrew? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install --cask gcc-aarch64-embedded
    fi
fi

echo ""
echo "=== Step 5: Install Python dependencies ==="
echo "Installing Python packages..."
pip3 install --user six protobuf numpy || {
    echo "Warning: Some packages may already be installed."
}

echo ""
echo "=== Step 6: Verify installation ==="
echo ""
echo "Checking installed tools:"
echo ""

check_tool() {
    local tool=$1
    local package=$2
    if command -v "$tool" &>/dev/null; then
        echo "✓ $tool: $(which $tool)"
    else
        echo "✗ $tool: not found (try: brew install $package)"
    fi
}

check_tool "scons" "scons"
check_tool "swig" "swig"
check_tool "protoc" "protobuf"
check_tool "qemu-aarch64" "qemu"
check_tool "aarch64-linux-gnu-gcc" "gcc-aarch64-embedded (cask)"
check_tool "python3" "python@3"

echo ""
echo "Python packages:"
pip3 list 2>/dev/null | grep -iE "six|protobuf|numpy" || echo "  (none found)"

echo ""
echo "=========================================="
echo "Environment Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Build gem5: ./scripts/build_gem5.sh ARM opt"
echo "  2. Run preflight check: python3 tools/sdc_preflight.py --verbose"
echo "  3. Test gem5 build: python3 dev/debug/test_gem5_build.py"
echo ""
