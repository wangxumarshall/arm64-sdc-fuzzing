#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "build_gem5_noninteractive.sh is now a compatibility wrapper."
echo "Delegating to build_gem5_linux_arm.sh..."
exec "$SCRIPT_DIR/build_gem5_linux_arm.sh"
