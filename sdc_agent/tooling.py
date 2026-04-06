#!/usr/bin/env python3
"""Shared local tool resolution for the ARM64 SDC workflow."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEM5_BINARY = REPO_ROOT / "gem5" / "build" / "ARM" / "gem5.opt"
DEFAULT_GEM5_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "sdc_kunpeng920_se.py"
DEFAULT_GEM5_BAREMETAL_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "baremetal.py"
DEFAULT_MCPAT_BINARY = REPO_ROOT / "mcpat" / "mcpat"
DEFAULT_OPENDCDIAG_ROOT = REPO_ROOT / "opendcdiag"
DEFAULT_QEMU_SYSTEM_BINARY = REPO_ROOT / "qemu" / "build" / "qemu-system-aarch64"
DEFAULT_QEMU_SYSTEM_BINARY_UNSIGNED = REPO_ROOT / "qemu" / "build" / "qemu-system-aarch64-unsigned"
DEFAULT_QEMU_USER_BINARY = REPO_ROOT / "qemu" / "build" / "qemu-aarch64"

ENV_COMPILER = "SDC_COMPILER"
ENV_QEMU_USER_BINARY = "SDC_QEMU_USER_BINARY"
ENV_QEMU_SYSTEM_BINARY = "SDC_QEMU_SYSTEM_BINARY"
ENV_GEM5_BINARY = "SDC_GEM5_BINARY"
ENV_MCPAT_BINARY = "SDC_MCPAT_BINARY"
ENV_OPENDCDIAG_ROOT = "SDC_OPENDCDIAG_ROOT"
ENV_GEM5_CONFIG = "SDC_GEM5_CONFIG"
ENV_MESON_BINARY = "SDC_MESON_BINARY"
ENV_NINJA_BINARY = "SDC_NINJA_BINARY"


@dataclass(frozen=True)
class HostContext:
    system: str
    machine: str
    python_version: str
    os_release: Dict[str, str] = field(default_factory=dict)

    @property
    def normalized_machine(self) -> str:
        return self.machine.strip().lower()

    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"

    @property
    def is_darwin(self) -> bool:
        return self.system == "Darwin"

    @property
    def is_linux_arm64(self) -> bool:
        return self.is_linux and self.normalized_machine in {"aarch64", "arm64"}

    def to_dict(self) -> Dict[str, object]:
        return {
            "system": self.system,
            "machine": self.machine,
            "python_version": self.python_version,
            "os_release": dict(self.os_release),
            "is_linux": self.is_linux,
            "is_darwin": self.is_darwin,
            "is_linux_arm64": self.is_linux_arm64,
        }


@dataclass(frozen=True)
class LocalToolResolution:
    compiler: Optional[str]
    qemu_user_binary: Optional[str]
    qemu_system_binary: Optional[str]
    gem5_binary: Optional[str]
    gem5_config: Optional[str]
    mcpat_binary: Optional[str]
    meson_binary: Optional[str]
    ninja_binary: Optional[str]
    opendcdiag_root: Optional[str]

    def to_dict(self) -> Dict[str, Optional[str]]:
        return asdict(self)


@dataclass(frozen=True)
class MissingStep:
    step_id: str
    detail: str
    command: Optional[List[str]]
    cwd: Optional[str]
    auto_build: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def get_host_context() -> HostContext:
    os_release: Dict[str, str] = {}
    if platform.system() == "Linux":
        try:
            os_release = dict(platform.freedesktop_os_release())  # type: ignore[attr-defined]
        except Exception:
            os_release = {}
    return HostContext(
        system=platform.system(),
        machine=platform.machine(),
        python_version=platform.python_version(),
        os_release=os_release,
    )


def _looks_like_path(value: str) -> bool:
    return os.sep in value or value.startswith(".") or value.startswith("~")


def _normalize_requested_value(value: Optional[str | Path]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "" or raw.lower() == "auto":
        return None
    return raw


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_single_command_or_executable(value: str) -> Optional[str]:
    if _looks_like_path(value):
        path = Path(value).expanduser()
        if _is_executable(path):
            return str(path.resolve())
        return None
    resolved = shutil.which(value)
    return resolved or None


def _resolve_single_existing_path(value: str, *, directory: bool = False) -> Optional[str]:
    path = Path(value).expanduser()
    if (path.is_dir() if directory else path.exists()):
        return str(path.resolve())
    return None


def _resolve_command_or_executable(
    explicit: Optional[str | Path],
    *,
    env_var: Optional[str] = None,
    repo_candidates: Sequence[Path] = (),
    command_candidates: Sequence[str] = (),
) -> Optional[str]:
    requested = _normalize_requested_value(explicit)
    if requested is not None:
        return _resolve_single_command_or_executable(requested)

    if env_var:
        env_value = _normalize_requested_value(os.environ.get(env_var))
        if env_value is not None:
            return _resolve_single_command_or_executable(env_value)

    for candidate in repo_candidates:
        if _is_executable(candidate):
            return str(candidate.resolve())

    for candidate in command_candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return None


def _resolve_existing_path(
    explicit: Optional[str | Path],
    *,
    env_var: Optional[str] = None,
    fallback_paths: Sequence[Path] = (),
    directory: bool = False,
) -> Optional[str]:
    requested = _normalize_requested_value(explicit)
    if requested is not None:
        return _resolve_single_existing_path(requested, directory=directory)

    if env_var:
        env_value = _normalize_requested_value(os.environ.get(env_var))
        if env_value is not None:
            return _resolve_single_existing_path(env_value, directory=directory)

    for candidate in fallback_paths:
        if (candidate.is_dir() if directory else candidate.exists()):
            return str(candidate.resolve())

    return None


def resolve_local_tools(
    *,
    compiler: Optional[str | Path] = None,
    qemu_user_binary: Optional[str | Path] = None,
    qemu_system_binary: Optional[str | Path] = None,
    gem5_binary: Optional[str | Path] = None,
    gem5_config: Optional[str | Path] = None,
    mcpat_binary: Optional[str | Path] = None,
    meson_binary: Optional[str | Path] = None,
    ninja_binary: Optional[str | Path] = None,
    opendcdiag_root: Optional[str | Path] = None,
    allow_native_compiler: Optional[bool] = None,
) -> LocalToolResolution:
    host = get_host_context()
    if allow_native_compiler is None:
        allow_native_compiler = host.is_linux_arm64

    compiler_candidates = ["aarch64-linux-gnu-gcc", "aarch64-conda-linux-gnu-gcc"]
    if allow_native_compiler:
        compiler_candidates.extend(["gcc", "cc"])

    resolved_compiler = _resolve_command_or_executable(
        compiler,
        env_var=ENV_COMPILER,
        command_candidates=tuple(compiler_candidates),
    )
    resolved_qemu_user = _resolve_command_or_executable(
        qemu_user_binary,
        env_var=ENV_QEMU_USER_BINARY,
        repo_candidates=(DEFAULT_QEMU_USER_BINARY,),
        command_candidates=("qemu-aarch64",),
    )
    resolved_qemu_system = _resolve_command_or_executable(
        qemu_system_binary,
        env_var=ENV_QEMU_SYSTEM_BINARY,
        repo_candidates=(DEFAULT_QEMU_SYSTEM_BINARY, DEFAULT_QEMU_SYSTEM_BINARY_UNSIGNED),
        command_candidates=("qemu-system-aarch64",),
    )
    resolved_gem5 = _resolve_command_or_executable(
        gem5_binary,
        env_var=ENV_GEM5_BINARY,
        repo_candidates=(DEFAULT_GEM5_BINARY,),
        command_candidates=("gem5.opt",),
    )
    resolved_mcpat = _resolve_command_or_executable(
        mcpat_binary,
        env_var=ENV_MCPAT_BINARY,
        repo_candidates=(DEFAULT_MCPAT_BINARY,),
        command_candidates=("mcpat",),
    )
    resolved_gem5_config = _resolve_existing_path(
        gem5_config,
        env_var=ENV_GEM5_CONFIG,
        fallback_paths=(DEFAULT_GEM5_CONFIG,),
    )
    resolved_meson = _resolve_command_or_executable(
        meson_binary,
        env_var=ENV_MESON_BINARY,
        command_candidates=("meson",),
    )
    resolved_ninja = _resolve_command_or_executable(
        ninja_binary,
        env_var=ENV_NINJA_BINARY,
        command_candidates=("ninja",),
    )
    resolved_opendcdiag = _resolve_existing_path(
        opendcdiag_root,
        env_var=ENV_OPENDCDIAG_ROOT,
        fallback_paths=(DEFAULT_OPENDCDIAG_ROOT,),
        directory=True,
    )
    return LocalToolResolution(
        compiler=resolved_compiler,
        qemu_user_binary=resolved_qemu_user,
        qemu_system_binary=resolved_qemu_system,
        gem5_binary=resolved_gem5,
        gem5_config=resolved_gem5_config,
        mcpat_binary=resolved_mcpat,
        meson_binary=resolved_meson,
        ninja_binary=resolved_ninja,
        opendcdiag_root=resolved_opendcdiag,
    )


def build_missing_steps(
    resolved: LocalToolResolution,
    *,
    profile: str = "sim",
    host: Optional[HostContext] = None,
    require_qemu_user: bool = True,
    require_qemu_system: bool = False,
    require_gem5: bool = True,
    require_gem5_config: bool = True,
    require_mcpat: bool = True,
    require_hardware_tools: bool = False,
) -> List[MissingStep]:
    steps: List[MissingStep] = []
    host = host or get_host_context()
    normalized_profile = str(profile).strip().lower()

    def add_step(step: MissingStep) -> None:
        if any(existing.step_id == step.step_id for existing in steps):
            return
        steps.append(step)

    if normalized_profile == "sim" and not host.is_linux_arm64:
        add_step(
            MissingStep(
                step_id="use_linux_arm_runner",
                detail=(
                    "The sim profile requires a Linux/aarch64 host "
                    "(Ubuntu 24.04 ARM is the supported baseline)."
                ),
                command=None,
                cwd=None,
                auto_build=False,
            )
        )

    if resolved.compiler is None:
        add_step(
            MissingStep(
                step_id="install_compiler",
                detail=(
                    "Install a usable ARM64 compiler. On Ubuntu 24.04 ARM, "
                    "`gcc` is sufficient; on other hosts expose `aarch64-linux-gnu-gcc`."
                ),
                command=[str((REPO_ROOT / "scripts" / "bootstrap_ubuntu_24_04_arm.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=False,
            )
        )

    if require_qemu_user and resolved.qemu_user_binary is None:
        if normalized_profile == "sim":
            add_step(
                MissingStep(
                    step_id="install_qemu_user",
                    detail="Install `qemu-user` so `qemu-aarch64` is available on PATH.",
                    command=[str((REPO_ROOT / "scripts" / "bootstrap_ubuntu_24_04_arm.sh").resolve())],
                    cwd=str(REPO_ROOT),
                    auto_build=False,
                )
            )
        else:
            add_step(
                MissingStep(
                    step_id="build_qemu",
                    detail="Build the repo-local QEMU binaries for both user and system mode.",
                    command=[str((REPO_ROOT / "scripts" / "build_qemu_headless.sh").resolve())],
                    cwd=str(REPO_ROOT),
                    auto_build=True,
                )
            )

    if require_qemu_system and resolved.qemu_system_binary is None:
        if normalized_profile == "sim":
            add_step(
                MissingStep(
                    step_id="install_qemu_system",
                    detail="Install `qemu-system-arm` so `qemu-system-aarch64` is available on PATH.",
                    command=[str((REPO_ROOT / "scripts" / "bootstrap_ubuntu_24_04_arm.sh").resolve())],
                    cwd=str(REPO_ROOT),
                    auto_build=False,
                )
            )
        else:
            add_step(
                MissingStep(
                    step_id="build_qemu",
                    detail="Build the repo-local QEMU binaries for both user and system mode.",
                    command=[str((REPO_ROOT / "scripts" / "build_qemu_headless.sh").resolve())],
                    cwd=str(REPO_ROOT),
                    auto_build=True,
                )
            )

    if require_gem5 and resolved.gem5_binary is None:
        add_step(
            MissingStep(
                step_id="build_gem5",
                detail="Build the repo-local gem5 ARM binary on the Linux ARM runner.",
                command=[str((REPO_ROOT / "scripts" / "build_gem5_linux_arm.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=normalized_profile == "sim" and host.is_linux_arm64,
            )
        )

    if require_mcpat and resolved.mcpat_binary is None:
        add_step(
            MissingStep(
                step_id="build_mcpat",
                detail="Build the repo-local McPAT binary.",
                command=[str((REPO_ROOT / "scripts" / "build_mcpat.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=True,
            )
        )

    if require_gem5_config and resolved.gem5_config is None:
        add_step(
            MissingStep(
                step_id="restore_gem5_config",
                detail="Restore the gem5 SE configuration file expected by the control plane.",
                command=None,
                cwd=None,
                auto_build=False,
            )
        )

    if require_hardware_tools and resolved.meson_binary is None:
        add_step(
            MissingStep(
                step_id="install_meson",
                detail="Install `meson` to enable local OpenDCDiag staging runs.",
                command=[str((REPO_ROOT / "scripts" / "bootstrap_ubuntu_24_04_arm.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=False,
            )
        )

    if require_hardware_tools and resolved.ninja_binary is None:
        add_step(
            MissingStep(
                step_id="install_ninja",
                detail="Install `ninja` to support `meson compile` on the local hardware lane.",
                command=[str((REPO_ROOT / "scripts" / "bootstrap_ubuntu_24_04_arm.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=False,
            )
        )

    if require_hardware_tools and resolved.opendcdiag_root is None:
        add_step(
            MissingStep(
                step_id="restore_opendcdiag",
                detail="Ensure the `opendcdiag` source tree is present in the monorepo.",
                command=None,
                cwd=None,
                auto_build=False,
            )
        )

    return steps
