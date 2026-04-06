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
from typing import Dict, List, Optional

from .tooling import (
    DEFAULT_GEM5_BINARY,
    DEFAULT_GEM5_CONFIG,
    DEFAULT_MCPAT_BINARY,
    HostContext,
    build_missing_steps,
    get_host_context,
    resolve_local_tools,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = REPO_ROOT / "artifacts" / "sdc_vault.sqlite3"

PROFILE_DEV = "dev"
PROFILE_SIM = "sim"
PROFILE_HW = "hw"
SUPPORTED_PROFILES = (PROFILE_DEV, PROFILE_SIM, PROFILE_HW)


@dataclass(frozen=True)
class PreflightProfileSpec:
    name: str
    description: str
    require_compiler: bool
    require_qemu_user: bool
    require_qemu_system: bool
    require_gem5: bool
    require_gem5_config: bool
    require_mcpat: bool
    require_hardware_tools: bool
    check_build_deps: bool
    default_qemu_user_binary: Optional[str | Path] = None
    default_qemu_system_binary: Optional[str | Path] = None
    default_gem5_binary: Optional[str | Path] = None
    default_mcpat_binary: Optional[str | Path] = None
    default_gem5_config: Optional[str | Path] = None


PROFILE_SPECS: Dict[str, PreflightProfileSpec] = {
    PROFILE_DEV: PreflightProfileSpec(
        name=PROFILE_DEV,
        description="Developer/control-plane smoke on any supported host.",
        require_compiler=True,
        require_qemu_user=False,
        require_qemu_system=False,
        require_gem5=False,
        require_gem5_config=False,
        require_mcpat=False,
        require_hardware_tools=False,
        check_build_deps=False,
    ),
    PROFILE_SIM: PreflightProfileSpec(
        name=PROFILE_SIM,
        description="Real simulation runner on Ubuntu 24.04 ARM.",
        require_compiler=True,
        require_qemu_user=True,
        require_qemu_system=True,
        require_gem5=True,
        require_gem5_config=True,
        require_mcpat=True,
        require_hardware_tools=False,
        check_build_deps=True,
        default_qemu_user_binary="qemu-aarch64",
        default_qemu_system_binary="qemu-system-aarch64",
        default_gem5_binary=DEFAULT_GEM5_BINARY,
        default_mcpat_binary=DEFAULT_MCPAT_BINARY,
        default_gem5_config=DEFAULT_GEM5_CONFIG,
    ),
    PROFILE_HW: PreflightProfileSpec(
        name=PROFILE_HW,
        description="Hardware promotion and OpenDCDiag staging lane.",
        require_compiler=False,
        require_qemu_user=False,
        require_qemu_system=False,
        require_gem5=False,
        require_gem5_config=False,
        require_mcpat=False,
        require_hardware_tools=True,
        check_build_deps=False,
    ),
}


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    required: bool
    detail: str
    path: Optional[str] = None
    install_hint: Optional[str] = None


def normalize_profile_name(profile: str) -> str:
    normalized = str(profile).strip().lower()
    if normalized not in PROFILE_SPECS:
        raise ValueError(
            f"Unsupported preflight profile: {profile}. "
            f"Expected one of {', '.join(SUPPORTED_PROFILES)}."
        )
    return normalized


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
        install_hint="Python 3.8+ required for the control plane and gem5 scripts.",
    )


def _install_hint_for_package(host: HostContext, package: str, *, mac_package: Optional[str] = None) -> str:
    if host.is_linux:
        return f"sudo apt-get install -y {package}"
    package_name = mac_package or package
    return f"brew install {package_name}"


def check_build_dependencies(host: HostContext) -> List[PreflightCheck]:
    checks = []

    scons = shutil.which("scons")
    checks.append(
        PreflightCheck(
            name="scons",
            ok=scons is not None,
            required=True,
            detail="found" if scons else "missing",
            path=scons,
            install_hint=_install_hint_for_package(host, "scons"),
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
            install_hint=_install_hint_for_package(host, "swig"),
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
            install_hint=_install_hint_for_package(host, "protobuf-compiler", mac_package="protobuf"),
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


def _profile_compatibility_check(profile: str, host: HostContext) -> PreflightCheck:
    if profile == PROFILE_SIM:
        ok = host.is_linux_arm64
        detail = (
            "Linux/aarch64 host detected."
            if ok
            else "sim profile requires a Linux/aarch64 host (Ubuntu 24.04 ARM recommended)."
        )
        return PreflightCheck(
            name="host_profile_compatibility",
            ok=ok,
            required=True,
            detail=detail,
            install_hint="Run the sim profile on an Ubuntu 24.04 ARM machine.",
        )

    return PreflightCheck(
        name="host_profile_compatibility",
        ok=True,
        required=True,
        detail=f"{profile} profile is allowed on {host.system}/{host.machine}.",
    )


def run_preflight(
    *,
    profile: str = PROFILE_SIM,
    compiler: Optional[str | Path] = None,
    qemu_binary: Optional[str | Path] = None,
    qemu_user_binary: Optional[str | Path] = None,
    qemu_system_binary: Optional[str | Path] = None,
    gem5_binary: Optional[str | Path] = DEFAULT_GEM5_BINARY,
    mcpat_binary: Optional[str | Path] = DEFAULT_MCPAT_BINARY,
    gem5_config: Optional[str | Path] = DEFAULT_GEM5_CONFIG,
    vault_path: Path = DEFAULT_VAULT,
    meson_binary: Optional[str | Path] = None,
    ninja_binary: Optional[str | Path] = None,
    opendcdiag_root: Optional[str | Path] = None,
    check_build_deps: Optional[bool] = None,
    check_hardware_tools: Optional[bool] = None,
    require_qemu_user: Optional[bool] = None,
    require_qemu_system: Optional[bool] = None,
    require_mcpat: Optional[bool] = None,
) -> dict:
    normalized_profile = normalize_profile_name(profile)
    spec = PROFILE_SPECS[normalized_profile]
    host = get_host_context()

    if qemu_user_binary is None and qemu_binary is not None:
        qemu_user_binary = qemu_binary

    require_compiler = spec.require_compiler
    effective_require_qemu_user = spec.require_qemu_user if require_qemu_user is None else require_qemu_user
    effective_require_qemu_system = spec.require_qemu_system if require_qemu_system is None else require_qemu_system
    effective_require_mcpat = spec.require_mcpat if require_mcpat is None else require_mcpat
    effective_require_gem5 = spec.require_gem5
    effective_require_gem5_config = spec.require_gem5_config
    effective_check_build_deps = spec.check_build_deps if check_build_deps is None else check_build_deps
    effective_check_hardware_tools = (
        spec.require_hardware_tools if check_hardware_tools is None else check_hardware_tools
    )

    resolved = resolve_local_tools(
        compiler=compiler,
        qemu_user_binary=qemu_user_binary if qemu_user_binary is not None else spec.default_qemu_user_binary,
        qemu_system_binary=(
            qemu_system_binary if qemu_system_binary is not None else spec.default_qemu_system_binary
        ),
        gem5_binary=gem5_binary if gem5_binary is not None else spec.default_gem5_binary,
        gem5_config=gem5_config if gem5_config is not None else spec.default_gem5_config,
        mcpat_binary=mcpat_binary if mcpat_binary is not None else spec.default_mcpat_binary,
        meson_binary=meson_binary,
        ninja_binary=ninja_binary,
        opendcdiag_root=opendcdiag_root,
    )

    compiler_hint = (
        "Install `build-essential` on Ubuntu 24.04 ARM or expose `aarch64-linux-gnu-gcc`."
        if host.is_linux
        else "Install an ARM64 compiler or set SDC_COMPILER."
    )
    qemu_user_hint = (
        "Install `qemu-user` on Ubuntu 24.04 ARM or set SDC_QEMU_USER_BINARY."
        if normalized_profile == PROFILE_SIM
        else "Set SDC_QEMU_USER_BINARY or build repo-local QEMU."
    )
    qemu_system_hint = (
        "Install `qemu-system-arm` on Ubuntu 24.04 ARM or set SDC_QEMU_SYSTEM_BINARY."
        if normalized_profile == PROFILE_SIM
        else "Set SDC_QEMU_SYSTEM_BINARY or build repo-local QEMU."
    )

    checks: List[PreflightCheck] = [
        check_python_version(),
        _profile_compatibility_check(normalized_profile, host),
        _tool_check(
            "compiler",
            resolved.compiler,
            required=require_compiler,
            install_hint=compiler_hint,
        ),
        _tool_check(
            "qemu_user_binary",
            resolved.qemu_user_binary,
            required=effective_require_qemu_user,
            install_hint=qemu_user_hint,
        ),
        _tool_check(
            "qemu_system_binary",
            resolved.qemu_system_binary,
            required=effective_require_qemu_system,
            install_hint=qemu_system_hint,
        ),
        _tool_check(
            "gem5_binary",
            resolved.gem5_binary,
            required=effective_require_gem5,
            install_hint="Build repo-local gem5 with ./scripts/build_gem5_linux_arm.sh",
        ),
        _tool_check(
            "mcpat_binary",
            resolved.mcpat_binary,
            required=effective_require_mcpat,
            install_hint="Build repo-local McPAT with ./scripts/build_mcpat.sh",
        ),
        _tool_check(
            "gem5_config",
            resolved.gem5_config,
            required=effective_require_gem5_config,
        ),
        check_path("vault_parent", vault_path.parent, required=False),
    ]

    checks.extend(
        [
            _tool_check(
                "meson",
                resolved.meson_binary,
                required=effective_check_hardware_tools,
                install_hint=_install_hint_for_package(host, "meson"),
            ),
            _tool_check(
                "ninja",
                resolved.ninja_binary,
                required=effective_check_hardware_tools,
                install_hint=_install_hint_for_package(host, "ninja-build", mac_package="ninja"),
            ),
            _tool_check(
                "opendcdiag_root",
                resolved.opendcdiag_root,
                required=effective_check_hardware_tools,
            ),
        ]
    )

    if effective_check_build_deps:
        checks.extend(check_build_dependencies(host))

    ready = all(check.ok for check in checks if check.required)
    missing_steps = build_missing_steps(
        resolved,
        profile=normalized_profile,
        host=host,
        require_qemu_user=effective_require_qemu_user,
        require_qemu_system=effective_require_qemu_system,
        require_gem5=effective_require_gem5,
        require_gem5_config=effective_require_gem5_config,
        require_mcpat=effective_require_mcpat,
        require_hardware_tools=effective_check_hardware_tools,
    )
    return {
        "ready": ready,
        "profile": normalized_profile,
        "profile_description": spec.description,
        "repo_root": str(REPO_ROOT),
        "platform": host.system,
        "python_version": host.python_version,
        "host": host.to_dict(),
        "checks": [asdict(check) for check in checks],
        "resolved_paths": resolved.to_dict(),
        "qemu_user_binary": resolved.qemu_user_binary,
        "qemu_system_binary": resolved.qemu_system_binary,
        "missing_steps": [step.to_dict() for step in missing_steps],
    }


def summarize_runtime_capabilities() -> Dict[str, object]:
    host = get_host_context()
    profiles: Dict[str, object] = {}
    for profile_name in SUPPORTED_PROFILES:
        result = run_preflight(profile=profile_name, check_build_deps=False)
        profiles[profile_name] = {
            "ready": bool(result["ready"]),
            "required_failures": [
                check["name"]
                for check in result["checks"]
                if check["required"] and not check["ok"]
            ],
        }
    return {
        "host": host.to_dict(),
        "profiles": profiles,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the local ARM64 SDC fuzzing toolchain is ready."
    )
    parser.add_argument("--profile", default=PROFILE_SIM, choices=SUPPORTED_PROFILES)
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
        help="Skip build dependency checks for the selected profile.",
    )
    parser.add_argument(
        "--skip-hardware-tools",
        action="store_true",
        help="Skip local hardware-lane tool checks even if the profile normally requires them.",
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
        profile=args.profile,
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
        print(f"\nProfile: {result['profile']}")
        print(f"Description: {result['profile_description']}")
        print(f"Platform: {result['platform']}")
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
            print(f"\n✓ All required checks passed for profile {result['profile']}.")
        else:
            print(f"\n✗ Required checks failed for profile {result['profile']}.")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
