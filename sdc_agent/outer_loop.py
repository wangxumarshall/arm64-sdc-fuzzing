#!/usr/bin/env python3
"""Low-frequency outer-loop orchestrator for ARM64 SDC fault campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .campaign import resolve_source_path
from .differential import DEFAULT_GEM5_CONFIG, run_differential
from .materialize import materialize_testcase
from .preflight import DEFAULT_GEM5_BINARY, DEFAULT_MCPAT_BINARY, run_preflight
from .scheduler import FeedbackScheduler, RankedCandidate
from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "outer-loop"
DEFAULT_OUTER_STATUSES = ("INNER_READY", "POWER_READY", "GOLDEN_READY")


@dataclass(frozen=True)
class FaultSpec:
    fault_model: str
    fault_target: str
    fault_bit: Optional[int]
    fault_tick: Optional[int]


@dataclass(frozen=True)
class FaultRunResult:
    testcase_key: str
    run_key: str
    fault_model: str
    fault_target: str
    fault_bit: Optional[int]
    fault_tick: Optional[int]
    result_status: str
    golden_digest: Optional[str]
    faulted_digest: Optional[str]
    artifact_dir: str


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(row)
    raw_value = payload.get("metadata_json", "{}")
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(str(raw_value))


def plan_fault_matrix(
    *,
    fault_models: Sequence[str],
    fault_targets: Sequence[str],
    fault_bits: Sequence[Optional[int]],
    fault_ticks: Sequence[Optional[int]],
) -> List[FaultSpec]:
    specs: List[FaultSpec] = []
    unique: set[tuple[str, str, Optional[int], Optional[int]]] = set()

    models = list(fault_models) or ["register_bit_flip"]
    targets = list(fault_targets) or ["x0"]
    bits = list(fault_bits) or [0]
    ticks = list(fault_ticks) or [1000]

    for fault_model in models:
        if fault_model == "none":
            key = ("none", "", None, None)
            if key not in unique:
                unique.add(key)
                specs.append(FaultSpec(*key))
            continue
        for fault_target in targets:
            for fault_bit in bits:
                for fault_tick in ticks:
                    key = (fault_model, fault_target, fault_bit, fault_tick)
                    if key in unique:
                        continue
                    unique.add(key)
                    specs.append(FaultSpec(*key))
    return specs


def _spec_run_key(spec: FaultSpec) -> str:
    payload = json.dumps(asdict(spec), sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _update_outer_metadata(
    vault: SDCVault,
    testcase_key: str,
    *,
    campaign_key: str,
    aggregate: Mapping[str, Any],
) -> None:
    row = vault.get_testcase(testcase_key)
    if row is None:
        return
    metadata = _decode_metadata(row)
    metadata["outer_loop"] = dict(aggregate)
    metadata["outer_loop"]["campaign_key"] = campaign_key
    vault.update_execution_result(testcase_key, metadata=metadata)


def _aggregate_fault_results(
    candidate: RankedCandidate,
    fault_results: Sequence[FaultRunResult],
) -> Dict[str, Any]:
    total_runs = len(fault_results)
    sdc_hits = sum(1 for result in fault_results if result.result_status == "sdc_found")
    matched_runs = sum(1 for result in fault_results if result.result_status == "matched")
    successful_runs = sum(
        1 for result in fault_results if result.result_status in {"matched", "sdc_found"}
    )
    detection_rate = (sdc_hits / total_runs) if total_runs else 0.0
    repeatability_score = (successful_runs / total_runs) if total_runs else 0.0
    outer_value_score = candidate.fitness * detection_rate * repeatability_score

    if sdc_hits > 0:
        summary_status = "SDC_FOUND"
    elif matched_runs > 0:
        summary_status = "MATCHED"
    else:
        summary_status = "INVALID"

    return {
        "total_runs": total_runs,
        "sdc_hits": sdc_hits,
        "matched_runs": matched_runs,
        "successful_runs": successful_runs,
        "fault_detection_rate": detection_rate,
        "repeatability_score": repeatability_score,
        "outer_value_score": outer_value_score,
        "summary_status": summary_status,
    }


def run_outer_loop(
    *,
    db_path: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    limit: int = 1,
    source_root: Optional[Path] = None,
    process_statuses: Sequence[str] = DEFAULT_OUTER_STATUSES,
    fault_models: Sequence[str] = ("register_bit_flip",),
    fault_targets: Sequence[str] = ("x0",),
    fault_bits: Sequence[Optional[int]] = (0,),
    fault_ticks: Sequence[Optional[int]] = (1000,),
    dry_run: bool = False,
    skip_preflight: bool = False,
    compiler: str = "aarch64-linux-gnu-gcc",
    compiler_flags: Optional[List[str]] = None,
    qemu_binary: str = "qemu-aarch64",
    qemu_args: Optional[List[str]] = None,
    gem5_binary: str = str(DEFAULT_GEM5_BINARY),
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    gem5_args: Optional[List[str]] = None,
    gem5_cmd_flag: str = "auto",
    skip_mcpat: bool = False,
    mcpat_template_profile: str = "arm64-kunpeng920",
    mcpat_binary: Optional[Path] = DEFAULT_MCPAT_BINARY,
    timeout: int = 120,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    compiler_flags = list(compiler_flags or [])
    qemu_args = list(qemu_args or [])
    gem5_args = list(gem5_args or [])
    source_root = source_root.resolve() if source_root is not None else None

    preflight = None
    if not skip_preflight:
        preflight = run_preflight(
            compiler=compiler,
            qemu_binary=qemu_binary,
            gem5_binary=Path(gem5_binary),
            mcpat_binary=mcpat_binary or DEFAULT_MCPAT_BINARY,
            gem5_config=gem5_config,
            vault_path=db_path,
            check_build_deps=False,
        )
        if not dry_run and not preflight["ready"]:
            raise RuntimeError("Outer-loop preflight failed; refusing to execute.")

    scheduler = FeedbackScheduler()
    fault_specs = plan_fault_matrix(
        fault_models=fault_models,
        fault_targets=fault_targets,
        fault_bits=fault_bits,
        fault_ticks=fault_ticks,
    )
    campaign_key = hashlib.sha1(
        json.dumps([asdict(spec) for spec in fault_specs], sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    counts = {
        "selected": 0,
        "planned_runs": 0,
        "executed_runs": 0,
        "aggregated": 0,
        "source_missing": 0,
    }
    planned_runs: List[Dict[str, Any]] = []
    executed_runs: List[FaultRunResult] = []

    with SDCVault(db_path) as vault:
        campaign_id = vault.upsert_fault_campaign(
            campaign_key,
            selector={
                "statuses": list(process_statuses),
                "limit": limit,
            },
            matrix_hash=campaign_key,
            status="PLANNED" if dry_run else "RUNNING",
            metadata={"fault_specs": [asdict(spec) for spec in fault_specs]},
        )
        candidates = [
            candidate
            for candidate in scheduler.select_candidates(vault, limit * 4)
            if candidate.status in process_statuses
        ][:limit]
        counts["selected"] = len(candidates)

        for candidate in candidates:
            source_path = resolve_source_path(candidate, source_root)
            if (source_path is None or not source_path.exists()) and candidate.row.get("asm_content"):
                source_path = materialize_testcase(
                    vault,
                    candidate.testcase_key,
                    output_root=output_root / "materialized",
                )
            if source_path is None or not source_path.exists():
                counts["source_missing"] += 1
                continue

            testcase_fault_results: List[FaultRunResult] = []
            for spec in fault_specs:
                run_key = _spec_run_key(spec)
                artifact_dir = output_root / candidate.testcase_key / run_key
                artifact_dir.mkdir(parents=True, exist_ok=True)
                result_json = artifact_dir / "result.json"

                if dry_run:
                    counts["planned_runs"] += 1
                    planned_runs.append(
                        {
                            "testcase_key": candidate.testcase_key,
                            "run_key": run_key,
                            "source_path": str(source_path.resolve()),
                            "artifact_dir": str(artifact_dir.resolve()),
                            "fault_spec": asdict(spec),
                        }
                    )
                    continue

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
                    fault_model=spec.fault_model,
                    fault_target=spec.fault_target,
                    fault_bit=spec.fault_bit,
                    fault_tick=spec.fault_tick,
                    skip_gem5=False,
                    skip_mcpat=skip_mcpat,
                    mcpat_template_profile=mcpat_template_profile,
                    mcpat_binary=mcpat_binary,
                    timeout=timeout,
                )
                result_payload = result.to_dict()
                result_json.write_text(
                    json.dumps(result_payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                vault.record_fault_run(
                    campaign_id=campaign_id,
                    testcase_key=candidate.testcase_key,
                    fault_model=spec.fault_model,
                    fault_target=spec.fault_target,
                    fault_bit=spec.fault_bit,
                    fault_tick=spec.fault_tick,
                    golden_digest=result.golden_digest,
                    faulted_digest=result.faulted_digest,
                    result_status=result.status,
                    metadata={
                        "artifact_dir": str(artifact_dir.resolve()),
                        "result_json": str(result_json.resolve()),
                        "fault_request": result.fault_request or {},
                    },
                )
                run_record = FaultRunResult(
                    testcase_key=candidate.testcase_key,
                    run_key=run_key,
                    fault_model=spec.fault_model,
                    fault_target=spec.fault_target,
                    fault_bit=spec.fault_bit,
                    fault_tick=spec.fault_tick,
                    result_status=result.status,
                    golden_digest=result.golden_digest,
                    faulted_digest=result.faulted_digest,
                    artifact_dir=str(artifact_dir.resolve()),
                )
                testcase_fault_results.append(run_record)
                executed_runs.append(run_record)
                counts["executed_runs"] += 1

            if not dry_run and testcase_fault_results:
                aggregate = _aggregate_fault_results(candidate, testcase_fault_results)
                _update_outer_metadata(
                    vault,
                    candidate.testcase_key,
                    campaign_key=campaign_key,
                    aggregate=aggregate,
                )
                vault.mark_status(candidate.testcase_key, aggregate["summary_status"])
                counts["aggregated"] += 1

        if not dry_run:
            vault.upsert_fault_campaign(
                campaign_key,
                selector={
                    "statuses": list(process_statuses),
                    "limit": limit,
                },
                matrix_hash=campaign_key,
                status="COMPLETED",
                metadata={
                    "fault_specs": [asdict(spec) for spec in fault_specs],
                    "counts": counts,
                },
            )

    return {
        "ok": True,
        "dry_run": dry_run,
        "preflight": preflight,
        "campaign_key": campaign_key,
        "fault_specs": [asdict(spec) for spec in fault_specs],
        "counts": counts,
        "planned_runs": planned_runs,
        "executed_runs": [asdict(run) for run in executed_runs],
    }


def _parse_optional_ints(values: Sequence[str]) -> List[Optional[int]]:
    parsed: List[Optional[int]] = []
    for value in values:
        if value.lower() == "none":
            parsed.append(None)
        else:
            parsed.append(int(value))
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the low-frequency outer loop for ARM64 SDC fault campaigns."
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--process-status", action="append", default=[])
    parser.add_argument("--fault-model", action="append", default=["register_bit_flip"])
    parser.add_argument("--fault-target", action="append", default=["x0"])
    parser.add_argument("--fault-bit", action="append", default=["0"])
    parser.add_argument("--fault-tick", action="append", default=["1000"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--compiler", default="aarch64-linux-gnu-gcc")
    parser.add_argument("--compiler-flag", action="append", default=[])
    parser.add_argument("--qemu-binary", default="qemu-aarch64")
    parser.add_argument("--qemu-arg", action="append", default=[])
    parser.add_argument("--gem5-binary", default=str(DEFAULT_GEM5_BINARY))
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    parser.add_argument("--gem5-arg", action="append", default=[])
    parser.add_argument("--gem5-cmd-flag", default="auto")
    parser.add_argument("--skip-mcpat", action="store_true")
    parser.add_argument("--mcpat-template-profile", default="arm64-kunpeng920")
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--timeout", type=int, default=120)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_outer_loop(
        db_path=args.db,
        output_root=args.output_root,
        limit=args.limit,
        source_root=args.source_root,
        process_statuses=tuple(args.process_status or DEFAULT_OUTER_STATUSES),
        fault_models=tuple(args.fault_model),
        fault_targets=tuple(args.fault_target),
        fault_bits=_parse_optional_ints(args.fault_bit),
        fault_ticks=_parse_optional_ints(args.fault_tick),
        dry_run=args.dry_run,
        skip_preflight=args.skip_preflight,
        compiler=args.compiler,
        compiler_flags=list(args.compiler_flag),
        qemu_binary=args.qemu_binary,
        qemu_args=list(args.qemu_arg),
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        gem5_args=list(args.gem5_arg),
        gem5_cmd_flag=args.gem5_cmd_flag,
        skip_mcpat=args.skip_mcpat,
        mcpat_template_profile=args.mcpat_template_profile,
        mcpat_binary=args.mcpat_binary,
        timeout=args.timeout,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
