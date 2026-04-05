#!/usr/bin/env python3
"""Shared local tool resolution for the ARM64 SDC workflow."""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEM5_BINARY = REPO_ROOT / "gem5" / "build" / "ARM" / "gem5.opt"
DEFAULT_GEM5_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "sdc_kunpeng920_se.py"
DEFAULT_GEM5_BAREMETAL_CONFIG = REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "baremetal.py"
DEFAULT_MCPAT_BINARY = REPO_ROOT / "mcpat" / "mcpat"
DEFAULT_OPENDCDIAG_ROOT = REPO_ROOT / "opendcdiag"
DEFAULT_QEMU_SYSTEM_BINARY = REPO_ROOT / "qemu" / "build" / "qemu-system-aarch64"
DEFAULT_QEMU_USER_BINARY = REPO_ROOT / "qemu" / "build" / "qemu-aarch64"
DEFAULT_CONDA_COMPILER = Path("/Users/wangxu/anaconda3/bin/aarch64-conda-linux-gnu-gcc")


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


def _looks_like_path(value: str) -> bool:
    return os.sep in value or value.startswith(".")


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_command_or_executable(
    explicit: Optional[str | Path],
    *,
    repo_candidates: Sequence[Path] = (),
    command_candidates: Sequence[str] = (),
    fallback_paths: Sequence[Path] = (),
) -> Optional[str]:
    if explicit is not None:
        raw = str(explicit)
        if _looks_like_path(raw):
            path = Path(raw).expanduser()
            if _is_executable(path):
                return str(path.resolve())
            return None
        resolved = shutil.which(raw)
        return resolved or None

    for candidate in repo_candidates:
        if _is_executable(candidate):
            return str(candidate.resolve())

    for candidate in command_candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    for candidate in fallback_paths:
        if _is_executable(candidate):
            return str(candidate.resolve())

    return None


def _resolve_existing_path(
    explicit: Optional[str | Path],
    *,
    fallback_paths: Sequence[Path] = (),
    directory: bool = False,
) -> Optional[str]:
    if explicit is not None:
        path = Path(str(explicit)).expanduser()
        if (path.is_dir() if directory else path.exists()):
            return str(path.resolve())
        return None

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
) -> LocalToolResolution:
    resolved_compiler = _resolve_command_or_executable(
        compiler,
        command_candidates=("aarch64-linux-gnu-gcc", "aarch64-conda-linux-gnu-gcc"),
        fallback_paths=(DEFAULT_CONDA_COMPILER,),
    )
    resolved_qemu_user = _resolve_command_or_executable(
        qemu_user_binary,
        repo_candidates=(DEFAULT_QEMU_USER_BINARY,),
        command_candidates=("qemu-aarch64",),
    )
    resolved_qemu_system = _resolve_command_or_executable(
        qemu_system_binary,
        repo_candidates=(DEFAULT_QEMU_SYSTEM_BINARY,),
        command_candidates=("qemu-system-aarch64",),
    )
    resolved_gem5 = _resolve_command_or_executable(
        gem5_binary,
        repo_candidates=(DEFAULT_GEM5_BINARY,),
        command_candidates=("gem5.opt",),
    )
    resolved_mcpat = _resolve_command_or_executable(
        mcpat_binary,
        repo_candidates=(DEFAULT_MCPAT_BINARY,),
        command_candidates=("mcpat",),
    )
    resolved_gem5_config = _resolve_existing_path(
        gem5_config,
        fallback_paths=(DEFAULT_GEM5_CONFIG,),
    )
    resolved_meson = _resolve_command_or_executable(
        meson_binary,
        command_candidates=("meson",),
    )
    resolved_ninja = _resolve_command_or_executable(
        ninja_binary,
        command_candidates=("ninja",),
    )
    resolved_opendcdiag = _resolve_existing_path(
        opendcdiag_root,
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
    require_qemu_user: bool = True,
    require_qemu_system: bool = False,
    require_mcpat: bool = True,
    require_hardware_tools: bool = False,
) -> List[MissingStep]:
    steps: List[MissingStep] = []

    def add_step(step: MissingStep) -> None:
        if any(existing.step_id == step.step_id for existing in steps):
            return
        steps.append(step)

    if resolved.compiler is None:
        add_step(
            MissingStep(
                step_id="install_compiler",
                detail="Install or expose an AArch64 cross compiler on PATH.",
                command=None,
                cwd=None,
                auto_build=False,
            )
        )
    if require_qemu_user and resolved.qemu_user_binary is None:
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
        add_step(
            MissingStep(
                step_id="build_qemu",
                detail="Build the repo-local QEMU binaries for both user and system mode.",
                command=[str((REPO_ROOT / "scripts" / "build_qemu_headless.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=True,
            )
        )
    if resolved.gem5_binary is None:
        add_step(
            MissingStep(
                step_id="build_gem5",
                detail="Build the repo-local gem5 ARM binary.",
                command=[str((REPO_ROOT / "scripts" / "build_gem5_noninteractive.sh").resolve())],
                cwd=str(REPO_ROOT),
                auto_build=True,
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
    if resolved.gem5_config is None:
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
                command=None,
                cwd=None,
                auto_build=False,
            )
        )
    if require_hardware_tools and resolved.ninja_binary is None:
        add_step(
            MissingStep(
                step_id="install_ninja",
                detail="Install `ninja` to support `meson compile` on the local hardware lane.",
                command=None,
                cwd=None,
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
