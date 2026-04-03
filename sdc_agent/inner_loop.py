#!/usr/bin/env python3
"""High-frequency inner-loop orchestrator for ARM64 SDC fuzzing."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .differential import (
    DEFAULT_GEM5_CONFIG,
    DifferentialResult,
    run_differential,
)
from .generation import (
    DEFAULT_POLICY,
    DEFAULT_TARGET,
    DEFAULT_WRAPPER,
    generate_batch,
)
from .materialize import materialize_testcase
from .preflight import (
    DEFAULT_GEM5_BINARY,
    DEFAULT_MCPAT_BINARY,
    check_command,
    check_path,
)
from .vault import SDCVault

bootstrap_done = False
try:
    from microprobe.driver.genetic import EvolutionConfig, SDCFuzzingGeneticDriver

    bootstrap_done = True
except Exception:  # pragma: no cover - imported lazily in some environments
    EvolutionConfig = None  # type: ignore[assignment]
    SDCFuzzingGeneticDriver = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "inner-loop"
DEFAULT_PROCESS_STATUSES = ("STATIC_DONE", "PENDING")


@dataclass(frozen=True)
class InnerLoopCaseResult:
    testcase_key: str
    source_path: Optional[str]
    artifact_dir: Optional[str]
    power_requested: bool
    inner_status: str
    result_status: Optional[str] = None
    golden_digest: Optional[str] = None
    power_total: Optional[float] = None
    source_cache_hit: bool = False
    elf_cache_hit: bool = False
    golden_cache_hit: bool = False
    error: Optional[str] = None


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw_value = row.get("metadata_json", "{}")
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(str(raw_value))


def _jsonable_command(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    return {
        "command": list(payload.get("command", [])),
        "returncode": payload.get("returncode"),
        "timed_out": bool(payload.get("timed_out", False)),
        "stdout": payload.get("stdout", ""),
        "stderr": payload.get("stderr", ""),
        "status": "ok" if payload.get("returncode") == 0 else "failed",
    }


def _merge_metadata(base: Mapping[str, Any], updates: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_metadata(dict(merged[key]), value)
        elif isinstance(value, Mapping):
            merged[key] = _merge_metadata({}, value)
        else:
            merged[key] = value
    return merged


def _resolve_source_path(
    vault: SDCVault,
    testcase_key: str,
    metadata: Mapping[str, Any],
    *,
    output_root: Path,
) -> tuple[Path, bool]:
    explicit = metadata.get("source_path")
    if explicit:
        source_path = Path(str(explicit)).expanduser().resolve()
        if source_path.exists():
            return source_path, True
    return materialize_testcase(vault, testcase_key, output_root=output_root), False


def _cache_flags(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    source_cache_hit: bool,
    elf_path: Path,
) -> Dict[str, Any]:
    execution = metadata.get("execution", {})
    if isinstance(execution, Mapping):
        execution = dict(execution)
    else:
        execution = {}
    compile_meta = execution.get("compile", {})
    qemu_meta = execution.get("qemu", {})
    if not isinstance(compile_meta, Mapping):
        compile_meta = {}
    if not isinstance(qemu_meta, Mapping):
        qemu_meta = {}

    elf_cache_hit = bool(
        elf_path.exists()
        and compile_meta.get("status") == "ok"
    )
    cached_golden_digest = (
        candidate.get("qemu_golden_hash")
        or metadata.get("golden_digest")
    )
    golden_cache_hit = bool(
        elf_cache_hit
        and cached_golden_digest
        and qemu_meta.get("status") == "ok"
    )
    return {
        "source_cache_hit": source_cache_hit,
        "elf_cache_hit": elf_cache_hit,
        "golden_cache_hit": golden_cache_hit,
        "cached_golden_digest": str(cached_golden_digest) if cached_golden_digest else None,
    }


def _inner_status_from_result(
    result: DifferentialResult,
    *,
    power_requested: bool,
) -> str:
    if result.compile.returncode != 0:
        return "INVALID"
    if result.qemu.returncode != 0 or result.golden_digest is None:
        return "INVALID"
    if not power_requested:
        return "GOLDEN_READY"
    if result.gem5 is None:
        return "GOLDEN_READY"
    if result.gem5.timed_out:
        return "TIMEOUT"
    if result.gem5.returncode != 0:
        return "CRASHED"
    if result.status == "sdc_found":
        return "INVALID"
    if result.status == "digest_missing":
        return "INVALID"
    if result.mcpat is not None:
        return "INNER_READY"
    return "POWER_READY"


def _build_case_metadata(
    prior_metadata: Mapping[str, Any],
    *,
    source_path: Path,
    artifact_dir: Path,
    gem5_outdir: Path,
    result: DifferentialResult,
    power_requested: bool,
    inner_status: str,
    cache_flags: Mapping[str, Any],
) -> Dict[str, Any]:
    power_total = None
    if result.mcpat is not None:
        power_total = result.mcpat.get("power_total")

    fault_request = result.fault_request or {}
    if str(fault_request.get("fault_model", "") or "").strip().lower() == "none":
        fault_request = {}

    updates: Dict[str, Any] = {
        "source_path": str(source_path.resolve()),
        "golden_digest": result.golden_digest,
        "inner_loop": {
            "power_requested": power_requested,
            "inner_status": inner_status,
            "result_status": result.status,
            "artifact_dir": str(artifact_dir.resolve()),
            "gem5_outdir": str(gem5_outdir.resolve()),
            "source_path": str(source_path.resolve()),
            "golden_digest": result.golden_digest,
            "gem5_digest": result.faulted_digest,
            "power_total": power_total,
            "mcpat_error": result.mcpat_error,
            "source_cache_hit": bool(cache_flags.get("source_cache_hit", False)),
            "elf_cache_hit": bool(cache_flags.get("elf_cache_hit", False)),
            "golden_cache_hit": bool(cache_flags.get("golden_cache_hit", False)),
        },
        "execution": {
            "compile": _jsonable_command(result.compile.to_dict()),
            "qemu": _jsonable_command(result.qemu.to_dict()),
            "gem5": _jsonable_command(result.gem5.to_dict()) if result.gem5 is not None else {},
        },
        "mcpat": result.mcpat or {},
        "fault_request": fault_request,
    }

    if result.gem5 is not None:
        updates["inner_loop"]["gem5_returncode"] = result.gem5.returncode
    return _merge_metadata(prior_metadata, updates)


def _select_candidates(
    vault: SDCVault,
    *,
    limit: int,
    statuses: Sequence[str],
) -> List[Mapping[str, Any]]:
    rows = vault.fetch_top_k_risky(limit, statuses=statuses)
    return [dict(row) for row in rows]


def _run_inner_preflight(
    *,
    compiler: str,
    qemu_binary: str,
    gem5_binary: str,
    gem5_config: Path,
    mcpat_binary: Optional[Path],
    require_power: bool,
) -> Dict[str, Any]:
    checks = [
        asdict(check_command(compiler, required=True)),
        asdict(check_command(qemu_binary, required=True)),
    ]
    if require_power:
        checks.extend(
            [
                asdict(check_path("gem5_binary", Path(gem5_binary), required=True, executable=True)),
                asdict(check_path("gem5_config", gem5_config, required=True)),
                asdict(
                    check_path(
                        "mcpat_binary",
                        mcpat_binary or DEFAULT_MCPAT_BINARY,
                        required=True,
                        executable=True,
                    )
                ),
            ]
        )
    ready = all(item["ok"] for item in checks if item["required"])
    return {
        "ready": ready,
        "checks": checks,
    }


def _run_evolution(
    *,
    db_path: Path,
    output_root: Path,
    wrapper_name: str,
    sequence_length: int,
    benchmark_size: int,
    dependency_distance: int,
    strict_validation: bool,
    parent_limit: int,
    offspring_per_parent: int,
    max_offspring: int,
) -> Dict[str, Any]:
    if not bootstrap_done or EvolutionConfig is None or SDCFuzzingGeneticDriver is None:
        raise RuntimeError("Microprobe genetic driver is unavailable in this environment.")

    config = EvolutionConfig(
        parent_limit=parent_limit,
        offspring_per_parent=offspring_per_parent,
        max_offspring=max_offspring,
        sequence_length=sequence_length,
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        strict_validation=strict_validation,
        wrapper_name=wrapper_name,
    )
    driver = SDCFuzzingGeneticDriver(config=config)
    with SDCVault(db_path) as vault:
        records = driver.evolve(
            vault,
            output_dir=output_root / "evolved",
            parent_limit=parent_limit,
        )
    return {
        "emitted": len(records),
        "records": [asdict(record) for record in records],
    }


def run_inner_loop(
    *,
    db_path: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    generate_count: int = 0,
    generate_jobs: int = 1,
    process_limit: int = 8,
    power_limit: int = 4,
    process_statuses: Sequence[str] = DEFAULT_PROCESS_STATUSES,
    target: str = DEFAULT_TARGET,
    policy: str = DEFAULT_POLICY,
    wrapper: str = DEFAULT_WRAPPER,
    sequence_length: int = 8,
    benchmark_size: int = 64,
    dependency_distance: int = 1,
    strict_validation: bool = False,
    compiler: str = "aarch64-linux-gnu-gcc",
    qemu_binary: str = "qemu-aarch64",
    gem5_binary: str = str(DEFAULT_GEM5_BINARY),
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    mcpat_binary: Optional[Path] = DEFAULT_MCPAT_BINARY,
    skip_power: bool = False,
    skip_preflight: bool = False,
    timeout: int = 120,
    enable_evolution: bool = True,
    parent_limit: int = 4,
    offspring_per_parent: int = 2,
    max_offspring: int = 8,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    generation_payload: Optional[Dict[str, Any]] = None
    if generate_count > 0:
        generation_payload = generate_batch(
            db_path=db_path,
            target=target,
            policy=policy,
            wrapper=wrapper,
            count=generate_count,
            jobs=generate_jobs,
            sequence_length=sequence_length,
            benchmark_size=benchmark_size,
            dependency_distance=dependency_distance,
            strict_validation=strict_validation,
            output_dir=output_root / "generated",
        )
        generated_keys = generation_payload.get("testcase_keys", [])
        if generated_keys:
            with SDCVault(db_path) as generation_vault:
                for testcase_key in generated_keys:
                    row = generation_vault.get_testcase(testcase_key)
                    if row is not None and row["status"] == "PENDING":
                        generation_vault.mark_status(testcase_key, "STATIC_DONE")

    preflight = None
    require_power = not skip_power and power_limit > 0
    if not skip_preflight:
        preflight = _run_inner_preflight(
            compiler=compiler,
            qemu_binary=qemu_binary,
            gem5_binary=gem5_binary,
            gem5_config=gem5_config,
            mcpat_binary=mcpat_binary,
            require_power=require_power,
        )
        if not preflight["ready"]:
            raise RuntimeError("Inner-loop preflight failed; refusing to execute.")

    case_results: List[InnerLoopCaseResult] = []
    counts = {
        "selected": 0,
        "processed": 0,
        "static_done": 0,
        "golden_ready": 0,
        "power_ready": 0,
        "inner_ready": 0,
        "invalid": 0,
        "timed_out": 0,
        "crashed": 0,
        "cached_source": 0,
        "cached_elf": 0,
        "cached_golden": 0,
    }

    with SDCVault(db_path) as vault:
        candidates = _select_candidates(
            vault,
            limit=process_limit,
            statuses=tuple(process_statuses),
        )
        counts["selected"] = len(candidates)

        for index, candidate in enumerate(candidates):
            testcase_key = str(candidate["testcase_key"])
            candidate_output = output_root / testcase_key
            candidate_output.mkdir(parents=True, exist_ok=True)
            metadata = _decode_metadata(candidate)
            source_path, source_cache_hit = _resolve_source_path(
                vault,
                testcase_key,
                metadata,
                output_root=output_root / "materialized",
            )
            elf_path = candidate_output / f"{testcase_key}.elf"
            cache_flags = _cache_flags(
                candidate,
                metadata,
                source_cache_hit=source_cache_hit,
                elf_path=elf_path,
            )
            power_requested = (not skip_power) and index < power_limit
            counts["static_done"] += 1 if candidate.get("status") == "STATIC_DONE" else 0
            counts["cached_source"] += 1 if cache_flags["source_cache_hit"] else 0
            counts["cached_elf"] += 1 if cache_flags["elf_cache_hit"] else 0
            counts["cached_golden"] += 1 if cache_flags["golden_cache_hit"] else 0

            try:
                result = run_differential(
                    source=source_path,
                    elf=elf_path,
                    skip_compile=bool(cache_flags["elf_cache_hit"]),
                    skip_qemu=bool(cache_flags["golden_cache_hit"]),
                    cached_golden_digest=cache_flags["cached_golden_digest"],
                    compiler=compiler,
                    qemu_binary=qemu_binary,
                    gem5_binary=gem5_binary,
                    gem5_config=gem5_config,
                    gem5_outdir=candidate_output / "gem5",
                    fault_model="none",
                    fault_target="",
                    skip_gem5=not power_requested,
                    skip_mcpat=not power_requested,
                    mcpat_binary=mcpat_binary,
                    timeout=timeout,
                )
                inner_status = _inner_status_from_result(
                    result,
                    power_requested=power_requested,
                )
                updated_metadata = _build_case_metadata(
                    metadata,
                    source_path=source_path,
                    artifact_dir=candidate_output,
                    gem5_outdir=candidate_output / "gem5",
                    result=result,
                    power_requested=power_requested,
                    inner_status=inner_status,
                    cache_flags=cache_flags,
                )
                mcpat_power = None
                if result.mcpat is not None and result.mcpat.get("power_total") is not None:
                    mcpat_power = float(result.mcpat["power_total"])

                vault.update_execution_result(
                    testcase_key,
                    qemu_golden_hash=result.golden_digest,
                    mcpat_power=mcpat_power,
                    status=inner_status,
                    metadata=updated_metadata,
                )

                counts["processed"] += 1
                if inner_status == "GOLDEN_READY":
                    counts["golden_ready"] += 1
                elif inner_status == "POWER_READY":
                    counts["power_ready"] += 1
                elif inner_status == "INNER_READY":
                    counts["inner_ready"] += 1
                elif inner_status == "INVALID":
                    counts["invalid"] += 1
                elif inner_status == "TIMEOUT":
                    counts["timed_out"] += 1
                elif inner_status == "CRASHED":
                    counts["crashed"] += 1

                case_results.append(
                    InnerLoopCaseResult(
                        testcase_key=testcase_key,
                        source_path=str(source_path.resolve()),
                        artifact_dir=str(candidate_output.resolve()),
                        power_requested=power_requested,
                        inner_status=inner_status,
                        result_status=result.status,
                        golden_digest=result.golden_digest,
                        power_total=mcpat_power,
                        source_cache_hit=bool(cache_flags["source_cache_hit"]),
                        elf_cache_hit=bool(cache_flags["elf_cache_hit"]),
                        golden_cache_hit=bool(cache_flags["golden_cache_hit"]),
                    )
                )
            except Exception as exc:
                error_metadata = _merge_metadata(
                    metadata,
                    {
                        "source_path": str(source_path.resolve()),
                        "inner_loop": {
                            "power_requested": power_requested,
                            "inner_status": "CRASHED",
                            "error": str(exc),
                            "artifact_dir": str(candidate_output.resolve()),
                        },
                    },
                )
                vault.update_execution_result(
                    testcase_key,
                    status="CRASHED",
                    metadata=error_metadata,
                )
                counts["processed"] += 1
                counts["crashed"] += 1
                case_results.append(
                    InnerLoopCaseResult(
                        testcase_key=testcase_key,
                        source_path=str(source_path.resolve()),
                        artifact_dir=str(candidate_output.resolve()),
                        power_requested=power_requested,
                        inner_status="CRASHED",
                        source_cache_hit=bool(cache_flags["source_cache_hit"]),
                        elf_cache_hit=bool(cache_flags["elf_cache_hit"]),
                        golden_cache_hit=bool(cache_flags["golden_cache_hit"]),
                        error=str(exc),
                    )
                )

    evolution_payload = {"emitted": 0, "records": []}
    if enable_evolution and max_offspring > 0:
        evolution_payload = _run_evolution(
            db_path=db_path,
            output_root=output_root,
            wrapper_name=wrapper,
            sequence_length=sequence_length,
            benchmark_size=benchmark_size,
            dependency_distance=dependency_distance,
            strict_validation=strict_validation,
            parent_limit=parent_limit,
            offspring_per_parent=offspring_per_parent,
            max_offspring=max_offspring,
        )

    return {
        "ok": True,
        "preflight": preflight,
        "generate": generation_payload,
        "counts": counts,
        "cases": [asdict(result) for result in case_results],
        "evolve": evolution_payload,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the high-frequency inner loop for ARM64 SDC fuzzing."
    )
    parser.add_argument("--db", type=Path, required=True, help="Vault database path.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for generated/materialized/inner-loop artifacts.",
    )
    parser.add_argument("--generate-count", type=int, default=0)
    parser.add_argument("--generate-jobs", type=int, default=1)
    parser.add_argument("--process-limit", type=int, default=8)
    parser.add_argument("--power-limit", type=int, default=4)
    parser.add_argument(
        "--process-status",
        action="append",
        default=[],
        help="Statuses eligible for processing. Repeat as needed.",
    )
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--wrapper", default=DEFAULT_WRAPPER)
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--benchmark-size", type=int, default=64)
    parser.add_argument("--dependency-distance", type=int, default=1)
    parser.add_argument("--strict-validation", action="store_true")
    parser.add_argument("--compiler", default="aarch64-linux-gnu-gcc")
    parser.add_argument("--qemu-binary", default="qemu-aarch64")
    parser.add_argument("--gem5-binary", default=str(DEFAULT_GEM5_BINARY))
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--skip-power", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-evolution", action="store_true")
    parser.add_argument("--parent-limit", type=int, default=4)
    parser.add_argument("--offspring-per-parent", type=int, default=2)
    parser.add_argument("--max-offspring", type=int, default=8)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_inner_loop(
        db_path=args.db,
        output_root=args.output_root,
        generate_count=args.generate_count,
        generate_jobs=args.generate_jobs,
        process_limit=args.process_limit,
        power_limit=args.power_limit,
        process_statuses=tuple(args.process_status or DEFAULT_PROCESS_STATUSES),
        target=args.target,
        policy=args.policy,
        wrapper=args.wrapper,
        sequence_length=args.sequence_length,
        benchmark_size=args.benchmark_size,
        dependency_distance=args.dependency_distance,
        strict_validation=args.strict_validation,
        compiler=args.compiler,
        qemu_binary=args.qemu_binary,
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        mcpat_binary=args.mcpat_binary,
        skip_power=args.skip_power,
        skip_preflight=args.skip_preflight,
        timeout=args.timeout,
        enable_evolution=not args.no_evolution,
        parent_limit=args.parent_limit,
        offspring_per_parent=args.offspring_per_parent,
        max_offspring=args.max_offspring,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
