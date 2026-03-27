#!/usr/bin/env python3
"""Preflight checks for the ARM64 SDC fuzzing toolchain."""

from __future__ import annotations

import argparse
import json
import shutil
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


def check_command(name: str, *, required: bool = True) -> PreflightCheck:
    resolved = shutil.which(name)
    return PreflightCheck(
        name=name,
        ok=resolved is not None,
        required=required,
        detail="found" if resolved else "missing from PATH",
        path=resolved,
    )


def check_path(
    name: str,
    path: Path,
    *,
    required: bool = True,
    executable: bool = False,
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
    )


def run_preflight(
    *,
    compiler: str = "aarch64-linux-gnu-gcc",
    qemu_binary: str = "qemu-aarch64",
    gem5_binary: Path = DEFAULT_GEM5_BINARY,
    mcpat_binary: Path = DEFAULT_MCPAT_BINARY,
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    vault_path: Path = DEFAULT_VAULT,
) -> dict:
    checks: List[PreflightCheck] = [
        check_command(compiler, required=True),
        check_command(qemu_binary, required=True),
        check_path("gem5_binary", gem5_binary, required=True, executable=True),
        check_path("mcpat_binary", mcpat_binary, required=True, executable=True),
        check_path("gem5_config", gem5_config, required=True),
        check_path("vault_parent", vault_path.parent, required=False),
    ]

    ready = all(check.ok for check in checks if check.required)
    return {
        "ready": ready,
        "repo_root": str(REPO_ROOT),
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
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
