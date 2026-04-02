#!/usr/bin/env python3
"""Test gem5 ARM64 build and execution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GEM5_BINARY = REPO_ROOT / "gem5" / "build" / "ARM" / "gem5.opt"
DEFAULT_GEM5_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "starter_se.py"


def check_gem5_binary(gem5_binary: Path) -> Dict[str, any]:
    """Check if gem5 binary exists and is executable."""
    result = {
        "check": "gem5_binary",
        "path": str(gem5_binary),
        "exists": gem5_binary.exists(),
        "is_file": gem5_binary.is_file() if gem5_binary.exists() else False,
        "executable": False,
        "version": None,
        "error": None,
    }
    
    if result["exists"] and result["is_file"]:
        result["executable"] = os.access(gem5_binary, os.X_OK)
    
    if result["executable"]:
        try:
            output = subprocess.run(
                [str(gem5_binary), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if output.returncode == 0:
                result["version"] = output.stdout.strip().split("\n")[0]
        except Exception as e:
            result["error"] = str(e)
    
    return result


def check_gem5_config(gem5_config: Path) -> Dict[str, any]:
    """Check if gem5 config file exists."""
    return {
        "check": "gem5_config",
        "path": str(gem5_config),
        "exists": gem5_config.exists(),
        "is_file": gem5_config.is_file() if gem5_config.exists() else False,
    }


def create_hello_world_binary(output_dir: Path) -> Optional[Path]:
    """Create a simple ARM64 hello world binary for testing."""
    source = output_dir / "hello.c"
    binary = output_dir / "hello"
    
    source.write_text("""
#include <stdio.h>
int main() {
    printf("Hello from gem5 ARM64!\\n");
    return 0;
}
""")
    
    try:
        subprocess.run(
            ["aarch64-linux-gnu-gcc", "-static", "-o", str(binary), str(source)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return binary
    except FileNotFoundError:
        print("WARNING: aarch64-linux-gnu-gcc not found, skipping binary creation")
        return None
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Failed to compile test binary: {e.stderr}")
        return None


def test_gem5_se_mode(
    gem5_binary: Path,
    gem5_config: Path,
    test_binary: Path,
    output_dir: Path,
    timeout: int = 60,
) -> Dict[str, any]:
    """Test gem5 SE mode execution."""
    result = {
        "check": "gem5_se_mode",
        "success": False,
        "output": None,
        "error": None,
        "returncode": None,
    }
    
    gem5_outdir = output_dir / "m5out-test"
    
    try:
        proc = subprocess.run(
            [
                str(gem5_binary),
                "-d", str(gem5_outdir),
                str(gem5_config),
                "--cpu-type=atomic",
                "--num-cores=1",
                "--mem-size=256MiB",
                str(test_binary),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
        
        result["returncode"] = proc.returncode
        result["output"] = proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout
        
        if proc.returncode == 0:
            result["success"] = True
        else:
            result["error"] = proc.stderr[-500:] if len(proc.stderr) > 500 else proc.stderr
            
    except subprocess.TimeoutExpired:
        result["error"] = f"Timeout after {timeout} seconds"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Test gem5 ARM64 build")
    parser.add_argument(
        "--gem5-binary",
        type=Path,
        default=DEFAULT_GEM5_BINARY,
        help="Path to gem5 binary",
    )
    parser.add_argument(
        "--gem5-config",
        type=Path,
        default=DEFAULT_GEM5_CONFIG,
        help="Path to gem5 SE config",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "gem5-test",
        help="Output directory for test artifacts",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout for gem5 execution in seconds",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "ready": False,
        "checks": [],
    }
    
    print("=== gem5 ARM64 Build Test ===\n")
    
    print("1. Checking gem5 binary...")
    binary_check = check_gem5_binary(args.gem5_binary)
    results["checks"].append(binary_check)
    if binary_check["exists"]:
        print(f"   ✓ Binary exists: {binary_check['path']}")
        if binary_check["executable"]:
            print(f"   ✓ Binary is executable")
            if binary_check["version"]:
                print(f"   ✓ Version: {binary_check['version']}")
        else:
            print(f"   ✗ Binary is not executable")
    else:
        print(f"   ✗ Binary not found: {binary_check['path']}")
        print(f"   → Run: ./scripts/build_gem5.sh ARM opt")
    
    print("\n2. Checking gem5 config...")
    config_check = check_gem5_config(args.gem5_config)
    results["checks"].append(config_check)
    if config_check["exists"]:
        print(f"   ✓ Config exists: {config_check['path']}")
    else:
        print(f"   ✗ Config not found: {config_check['path']}")
    
    print("\n3. Testing gem5 SE mode execution...")
    if binary_check["executable"] and config_check["exists"]:
        test_binary = create_hello_world_binary(args.output_dir)
        if test_binary:
            print(f"   Created test binary: {test_binary}")
            se_test = test_gem5_se_mode(
                args.gem5_binary,
                args.gem5_config,
                test_binary,
                args.output_dir,
                args.timeout,
            )
            results["checks"].append(se_test)
            
            if se_test["success"]:
                print(f"   ✓ gem5 SE mode execution successful")
                print(f"   Output: {se_test['output'][:200]}")
            else:
                print(f"   ✗ gem5 SE mode execution failed")
                if se_test["error"]:
                    print(f"   Error: {se_test['error']}")
        else:
            print("   ⊘ Skipped: Could not create test binary")
            print("   → Install: brew install --cask gcc-aarch64-embedded")
    else:
        print("   ⊘ Skipped: gem5 binary or config not available")
    
    results["ready"] = all(
        c.get("success", c.get("exists", False))
        for c in results["checks"]
    )
    
    if args.json:
        print("\n" + json.dumps(results, indent=2))
    else:
        print(f"\n{'='*40}")
        if results["ready"]:
            print("✓ gem5 ARM64 is ready for SDC fuzzing!")
        else:
            print("✗ gem5 ARM64 setup incomplete")
            print("\nNext steps:")
            if not binary_check["exists"]:
                print("  1. Build gem5: ./scripts/build_gem5.sh ARM opt")
            if not binary_check.get("executable"):
                print("  2. Verify permissions: chmod +x gem5/build/ARM/gem5.opt")
            print("  3. Install toolchain: brew install qemu")
            print("  4. Install cross-compiler: brew install --cask gcc-aarch64-embedded")
    
    return 0 if results["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
