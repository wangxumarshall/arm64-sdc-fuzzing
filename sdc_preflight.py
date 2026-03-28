#!/usr/bin/env python3
"""Preflight checks for the ARM64 SDC fuzzing toolchain."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_GEM5_BINARY = REPO_ROOT / "gem5" / "build" / "ARM" / "gem5.opt"
DEFAULT_MCPAT_BINARY = REPO_ROOT / "mcpat" / "mcpat" / "mcpat"
DEFAULT_GEM5_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "sdc_kunpeng920_se.py"
DEFAULT_VAULT = REPO_ROOT / "artifacts" / "sdc_vault.sqlite3"


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    required: bool
    detail: str
    path: Optional[str] = None
    install_hint: Optional[str] = None


def check_command(name: str, *, required: bool = True, install_hint: Optional[str] = None) -> PreflightCheck:
    resolved = shutil.which(name)
    return PreflightCheck(
        name=name,
        ok=resolved is not None,
        required=required,
        detail="found" if resolved else "missing from PATH",
        path=resolved,
        install_hint=install_hint,
    )


def check_path(
    name: str,
    path: Path,
    *,
    required: bool = True,
    executable: bool = False,
    install_hint: Optional[str] = None,
) -> PreflightCheck:
    resolved = path.resolve()
    exists = resolved.exists()
    if executable:
        ok = exists and resolved.is_file() and resolved.stat().st_mode & 0o111 != 0
        detail = "executable present" if ok else "missing or not executable"
    else:
        ok = exists
        detail = "present" if ok else "missing"
    return PreflightCheck(
        name=name,
        ok=ok,
        required=required,
        detail=detail,
        path=str(resolved),
        install_hint=install_hint,
    )


def check_python_version() -> PreflightCheck:
    version = platform.python_version()
    parts = version.split('.')
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    ok = major == 3 and minor >= 8
    return PreflightCheck(
        name="python_version",
        ok=ok,
        required=True,
        detail=f"Python {version}",
        install_hint="Python 3.8+ required for gem5",
    )


def check_build_dependencies() -> List[PreflightCheck]:
    checks = []
    
    scons = shutil.which("scons")
    checks.append(PreflightCheck(
        name="scons",
        ok=scons is not None,
        required=True,
        detail="found" if scons else "missing",
        path=scons,
        install_hint="brew install scons",
    ))
    
    swig = shutil.which("swig")
    checks.append(PreflightCheck(
        name="swig",
        ok=swig is not None,
        required=True,
        detail="found" if swig else "missing",
        path=swig,
        install_hint="brew install swig",
    ))
    
    try:
        result = subprocess.run(
            ["protoc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        protoc_ok = result.returncode == 0
        protoc_detail = result.stdout.strip() if protoc_ok else "not working"
    except Exception:
        protoc_ok = False
        protoc_detail = "missing"
    
    checks.append(PreflightCheck(
        name="protobuf",
        ok=protoc_ok,
        required=True,
        detail=protoc_detail,
        install_hint="brew install protobuf",
    ))
    
    return checks


def run_preflight(
    *,
    compiler: str = "aarch64-linux-gnu-gcc",
    qemu_binary: str = "qemu-aarch64",
    gem5_binary: Path = DEFAULT_GEM5_BINARY,
    mcpat_binary: Path = DEFAULT_MCPAT_BINARY,
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    vault_path: Path = DEFAULT_VAULT,
    check_build_deps: bool = True,
) -> dict:
    checks: List[PreflightCheck] = [
        check_python_version(),
        check_command(compiler, required=True, install_hint="brew install --cask gcc-aarch64-embedded"),
        check_command(qemu_binary, required=True, install_hint="brew install qemu"),
        check_path("gem5_binary", gem5_binary, required=True, executable=True, 
                   install_hint="Run: ./build_gem5.sh ARM opt"),
        check_path("mcpat_binary", mcpat_binary, required=True, executable=True),
        check_path("gem5_config", gem5_config, required=True),
        check_path("vault_parent", vault_path.parent, required=False),
    ]
    
    if check_build_deps:
        checks.extend(check_build_dependencies())

    ready = all(check.ok for check in checks if check.required)
    return {
        "ready": ready,
        "repo_root": str(REPO_ROOT),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "checks": [asdict(check) for check in checks],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the local ARM64 SDC fuzzing toolchain is ready."
    )
    parser.add_argument("--compiler", default="aarch64-linux-gnu-gcc")
    parser.add_argument("--qemu-binary", default="qemu-aarch64")
    parser.add_argument("--gem5-binary", type=Path, default=DEFAULT_GEM5_BINARY)
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    parser.add_argument("--vault-path", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--skip-build-deps", action="store_true",
                        help="Skip build dependency checks")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output with install hints")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = run_preflight(
        compiler=args.compiler,
        qemu_binary=args.qemu_binary,
        gem5_binary=args.gem5_binary,
        mcpat_binary=args.mcpat_binary,
        gem5_config=args.gem5_config,
        vault_path=args.vault_path,
        check_build_deps=not args.skip_build_deps,
    )
    
    if args.verbose:
        print("=" * 60)
        print("ARM64 SDC Fuzzing Toolchain Preflight Check")
        print("=" * 60)
        print(f"\nPlatform: {result['platform']}")
        print(f"Python: {result['python_version']}")
        print(f"Repository: {result['repo_root']}")
        print("\nChecks:")
        print("-" * 60)
        
        for check in result["checks"]:
            status = "✓" if check["ok"] else "✗" if check["required"] else "○"
            print(f"{status} {check['name']}: {check['detail']}")
            if check.get("path"):
                print(f"   Path: {check['path']}")
            if not check["ok"] and check.get("install_hint"):
                print(f"   Install: {check['install_hint']}")
        
        print("-" * 60)
        if result["ready"]:
            print("\n✓ All required checks passed. Ready for SDC fuzzing!")
        else:
            print("\n✗ Some required checks failed. See above for details.")
            print("\nQuick fix commands:")
            print("  brew install scons swig protobuf qemu")
            print("  brew install --cask gcc-aarch64-embedded")
            print("  ./build_gem5.sh ARM opt")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
