#!/usr/bin/env python3
"""Outer-loop campaign runner for the ARM64 SDC fuzzing flow."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .differential import (
    DEFAULT_GEM5_CONFIG,
    DEFAULT_GEM5_OUTDIR,
    run_differential,
)
from .materialize import materialize_testcase
from .preflight import (
    DEFAULT_GEM5_BINARY,
    DEFAULT_MCPAT_BINARY,
    run_preflight,
)
from .scheduler import FeedbackScheduler, RankedCandidate
from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "campaign"


@dataclass(frozen=True)
class CampaignRun:
    testcase_key: str
    source_path: Optional[str]
    action: str
    scheduler_status: str
    fitness: float
    result_status: Optional[str] = None
    result_json: Optional[str] = None
    artifact_dir: Optional[str] = None
    error: Optional[str] = None


def _load_metadata(metadata_json: Any) -> Dict[str, Any]:
    if isinstance(metadata_json, dict):
        return dict(metadata_json)
    if metadata_json in (None, ""):
        return {}
    return json.loads(str(metadata_json))


def resolve_source_path(
    candidate: RankedCandidate, source_root: Optional[Path]
) -> Optional[Path]:
    explicit = candidate.metadata.get("source_path")
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    if source_root is None:
        return None
    return (source_root / f"{candidate.testcase_key}.c").resolve()


def _update_campaign_metadata(
    vault: SDCVault,
    testcase_key: str,
    *,
    source_path: Path,
    artifact_dir: Path,
    result_json: Path,
) -> None:
    row = vault.get_testcase(testcase_key)
    if row is None:
        return
    metadata = _load_metadata(row["metadata_json"])
    metadata["source_path"] = str(source_path)
    metadata["campaign"] = {
        "artifact_dir": str(artifact_dir),
        "result_json": str(result_json),
    }
    vault.update_execution_result(testcase_key, metadata=metadata)


def execute_campaign(
    *,
    db_path: Path,
    limit: int,
    source_root: Optional[Path],
    output_root: Path,
    dry_run: bool,
    skip_preflight: bool,
    compiler: str,
    compiler_flags: List[str],
    qemu_binary: str,
    qemu_args: List[str],
    gem5_binary: str,
    gem5_config: Path,
    gem5_args: List[str],
    gem5_cmd_flag: str,
    fault_model: str,
    fault_target: str,
    fault_bit: Optional[int],
    fault_tick: Optional[int],
    skip_gem5: bool,
    skip_mcpat: bool,
    mcpat_template_profile: str,
    mcpat_binary: Optional[Path],
    timeout: int,
) -> Dict[str, Any]:
    source_root = source_root.resolve() if source_root is not None else None
    output_root = output_root.resolve()
    preflight = None
    if not skip_preflight:
        preflight = run_preflight(
            compiler=compiler,
            qemu_binary=qemu_binary,
            gem5_binary=Path(gem5_binary),
            mcpat_binary=mcpat_binary or DEFAULT_MCPAT_BINARY,
            gem5_config=gem5_config,
            vault_path=db_path,
            require_gem5=False if skip_gem5 else None,
            require_mcpat=False if skip_gem5 or skip_mcpat else None,
        )
        if not dry_run and not preflight["ready"]:
            raise RuntimeError("Preflight checks failed; refusing to execute campaign.")

    scheduler = FeedbackScheduler()
    runs: List[CampaignRun] = []
    counts = {
        "selected": 0,
        "planned": 0,
        "executed": 0,
        "source_missing": 0,
    }

    with SDCVault(db_path) as vault:
        candidates = scheduler.select_candidates(vault, limit)
        counts["selected"] = len(candidates)
        effective_fault_model = "none" if skip_gem5 else fault_model
        effective_fault_target = "" if skip_gem5 else fault_target
        effective_fault_bit = None if skip_gem5 else fault_bit
        effective_fault_tick = None if skip_gem5 else fault_tick

        for candidate in candidates:
            source_path = resolve_source_path(candidate, source_root)
            if (source_path is None or not source_path.exists()) and candidate.row.get(
                "asm_content"
            ):
                source_path = materialize_testcase(
                    vault,
                    candidate.testcase_key,
                    output_root=output_root / "materialized",
                )

            if source_path is None or not source_path.exists():
                counts["source_missing"] += 1
                runs.append(
                    CampaignRun(
                        testcase_key=candidate.testcase_key,
                        source_path=str(source_path) if source_path else None,
                        action="source_missing",
                        scheduler_status=candidate.status,
                        fitness=candidate.fitness,
                        error="No renderable source path is available for this testcase.",
                    )
                )
                continue

            artifact_dir = output_root / candidate.testcase_key
            result_json = artifact_dir / "result.json"
            if dry_run:
                counts["planned"] += 1
                runs.append(
                    CampaignRun(
                        testcase_key=candidate.testcase_key,
                        source_path=str(source_path),
                        action="planned",
                        scheduler_status=candidate.status,
                        fitness=candidate.fitness,
                        artifact_dir=str(artifact_dir),
                        result_json=str(result_json),
                    )
                )
                continue

            artifact_dir.mkdir(parents=True, exist_ok=True)
            result = run_differential(
                source=source_path,
                elf=artifact_dir / f"{candidate.testcase_key}.elf",
                compiler=compiler,
                compiler_flags=compiler_flags,
                qemu_binary=qemu_binary,
                qemu_args=qemu_args,
                gem5_binary=gem5_binary,
                gem5_config=gem5_config,
                gem5_outdir=artifact_dir / "gem5",
                gem5_args=gem5_args,
                gem5_cmd_flag=gem5_cmd_flag,
                fault_model=effective_fault_model,
                fault_target=effective_fault_target,
                fault_bit=effective_fault_bit,
                fault_tick=effective_fault_tick,
                skip_gem5=skip_gem5,
                skip_mcpat=skip_mcpat,
                mcpat_template_profile=mcpat_template_profile,
                mcpat_binary=mcpat_binary,
                timeout=timeout,
            )
            payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
            result_json.write_text(payload + "\n", encoding="utf-8")
            updated = scheduler.record_result(vault, candidate.testcase_key, result.to_dict())
            _update_campaign_metadata(
                vault,
                candidate.testcase_key,
                source_path=source_path,
                artifact_dir=artifact_dir,
                result_json=result_json,
            )
            counts["executed"] += 1
            runs.append(
                CampaignRun(
                    testcase_key=candidate.testcase_key,
                    source_path=str(source_path),
                    action="executed",
                    scheduler_status=updated.status,
                    fitness=updated.fitness,
                    result_status=result.status,
                    artifact_dir=str(artifact_dir),
                    result_json=str(result_json),
                )
            )

    ok = dry_run or skip_preflight or bool(preflight and preflight["ready"])
    if not dry_run and counts["source_missing"] > 0:
        ok = False

    return {
        "ok": ok,
        "dry_run": dry_run,
        "preflight": preflight,
        "counts": counts,
        "runs": [asdict(run) for run in runs],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select, execute, and record ARM64 SDC campaign candidates."
    )
    parser.add_argument("--db", type=Path, required=True, help="Vault database path.")
    parser.add_argument("--limit", type=int, default=1, help="Max candidates to run.")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Optional directory containing <testcase_key>.c files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Campaign artifact directory.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan without executing.")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip local toolchain readiness checks.",
    )
    parser.add_argument("--compiler", default="aarch64-linux-gnu-gcc")
    parser.add_argument("--compiler-flag", action="append", default=[])
    parser.add_argument("--qemu-binary", default="qemu-aarch64")
    parser.add_argument("--qemu-arg", action="append", default=[])
    parser.add_argument("--gem5-binary", default=str(DEFAULT_GEM5_BINARY))
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    parser.add_argument("--gem5-arg", action="append", default=[])
    parser.add_argument("--gem5-cmd-flag", default="auto")
    parser.add_argument("--fault-model", default="none")
    parser.add_argument("--fault-target", default="")
    parser.add_argument("--fault-bit", type=int, default=None)
    parser.add_argument("--fault-tick", type=int, default=None)
    parser.add_argument("--skip-gem5", action="store_true")
    parser.add_argument("--skip-mcpat", action="store_true")
    parser.add_argument(
        "--mcpat-template-profile",
        default="arm64-kunpeng920",
    )
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        payload = execute_campaign(
            db_path=args.db,
            limit=args.limit,
            source_root=args.source_root,
            output_root=args.output_root,
            dry_run=args.dry_run,
            skip_preflight=args.skip_preflight,
            compiler=args.compiler,
            compiler_flags=args.compiler_flag,
            qemu_binary=args.qemu_binary,
            qemu_args=args.qemu_arg,
            gem5_binary=args.gem5_binary,
            gem5_config=args.gem5_config,
            gem5_args=args.gem5_arg,
            gem5_cmd_flag=args.gem5_cmd_flag,
            fault_model=args.fault_model,
            fault_target=args.fault_target,
            fault_bit=args.fault_bit,
            fault_tick=args.fault_tick,
            skip_gem5=args.skip_gem5,
            skip_mcpat=args.skip_mcpat,
            mcpat_template_profile=args.mcpat_template_profile,
            mcpat_binary=args.mcpat_binary,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        output = json.dumps(payload, indent=2, ensure_ascii=False)
        print(output)
        if args.json_out is not None:
            args.json_out.write_text(output + "\n", encoding="utf-8")
        return 1

    output = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
