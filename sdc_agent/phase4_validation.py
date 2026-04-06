#!/usr/bin/env python3
"""Real end-to-end Phase 4 validation using system-mode QEMU + gem5 + McPAT."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .differential import (
    fault_request_has_observed_injection,
    fault_request_requires_injection,
)
from .tooling import resolve_local_tools
from .outer_loop import FaultSpec, build_campaign_identity, plan_fault_matrix
from .phase2_validation import (
    DEFAULT_DB,
    DEFAULT_GEM5_BAREMETAL_CONFIG,
    DEFAULT_GEM5_BINARY,
    DEFAULT_MCPAT_BINARY,
    DEFAULT_OUTPUT_ROOT as DEFAULT_PHASE2_OUTPUT_ROOT,
    PROFILE_SIM_SAFE,
    _decode_metadata,
    _resolve_compiler,
    build_semihost_validation_elf,
    run_gem5_semihost_validation,
    run_qemu_system_golden,
    SAFE_BASELINE_ASM,
)
from .power_backends.mcpat_backend import McPATBackend
from .vault import SDCVault, VaultEntry


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "phase4-validation"


@dataclass(frozen=True)
class Phase4FaultRun:
    run_key: str
    fault_model: str
    fault_target: str
    fault_bit: Optional[int]
    fault_tick: Optional[int]
    result_status: str
    golden_digest: Optional[str]
    faulted_digest: Optional[str]
    artifact_dir: str
    execution_plane: str
    injection_observed: bool


@dataclass(frozen=True)
class Phase4ValidationResult:
    testcase_key: str
    campaign_key: str
    campaign_id: int
    total_runs: int
    sdc_hits: int
    matched_runs: int
    successful_runs: int
    fault_detection_rate: float
    repeatability_score: float
    outer_value_score: float
    summary_status: str
    qemu_golden_digest: Optional[str]
    mcpat_power_total: Optional[float]
    report_path: str


def _build_validation_entry(profile_name: str) -> VaultEntry:
    return VaultEntry(
        testcase_key="phase4-safe-baseline",
        asm_content=SAFE_BASELINE_ASM,
        target_name="armv8_common-armv8_common-aarch64_linux_gcc",
        policy_name="phase4_validation",
        ace_score=0.1,
        ibr_score=0.1,
        memory_pressure_score=0.0,
        risk_score=0.1,
        status="INNER_READY",
        metadata={
            "profile_name": profile_name,
            "requested_profile_name": profile_name,
            "effective_profile_name": profile_name,
            "phase4_validation": {
                "sample_kind": "safe_baseline_case",
            },
        },
    )


def _spec_run_key(spec: FaultSpec) -> str:
    payload = json.dumps(asdict(spec), sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _aggregate_fault_runs(
    *,
    base_score: float,
    runs: Sequence[Phase4FaultRun],
) -> Dict[str, Any]:
    total_runs = len(runs)
    sdc_hits = sum(1 for run in runs if run.result_status == "sdc_found")
    matched_runs = sum(1 for run in runs if run.result_status == "matched")
    successful_runs = sum(
        1 for run in runs if run.result_status in {"matched", "sdc_found"}
    )
    detection_rate = (sdc_hits / total_runs) if total_runs else 0.0
    repeatability_score = (successful_runs / total_runs) if total_runs else 0.0
    outer_value_score = base_score * repeatability_score * max(detection_rate, 1e-9)
    summary_status = "SDC_FOUND" if sdc_hits else "MATCHED" if matched_runs else "INVALID"
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


def _build_phase4_fault_request(
    spec: FaultSpec,
    gem5_result: Mapping[str, Any],
) -> Dict[str, Any]:
    payload = dict(asdict(spec))
    raw_fault_request = gem5_result.get("fault_request")
    if isinstance(raw_fault_request, Mapping):
        payload.update(dict(raw_fault_request))
    payload["implemented_in_script"] = bool(
        payload.get("implemented_in_script", gem5_result.get("implemented_in_script", False))
    )
    payload["injection_observed"] = bool(
        payload.get("injection_observed", gem5_result.get("injection_observed", False))
    )
    payload["execution_plane"] = str(
        payload.get("execution_plane")
        or gem5_result.get("fault_execution_plane")
        or ("none" if spec.fault_model == "none" else "phase4_no_injector")
    )
    return payload


def _classify_phase4_fault_run(
    *,
    qemu_result: Mapping[str, Any],
    gem5_result: Mapping[str, Any],
    fault_request: Mapping[str, Any],
) -> str:
    if int(qemu_result.get("returncode", -1)) != 0:
        return "golden_failed"
    if int(gem5_result.get("returncode", -1)) != 0:
        return "gem5_failed"
    if fault_request_requires_injection(fault_request) and not fault_request_has_observed_injection(
        fault_request
    ):
        return "no_injection"

    golden_digest = qemu_result.get("golden_digest")
    faulted_digest = gem5_result.get("gem5_digest")
    if golden_digest is None or faulted_digest is None:
        return "digest_missing"
    if str(golden_digest) != str(faulted_digest):
        return "sdc_found"
    return "matched"


def run_phase4_validation(
    *,
    db_path: Path = DEFAULT_DB,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    profile_name: str = PROFILE_SIM_SAFE,
    compiler: Optional[str] = None,
    qemu_binary: str | Path = "qemu-system-aarch64",
    gem5_binary: Path = DEFAULT_GEM5_BINARY,
    gem5_config: Path = DEFAULT_GEM5_BAREMETAL_CONFIG,
    mcpat_binary: Path = DEFAULT_MCPAT_BINARY,
    fault_models: Sequence[str] = ("register_bit_flip",),
    fault_targets: Sequence[str] = ("x0", "x1"),
    fault_bits: Sequence[Optional[int]] = (0, 1),
    fault_ticks: Sequence[Optional[int]] = (1000,),
    timeout: int = 30,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_tools = resolve_local_tools(
        compiler=compiler,
        qemu_system_binary=qemu_binary,
        gem5_binary=gem5_binary,
        gem5_config=gem5_config,
        mcpat_binary=mcpat_binary,
    )
    compiler = resolved_tools.compiler or _resolve_compiler()
    qemu_binary = Path(resolved_tools.qemu_system_binary or qemu_binary).resolve()
    gem5_binary = Path(resolved_tools.gem5_binary or gem5_binary).resolve()
    gem5_config = Path(resolved_tools.gem5_config or gem5_config).resolve()
    mcpat_binary = Path(resolved_tools.mcpat_binary or mcpat_binary).resolve()

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(_build_validation_entry(profile_name))
        row = vault.get_testcase("phase4-safe-baseline")
        if row is None:
            raise RuntimeError("Failed to create Phase 4 validation testcase.")
        testcase = dict(row)

    testcase_key = str(testcase["testcase_key"])
    metadata = _decode_metadata(testcase)
    build_dir = output_root / testcase_key
    build_artifacts = build_semihost_validation_elf(
        asm_content=str(testcase["asm_content"]),
        testcase_key=testcase_key,
        output_root=build_dir,
        compiler=compiler,
    )

    qemu_result = run_qemu_system_golden(
        qemu_binary=qemu_binary,
        elf_path=build_artifacts["elf_path"],
        timeout=timeout,
    )
    fault_specs = plan_fault_matrix(
        fault_models=fault_models,
        fault_targets=fault_targets,
        fault_bits=fault_bits,
        fault_ticks=fault_ticks,
    )
    matrix_hash, campaign_key = build_campaign_identity(fault_specs)

    with SDCVault(db_path) as vault:
        campaign_id = vault.upsert_fault_campaign(
            campaign_key,
            selector={
                "validation": "phase4_real_e2e",
                "testcase_key": testcase_key,
            },
            matrix_hash=matrix_hash,
            status="RUNNING",
            metadata={"fault_specs": [asdict(spec) for spec in fault_specs]},
        )

        run_records: List[Phase4FaultRun] = []
        latest_mcpat_power: Optional[float] = None
        for spec in fault_specs:
            run_key = _spec_run_key(spec)
            run_dir = build_dir / run_key
            gem5_outdir = run_dir / "gem5"
            gem5_result = run_gem5_semihost_validation(
                gem5_binary=gem5_binary,
                gem5_config=gem5_config,
                elf_path=build_artifacts["elf_path"],
                output_root=gem5_outdir,
                timeout=timeout,
            )
            fault_request = _build_phase4_fault_request(spec, gem5_result)
            result_status = _classify_phase4_fault_run(
                qemu_result=qemu_result,
                gem5_result=gem5_result,
                fault_request=fault_request,
            )
            mcpat_result: Dict[str, Any] = {}
            if int(gem5_result.get("returncode", -1)) == 0:
                mcpat_result = McPATBackend(
                    template_profile="arm64-kunpeng920",
                    mcpat_binary=mcpat_binary,
                ).run(gem5_outdir)
                latest_mcpat_power = float(mcpat_result["power_total"])
            result_json = run_dir / "result.json"
            run_payload = {
                "fault_spec": asdict(spec),
                "fault_request": fault_request,
                "qemu": qemu_result,
                "gem5": gem5_result,
                "mcpat": {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in mcpat_result.items()
                },
                "result_status": result_status,
                "fault_execution_plane": fault_request["execution_plane"],
            }
            result_json.parent.mkdir(parents=True, exist_ok=True)
            result_json.write_text(
                json.dumps(run_payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            vault.record_fault_run(
                campaign_id=campaign_id,
                testcase_key=testcase_key,
                fault_model=spec.fault_model,
                fault_target=spec.fault_target,
                fault_bit=spec.fault_bit,
                fault_tick=spec.fault_tick,
                golden_digest=qemu_result["golden_digest"],
                faulted_digest=gem5_result["gem5_digest"],
                result_status=result_status,
                metadata={
                    "artifact_dir": str(run_dir.resolve()),
                    "result_json": str(result_json.resolve()),
                    "fault_request": fault_request,
                    "fault_execution_plane": fault_request["execution_plane"],
                    "injection_observed": bool(fault_request["injection_observed"]),
                },
            )
            run_records.append(
                Phase4FaultRun(
                    run_key=run_key,
                    fault_model=spec.fault_model,
                    fault_target=spec.fault_target,
                    fault_bit=spec.fault_bit,
                    fault_tick=spec.fault_tick,
                    result_status=result_status,
                    golden_digest=qemu_result["golden_digest"],
                    faulted_digest=gem5_result["gem5_digest"],
                    artifact_dir=str(run_dir.resolve()),
                    execution_plane=str(fault_request["execution_plane"]),
                    injection_observed=bool(fault_request["injection_observed"]),
                )
            )

        aggregate = _aggregate_fault_runs(base_score=1.0, runs=run_records)
        metadata["outer_loop"] = {
            **aggregate,
            "campaign_key": campaign_key,
            "validation_mode": "phase4_real_e2e",
            "qemu_binary": str(qemu_binary),
            "gem5_binary": str(gem5_binary),
            "mcpat_binary": str(mcpat_binary),
        }
        vault.update_execution_result(
            testcase_key,
            qemu_golden_hash=qemu_result["golden_digest"],
            mcpat_power=latest_mcpat_power,
            status=aggregate["summary_status"],
            metadata=metadata,
        )
        vault.upsert_fault_campaign(
            campaign_key,
            selector={
                "validation": "phase4_real_e2e",
                "testcase_key": testcase_key,
            },
            matrix_hash=matrix_hash,
            status="COMPLETED",
            metadata={
                "fault_specs": [asdict(spec) for spec in fault_specs],
                "aggregate": aggregate,
                "fault_execution_plane": (
                    "phase4_real_e2e"
                    if any(run.injection_observed for run in run_records)
                    else "phase4_no_injector"
                ),
            },
        )
        campaign = vault.get_fault_campaign(campaign_key)
        if campaign is None:
            raise RuntimeError("Phase 4 validation campaign disappeared unexpectedly.")

    report = Phase4ValidationResult(
        testcase_key=testcase_key,
        campaign_key=campaign_key,
        campaign_id=int(campaign["campaign_id"]),
        total_runs=int(aggregate["total_runs"]),
        sdc_hits=int(aggregate["sdc_hits"]),
        matched_runs=int(aggregate["matched_runs"]),
        successful_runs=int(aggregate["successful_runs"]),
        fault_detection_rate=float(aggregate["fault_detection_rate"]),
        repeatability_score=float(aggregate["repeatability_score"]),
        outer_value_score=float(aggregate["outer_value_score"]),
        summary_status=str(aggregate["summary_status"]),
        qemu_golden_digest=qemu_result["golden_digest"],
        mcpat_power_total=latest_mcpat_power,
        report_path=str((build_dir / "phase4-validation.json").resolve()),
    )
    report_payload = {
        **asdict(report),
        "fault_specs": [asdict(spec) for spec in fault_specs],
        "fault_runs": [asdict(run) for run in run_records],
        "qemu": qemu_result,
        "fault_execution_plane": (
            "phase4_real_e2e"
            if any(run.injection_observed for run in run_records)
            else "phase4_no_injector"
        ),
    }
    report_path = Path(report.report_path)
    report_path.write_text(
        json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real Phase 4 end-to-end validation for multi-fault campaigns."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--profile", default=PROFILE_SIM_SAFE)
    parser.add_argument("--compiler", default=None)
    parser.add_argument("--qemu-binary", default="qemu-system-aarch64")
    parser.add_argument("--gem5-binary", type=Path, default=DEFAULT_GEM5_BINARY)
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_BAREMETAL_CONFIG)
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--fault-model", action="append", default=["register_bit_flip"])
    parser.add_argument("--fault-target", action="append", default=["x0", "x1"])
    parser.add_argument("--fault-bit", action="append", default=["0", "1"])
    parser.add_argument("--fault-tick", action="append", default=["1000"])
    parser.add_argument("--timeout", type=int, default=30)
    return parser


def _parse_optional_ints(values: Sequence[str]) -> List[Optional[int]]:
    parsed: List[Optional[int]] = []
    for value in values:
        if value.lower() == "none":
            parsed.append(None)
        else:
            parsed.append(int(value))
    return parsed


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_phase4_validation(
        db_path=args.db,
        output_root=args.output_root,
        profile_name=args.profile,
        compiler=args.compiler,
        qemu_binary=args.qemu_binary,
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        mcpat_binary=args.mcpat_binary,
        fault_models=tuple(args.fault_model),
        fault_targets=tuple(args.fault_target),
        fault_bits=_parse_optional_ints(args.fault_bit),
        fault_ticks=_parse_optional_ints(args.fault_tick),
        timeout=args.timeout,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["summary_status"] in {"MATCHED", "SDC_FOUND"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
