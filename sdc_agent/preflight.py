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

from .tooling import (
    DEFAULT_GEM5_BINARY,
    DEFAULT_GEM5_CONFIG,
    DEFAULT_MCPAT_BINARY,
    build_missing_steps,
    resolve_local_tools,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
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
    parts = version.split(".")
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
    checks.append(
        PreflightCheck(
            name="scons",
            ok=scons is not None,
            required=True,
            detail="found" if scons else "missing",
            path=scons,
            install_hint="brew install scons",
        )
    )

    swig = shutil.which("swig")
    checks.append(
        PreflightCheck(
            name="swig",
            ok=swig is not None,
            required=True,
            detail="found" if swig else "missing",
            path=swig,
            install_hint="brew install swig",
        )
    )

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

    checks.append(
        PreflightCheck(
            name="protobuf",
            ok=protoc_ok,
            required=True,
            detail=protoc_detail,
            install_hint="brew install protobuf",
        )
    )

    return checks


def _tool_check(
    name: str,
    resolved_path: Optional[str],
    *,
    required: bool,
    install_hint: Optional[str] = None,
) -> PreflightCheck:
    return PreflightCheck(
        name=name,
        ok=resolved_path is not None,
        required=required,
        detail="resolved" if resolved_path else "missing",
        path=resolved_path,
        install_hint=install_hint,
    )


def run_preflight(
    *,
    compiler: Optional[str | Path] = None,
    qemu_binary: Optional[str | Path] = None,
    qemu_user_binary: Optional[str | Path] = None,
    qemu_system_binary: Optional[str | Path] = None,
    gem5_binary: Optional[Path] = DEFAULT_GEM5_BINARY,
    mcpat_binary: Optional[Path] = DEFAULT_MCPAT_BINARY,
    gem5_config: Optional[Path] = DEFAULT_GEM5_CONFIG,
    vault_path: Path = DEFAULT_VAULT,
    meson_binary: Optional[str | Path] = None,
    ninja_binary: Optional[str | Path] = None,
    opendcdiag_root: Optional[str | Path] = None,
    check_build_deps: bool = True,
    check_hardware_tools: bool = False,
    require_qemu_user: bool = True,
    require_qemu_system: bool = False,
    require_mcpat: bool = True,
) -> dict:
    if qemu_user_binary is None and qemu_binary is not None:
        qemu_user_binary = qemu_binary

    compiler_hint = None if str(compiler or "").strip() in {"", "aarch64-linux-gnu-gcc"} else compiler
    qemu_user_hint = None if str(qemu_user_binary or "").strip() in {"", "qemu-aarch64"} else qemu_user_binary
    qemu_system_hint = None if str(qemu_system_binary or "").strip() in {"", "qemu-system-aarch64"} else qemu_system_binary

    resolved = resolve_local_tools(
        compiler=compiler_hint,
        qemu_user_binary=qemu_user_hint,
        qemu_system_binary=qemu_system_hint,
        gem5_binary=gem5_binary,
        gem5_config=gem5_config,
        mcpat_binary=mcpat_binary,
        meson_binary=meson_binary,
        ninja_binary=ninja_binary,
        opendcdiag_root=opendcdiag_root,
    )

    checks: List[PreflightCheck] = [
        check_python_version(),
        _tool_check(
            "compiler",
            resolved.compiler,
            required=True,
            install_hint="brew install --cask gcc-aarch64-embedded",
        ),
        _tool_check(
            "qemu_user_binary",
            resolved.qemu_user_binary,
            required=require_qemu_user,
            install_hint="Run ./scripts/build_qemu_headless.sh or install qemu",
        ),
        _tool_check(
            "qemu_system_binary",
            resolved.qemu_system_binary,
            required=require_qemu_system,
            install_hint="Run ./scripts/build_qemu_headless.sh or install qemu",
        ),
        _tool_check(
            "gem5_binary",
            resolved.gem5_binary,
            required=True,
            install_hint="Run ./scripts/build_gem5_noninteractive.sh",
        ),
        _tool_check(
            "mcpat_binary",
            resolved.mcpat_binary,
            required=require_mcpat,
            install_hint="Run ./scripts/build_mcpat.sh",
        ),
        _tool_check(
            "gem5_config",
            resolved.gem5_config,
            required=True,
        ),
        check_path("vault_parent", vault_path.parent, required=False),
    ]

    checks.extend(
        [
            _tool_check(
                "meson",
                resolved.meson_binary,
                required=check_hardware_tools,
                install_hint="brew install meson",
            ),
            _tool_check(
                "ninja",
                resolved.ninja_binary,
                required=check_hardware_tools,
                install_hint="brew install ninja",
            ),
            _tool_check(
                "opendcdiag_root",
                resolved.opendcdiag_root,
                required=check_hardware_tools,
            ),
        ]
    )

    if check_build_deps:
        checks.extend(check_build_dependencies())

    ready = all(check.ok for check in checks if check.required)
    missing_steps = build_missing_steps(
        resolved,
        require_qemu_user=require_qemu_user,
        require_qemu_system=require_qemu_system,
        require_mcpat=require_mcpat,
        require_hardware_tools=check_hardware_tools,
    )
    return {
        "ready": ready,
        "repo_root": str(REPO_ROOT),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "checks": [asdict(check) for check in checks],
        "resolved_paths": resolved.to_dict(),
        "qemu_user_binary": resolved.qemu_user_binary,
        "qemu_system_binary": resolved.qemu_system_binary,
        "missing_steps": [step.to_dict() for step in missing_steps],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the local ARM64 SDC fuzzing toolchain is ready."
    )
    parser.add_argument("--compiler", default=None)
    parser.add_argument("--qemu-binary", default=None, help="Alias for --qemu-user-binary.")
    parser.add_argument("--qemu-user-binary", default=None)
    parser.add_argument("--qemu-system-binary", default=None)
    parser.add_argument("--gem5-binary", type=Path, default=DEFAULT_GEM5_BINARY)
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    parser.add_argument("--vault-path", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--meson-binary", default=None)
    parser.add_argument("--ninja-binary", default=None)
    parser.add_argument("--opendcdiag-root", default=None)
    parser.add_argument(
        "--skip-build-deps",
        action="store_true",
        help="Skip build dependency checks",
    )
    parser.add_argument(
        "--skip-hardware-tools",
        action="store_true",
        help="Skip local hardware-lane tool checks",
    )
    parser.add_argument(
        "--skip-system-qemu",
        action="store_true",
        help="Do not require a system-mode QEMU binary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output with install hints",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = run_preflight(
        compiler=args.compiler,
        qemu_binary=args.qemu_binary,
        qemu_user_binary=args.qemu_user_binary,
        qemu_system_binary=args.qemu_system_binary,
        gem5_binary=args.gem5_binary,
        mcpat_binary=args.mcpat_binary,
        gem5_config=args.gem5_config,
        vault_path=args.vault_path,
        meson_binary=args.meson_binary,
        ninja_binary=args.ninja_binary,
        opendcdiag_root=args.opendcdiag_root,
        check_build_deps=not args.skip_build_deps,
        check_hardware_tools=not args.skip_hardware_tools,
        require_qemu_system=not args.skip_system_qemu,
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
        print("\nResolved Paths:")
        for name, value in result["resolved_paths"].items():
            print(f"  {name}: {value or '(missing)'}")
        if result["missing_steps"]:
            print("\nMissing Steps:")
            for step in result["missing_steps"]:
                auto = "auto-build" if step["auto_build"] else "manual"
                print(f"  - [{auto}] {step['step_id']}: {step['detail']}")
                if step.get("command"):
                    print(f"    command: {' '.join(step['command'])}")

        if result["ready"]:
            print("\n✓ All required checks passed. Ready for SDC fuzzing!")
        else:
            print("\n✗ Some required checks failed. See above for details.")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
