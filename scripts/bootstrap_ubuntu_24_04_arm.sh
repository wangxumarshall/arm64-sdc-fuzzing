#!/bin/bash
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: bootstrap_ubuntu_24_04_arm.sh must run on Linux."
    exit 1
fi

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: bootstrap_ubuntu_24_04_arm.sh is intended for Ubuntu 24.04 ARM hosts."
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: apt-get not found. This bootstrap script targets Ubuntu 24.04."
    exit 1
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi

echo "=========================================="
echo "Ubuntu 24.04 ARM Bootstrap for SDC-Agent"
echo "=========================================="
echo "Host: $(uname -s) $(uname -m)"
echo ""

APT_PACKAGES=(
    build-essential
    gcc
    g++
    python3
    python3-dev
    python3-venv
    python3-pip
    pkg-config
    git
    qemu-user
    qemu-system-arm
    meson
    ninja-build
    scons
    swig
    protobuf-compiler
    libprotobuf-dev
    zlib1g-dev
    libgoogle-perftools-dev
    libboost-all-dev
    m4
    libpng-dev
    libelf-dev
)

echo "Installing apt packages..."
$SUDO apt-get update
$SUDO apt-get install -y "${APT_PACKAGES[@]}"

echo ""
echo "Verifying critical tools..."
for tool in python3 gcc g++ qemu-aarch64 qemu-system-aarch64 meson ninja scons swig protoc; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo "  ✓ $tool -> $(command -v "$tool")"
    else
        echo "  ✗ $tool missing after bootstrap"
        exit 1
    fi
done

echo ""
echo "Bootstrap complete."
