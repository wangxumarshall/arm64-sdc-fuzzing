#!/usr/bin/env python3
"""Top-level controller for the ARM64 SDC fuzzing pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .campaign import execute_campaign
from .hardware_lane import run_hardware_promotion
from .hardware_results import execute_hardware_promotions, ingest_hardware_result
from .managed_domains import collect_domain_statuses, diff_for_domain, summarize_managed_domains
from .materialize import materialize_testcase
from .preflight import (
    DEFAULT_GEM5_BINARY,
    DEFAULT_MCPAT_BINARY,
    PROFILE_DEV,
    PROFILE_HW,
    PROFILE_SIM,
    run_preflight,
    summarize_runtime_capabilities,
)
from .scheduler import FeedbackScheduler
from .tooling import (
    DEFAULT_GEM5_BAREMETAL_CONFIG,
    DEFAULT_GEM5_CONFIG,
    resolve_local_tools,
)
from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
MICROPROBE_SRC = REPO_ROOT / "microprobe" / "src"
DEFAULT_VAULT = REPO_ROOT / "artifacts" / "sdc_vault.sqlite3"
DEFAULT_AGENT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "sdc-agent"
DEFAULT_E2E_DEV_ROOT = REPO_ROOT / "artifacts" / "e2e-dev"
DEFAULT_E2E_SIM_ROOT = REPO_ROOT / "artifacts" / "e2e-sim"
DEFAULT_E2E_HW_ROOT = REPO_ROOT / "artifacts" / "e2e-hw"
DEFAULT_E2E_LOCAL_ROOT = REPO_ROOT / "artifacts" / "e2e-local"
DEFAULT_TARGET = "armv8_common-armv8_common-aarch64_linux_gcc"
DEFAULT_POLICY = "sdc_fuzzing"
DEFAULT_WRAPPER = "Arm64AsmWrapper"
PROFILE_SIM_SAFE = "SIM_SAFE"
GENERATION_STRATEGY_BASELINE = "baseline"


class AgentCommandError(RuntimeError):
    """Structured command failure that should be surfaced as JSON."""

    def __init__(self, message: str, *, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.payload = payload or {"ok": False, "error": message}


def _bootstrap_repo_python_paths() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(MICROPROBE_SRC) not in sys.path:
        sys.path.insert(0, str(MICROPROBE_SRC))


def _missing_dependency_runtime_error(exc: ModuleNotFoundError, *, context: str) -> RuntimeError:
    missing = exc.name or str(exc)
    return RuntimeError(
        f"{context} requires Python runtime dependencies for {Path(sys.executable).resolve()}. "
        f"Missing module: {missing}. "
        "On Ubuntu 24.04 ARM, run ./scripts/bootstrap_ubuntu_24_04_arm.sh. "
        "Otherwise install the repo requirements with "
        "`python3 -m pip install --break-system-packages -r requirements-dev.txt`."
    )


def _load_generation_module():
    _bootstrap_repo_python_paths()
    try:
        from . import generation as generation_module
    except ModuleNotFoundError as exc:
        raise _missing_dependency_runtime_error(exc, context="Generation commands") from exc

    try:
        generation_module.bootstrap_microprobe_paths()
    except ModuleNotFoundError as exc:
        raise _missing_dependency_runtime_error(exc, context="Generation commands") from exc
    return generation_module


def generate_batch(**kwargs):
    return _load_generation_module().generate_batch(**kwargs)


def run_phase2_validation(**kwargs):
    _load_generation_module()
    try:
        from .phase2_validation import run_phase2_validation as impl
    except ModuleNotFoundError as exc:
        raise _missing_dependency_runtime_error(exc, context="Phase 2 validation") from exc
    return impl(**kwargs)


def run_phase4_validation(**kwargs):
    _load_generation_module()
    try:
        from .phase4_validation import run_phase4_validation as impl
    except ModuleNotFoundError as exc:
        raise _missing_dependency_runtime_error(exc, context="Phase 4 validation") from exc
    return impl(**kwargs)


def summarize_vault(db_path: Path, *, limit: int = 5) -> Dict[str, Any]:
    scheduler = FeedbackScheduler()
    with SDCVault(db_path) as vault:
        counts = {
            "ALL": vault.count(),
            "PENDING": vault.count(status="PENDING"),
            "STATIC_DONE": vault.count(status="STATIC_DONE"),
            "GOLDEN_READY": vault.count(status="GOLDEN_READY"),
            "POWER_READY": vault.count(status="POWER_READY"),
            "INNER_READY": vault.count(status="INNER_READY"),
            "MATCHED": vault.count(status="MATCHED"),
            "SDC_FOUND": vault.count(status="SDC_FOUND"),
            "INVALID": vault.count(status="INVALID"),
            "TIMEOUT": vault.count(status="TIMEOUT"),
            "CRASHED": vault.count(status="CRASHED"),
        }
        top_candidates = [
            {
                "testcase_key": candidate.testcase_key,
                "status": candidate.status,
                "profile_name": candidate.profile_name,
                "inner_value_score": candidate.inner_value_score,
                "diversity_bonus": candidate.diversity_bonus,
                "fitness": candidate.fitness,
                "outer_value_score": candidate.outer_value_score,
                "injector_confidence_score": candidate.injector_confidence_score,
                "promotion_readiness_score": candidate.promotion_readiness_score,
                "promotion_ready": candidate.promotion_ready,
                "risk_score": candidate.row.get("risk_score", 0.0),
            }
            for candidate in scheduler.select_candidates(vault, limit)
        ]
        top_promotion_candidates = scheduler.promotion_plan(vault, limit)
    return {
        "db": str(db_path),
        "counts": counts,
        "top_candidates": top_candidates,
        "top_promotion_candidates": top_promotion_candidates,
        "managed_domains_summary": summarize_managed_domains(REPO_ROOT),
        "runtime_capabilities": summarize_runtime_capabilities(),
    }


def run_evolution(
    *,
    db_path: Path,
    output_dir: Optional[Path],
    parent_limit: int,
    offspring_per_parent: int,
    max_offspring: int,
    sequence_length: int,
    benchmark_size: int,
    dependency_distance: int,
    strict_validation: bool,
    min_memory_stride: int,
    base_seed: int,
    wrapper_name: str,
) -> Dict[str, Any]:
    _load_generation_module()
    try:
        from microprobe.driver.genetic import EvolutionConfig, SDCFuzzingGeneticDriver
    except ModuleNotFoundError as exc:
        raise _missing_dependency_runtime_error(exc, context="Evolution commands") from exc

    config = EvolutionConfig(
        parent_limit=parent_limit,
        offspring_per_parent=offspring_per_parent,
        max_offspring=max_offspring,
        sequence_length=sequence_length,
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        strict_validation=strict_validation,
        min_memory_stride=min_memory_stride,
        wrapper_name=wrapper_name,
        base_seed=base_seed,
    )
    driver = SDCFuzzingGeneticDriver(config=config)
    with SDCVault(db_path) as vault:
        records = driver.evolve(
            vault,
            output_dir=output_dir,
            parent_limit=parent_limit,
        )
    return {
        "emitted": len(records),
        "records": [asdict(record) for record in records],
    }


def run_cycle(
    *,
    db_path: Path,
    output_root: Path,
    generate_count: int,
    generate_jobs: int,
    campaign_limit: int,
    parent_limit: int,
    offspring_per_parent: int,
    max_offspring: int,
    target: str,
    policy: str,
    generate_profile: str,
    generation_strategy: str,
    template_name: Optional[str],
    generate_wrapper: str,
    evolve_wrapper: str,
    sequence_length: int,
    benchmark_size: int,
    dependency_distance: int,
    strict_validation: bool,
    compiler: str,
    qemu_binary: str,
    gem5_binary: str,
    gem5_config: Path,
    fault_model: str,
    fault_target: str,
    fault_bit: Optional[int],
    fault_tick: Optional[int],
    skip_gem5: bool,
    skip_mcpat: bool,
    skip_preflight: bool,
    timeout: int,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_tools = resolve_local_tools(
        compiler=None if str(compiler).strip() == "aarch64-linux-gnu-gcc" else compiler,
        qemu_user_binary=None if str(qemu_binary).strip() == "qemu-aarch64" else qemu_binary,
        gem5_binary=gem5_binary,
        gem5_config=gem5_config,
        mcpat_binary=DEFAULT_MCPAT_BINARY,
    )
    compiler = resolved_tools.compiler or compiler
    qemu_binary = resolved_tools.qemu_user_binary or qemu_binary
    gem5_binary = resolved_tools.gem5_binary or gem5_binary
    gem5_config = Path(resolved_tools.gem5_config or gem5_config)
    mcpat_binary = Path(resolved_tools.mcpat_binary or DEFAULT_MCPAT_BINARY)

    generation_payload = generate_batch(
        db_path=db_path,
        target=target,
        policy=policy,
        profile_name=generate_profile,
        generation_strategy=generation_strategy,
        template_name=template_name,
        wrapper=generate_wrapper,
        count=generate_count,
        jobs=generate_jobs,
        sequence_length=sequence_length,
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        strict_validation=strict_validation,
        output_dir=output_root / "generated",
    )

    campaign_payload = execute_campaign(
        db_path=db_path,
        limit=campaign_limit,
        source_root=None,
        output_root=output_root / "campaign",
        dry_run=False,
        skip_preflight=skip_preflight,
        compiler=compiler,
        compiler_flags=[],
        qemu_binary=qemu_binary,
        qemu_args=[],
        gem5_binary=gem5_binary,
        gem5_config=gem5_config,
        gem5_args=[],
        gem5_cmd_flag="auto",
        fault_model=fault_model,
        fault_target=fault_target,
        fault_bit=fault_bit,
        fault_tick=fault_tick,
        skip_gem5=skip_gem5,
        skip_mcpat=skip_mcpat,
        mcpat_template_profile="arm64-kunpeng920",
        mcpat_binary=mcpat_binary,
        timeout=timeout,
    )

    evolution_payload = run_evolution(
        db_path=db_path,
        output_dir=output_root / "evolved",
        parent_limit=parent_limit,
        offspring_per_parent=offspring_per_parent,
        max_offspring=max_offspring,
        sequence_length=sequence_length,
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        strict_validation=strict_validation,
        min_memory_stride=8192,
        base_seed=211,
        wrapper_name=evolve_wrapper,
    )

    return {
        "generate": generation_payload,
        "campaign": campaign_payload,
        "evolve": evolution_payload,
        "summary": summarize_vault(db_path),
        "resolved_paths": {
            "compiler": str(compiler),
            "qemu_user_binary": str(qemu_binary),
            "gem5_binary": str(gem5_binary),
            "gem5_config": str(gem5_config),
            "mcpat_binary": str(mcpat_binary),
        },
    }


def _build_runner_command(command: List[str]) -> List[str]:
    if command and command[0].endswith(".sh"):
        return ["bash", *command]
    return command


def _run_build_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for step in steps:
        command = list(step.get("command") or [])
        if not step.get("auto_build") or not command:
            continue
        run_command = _build_runner_command(command)
        completed = subprocess.run(
            run_command,
            cwd=step.get("cwd") or str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        result = {
            "step_id": step["step_id"],
            "command": run_command,
            "cwd": step.get("cwd") or str(REPO_ROOT),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        results.append(result)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Auto-build step failed for {step['step_id']} with returncode {completed.returncode}."
            )
    return results


def _default_e2e_output_root(output_root: Optional[Path], *, root: Path) -> Path:
    if output_root is not None:
        return output_root.resolve()
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return (root / run_id).resolve()


def _prepare_e2e_paths(
    *,
    output_root: Optional[Path],
    db_path: Optional[Path],
    default_root: Path,
) -> tuple[Path, Path]:
    resolved_output_root = _default_e2e_output_root(output_root, root=default_root)
    resolved_output_root.mkdir(parents=True, exist_ok=True)
    resolved_db_path = db_path.resolve() if db_path is not None else (resolved_output_root / "vault.sqlite3")
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved_output_root, resolved_db_path


def _run_profile_preflight(
    *,
    profile: str,
    db_path: Path,
    build_missing: bool,
    error_mode: str,
    error_message: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    preflight = run_preflight(
        profile=profile,
        vault_path=db_path,
    )

    build_results: List[Dict[str, Any]] = []
    if not preflight["ready"] and build_missing:
        manual_steps = [step for step in preflight["missing_steps"] if not step.get("auto_build")]
        if not manual_steps:
            build_results = _run_build_steps(list(preflight["missing_steps"]))
            preflight = run_preflight(
                profile=profile,
                vault_path=db_path,
            )

    if not preflight["ready"]:
        raise AgentCommandError(
            error_message,
            payload={
                "ok": False,
                "mode": error_mode,
                "db": str(db_path),
                "error": error_message,
                "preflight": preflight,
            },
        )

    return preflight, build_results


def _write_report(output_root: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    report_path = output_root / "report.json"
    report["report_json"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def run_e2e_dev(
    *,
    output_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    build_missing: bool = False,
    timeout: int = 30,
    invoked_as: str = "e2e-dev",
) -> Dict[str, Any]:
    del timeout
    default_root = DEFAULT_E2E_LOCAL_ROOT if invoked_as == "e2e-local" else DEFAULT_E2E_DEV_ROOT
    output_root, db_path = _prepare_e2e_paths(
        output_root=output_root,
        db_path=db_path,
        default_root=default_root,
    )
    preflight, build_results = _run_profile_preflight(
        profile=PROFILE_DEV,
        db_path=db_path,
        build_missing=build_missing,
        error_mode=invoked_as,
        error_message="Developer E2E preflight failed.",
    )

    generation_payload = generate_batch(
        db_path=db_path,
        target=DEFAULT_TARGET,
        policy=DEFAULT_POLICY,
        profile_name=PROFILE_SIM_SAFE,
        generation_strategy=GENERATION_STRATEGY_BASELINE,
        template_name=None,
        wrapper=DEFAULT_WRAPPER,
        count=1,
        jobs=1,
        sequence_length=4,
        benchmark_size=32,
        dependency_distance=1,
        strict_validation=False,
        output_dir=output_root / "generated",
    )
    if int(generation_payload.get("inserted", 0)) <= 0:
        raise RuntimeError(
            "Developer E2E generation emitted no valid testcases. "
            f"Failures: {generation_payload.get('failed', [])}"
        )

    materialized_source: Optional[Path] = None
    testcase_keys = list(generation_payload.get("testcase_keys") or [])
    if testcase_keys:
        with SDCVault(db_path) as vault:
            materialized_source = materialize_testcase(
                vault,
                testcase_keys[0],
                output_root=output_root / "materialized",
            )
    if materialized_source is None:
        raise RuntimeError("Developer E2E failed to materialize a generated testcase.")

    report = {
        "ok": True,
        "mode": "e2e-dev",
        "invoked_as": invoked_as,
        "output_root": str(output_root),
        "db": str(db_path),
        "resolved_paths": dict(preflight["resolved_paths"]),
        "preflight": preflight,
        "build": {
            "requested": build_missing,
            "results": build_results,
        },
        "generate": generation_payload,
        "materialized_source": str(materialized_source) if materialized_source is not None else None,
        "summary": summarize_vault(db_path),
    }
    return _write_report(output_root, report)


def run_e2e_sim(
    *,
    output_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    build_missing: bool = False,
    timeout: int = 120,
) -> Dict[str, Any]:
    output_root, db_path = _prepare_e2e_paths(
        output_root=output_root,
        db_path=db_path,
        default_root=DEFAULT_E2E_SIM_ROOT,
    )
    preflight, build_results = _run_profile_preflight(
        profile=PROFILE_SIM,
        db_path=db_path,
        build_missing=build_missing,
        error_mode="e2e-sim",
        error_message="Simulation E2E preflight failed.",
    )

    resolved_paths = dict(preflight["resolved_paths"])
    compiler = str(resolved_paths["compiler"])
    qemu_user_binary = str(resolved_paths["qemu_user_binary"])
    qemu_system_binary = str(resolved_paths["qemu_system_binary"])
    gem5_binary = str(resolved_paths["gem5_binary"])
    cycle_gem5_config = Path(str(resolved_paths["gem5_config"]))
    phase_gem5_config = (
        DEFAULT_GEM5_BAREMETAL_CONFIG.resolve()
        if DEFAULT_GEM5_BAREMETAL_CONFIG.exists()
        else cycle_gem5_config
    )
    mcpat_binary = Path(str(resolved_paths["mcpat_binary"]))

    phase2_payload = run_phase2_validation(
        db_path=db_path,
        output_root=output_root / "phase2",
        generate_count=1,
        profile_name=PROFILE_SIM_SAFE,
        candidate_kind="baseline",
        compiler=compiler,
        qemu_binary=qemu_system_binary,
        gem5_binary=Path(gem5_binary),
        gem5_config=phase_gem5_config,
        mcpat_binary=mcpat_binary,
        timeout=timeout,
    )
    phase4_payload = run_phase4_validation(
        db_path=db_path,
        output_root=output_root / "phase4",
        profile_name=PROFILE_SIM_SAFE,
        compiler=compiler,
        qemu_binary=qemu_system_binary,
        gem5_binary=Path(gem5_binary),
        gem5_config=phase_gem5_config,
        mcpat_binary=mcpat_binary,
        fault_models=("register_bit_flip",),
        fault_targets=("x0",),
        fault_bits=(0,),
        fault_ticks=(1000,),
        timeout=timeout,
    )
    cycle_payload = run_cycle(
        db_path=db_path,
        output_root=output_root / "cycle",
        generate_count=4,
        generate_jobs=1,
        campaign_limit=2,
        parent_limit=2,
        offspring_per_parent=1,
        max_offspring=2,
        target=DEFAULT_TARGET,
        policy=DEFAULT_POLICY,
        generate_profile=PROFILE_SIM_SAFE,
        generation_strategy=GENERATION_STRATEGY_BASELINE,
        template_name=None,
        generate_wrapper=DEFAULT_WRAPPER,
        evolve_wrapper=DEFAULT_WRAPPER,
        sequence_length=4,
        benchmark_size=32,
        dependency_distance=1,
        strict_validation=False,
        compiler=compiler,
        qemu_binary=qemu_user_binary,
        gem5_binary=gem5_binary,
        gem5_config=cycle_gem5_config,
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=0,
        fault_tick=1000,
        skip_gem5=False,
        skip_mcpat=False,
        skip_preflight=False,
        timeout=timeout,
    )
    if phase2_payload.get("status") != "INNER_READY":
        raise RuntimeError("Phase 2 simulation validation did not reach INNER_READY.")
    phase4_summary_status = str(phase4_payload.get("summary_status", ""))
    phase4_execution_plane = str(phase4_payload.get("fault_execution_plane", ""))
    if (
        phase4_summary_status not in {"MATCHED", "SDC_FOUND"}
        and not (
            phase4_summary_status == "INVALID"
            and phase4_execution_plane == "phase4_no_injector"
        )
    ):
        raise RuntimeError("Phase 4 simulation validation did not produce a valid summary status.")
    if int(cycle_payload.get("generate", {}).get("inserted", 0)) <= 0:
        raise RuntimeError("Cycle generation produced no inserted testcases.")
    if int(cycle_payload.get("campaign", {}).get("counts", {}).get("executed", 0)) <= 0:
        raise RuntimeError("Cycle campaign executed zero runs.")
    if int(cycle_payload.get("evolve", {}).get("emitted", 0)) <= 0:
        raise RuntimeError("Cycle evolution emitted zero offspring.")

    report = {
        "ok": True,
        "mode": "e2e-sim",
        "output_root": str(output_root),
        "db": str(db_path),
        "resolved_paths": {
            **resolved_paths,
            "gem5_baremetal_config": str(phase_gem5_config),
            "gem5_cycle_config": str(cycle_gem5_config),
        },
        "preflight": preflight,
        "build": {
            "requested": build_missing,
            "results": build_results,
        },
        "phase2": phase2_payload,
        "phase4": phase4_payload,
        "cycle": cycle_payload,
        "summary": summarize_vault(db_path),
    }
    return _write_report(output_root, report)


def run_e2e_hw(
    *,
    output_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    build_missing: bool = False,
) -> Dict[str, Any]:
    output_root, db_path = _prepare_e2e_paths(
        output_root=output_root,
        db_path=db_path,
        default_root=DEFAULT_E2E_HW_ROOT,
    )
    preflight, build_results = _run_profile_preflight(
        profile=PROFILE_HW,
        db_path=db_path,
        build_missing=build_missing,
        error_mode="e2e-hw",
        error_message="Hardware-lane preflight failed.",
    )

    promotion_payload = run_hardware_promotion(
        db_path=db_path,
        output_root=output_root / "hardware-promotion",
        limit=1,
        backend_name="opendcdiag",
        dry_run=False,
    )
    hardware_payload = execute_hardware_promotions(
        db_path=db_path,
        limit=1,
        backend_name="opendcdiag",
        machine_id="local-opendcdiag",
        runtime_root=output_root / "hardware-runtime",
        auto_ingest=True,
    )
    if not promotion_payload.get("promotions"):
        raise RuntimeError("Hardware promotion emitted no bundles.")
    if not hardware_payload.get("executed"):
        raise RuntimeError("Hardware lane executed no promotions.")

    report = {
        "ok": True,
        "mode": "e2e-hw",
        "output_root": str(output_root),
        "db": str(db_path),
        "resolved_paths": dict(preflight["resolved_paths"]),
        "preflight": preflight,
        "build": {
            "requested": build_missing,
            "results": build_results,
        },
        "promote_hw": promotion_payload,
        "run_hw": hardware_payload,
        "summary": summarize_vault(db_path),
        "latest_promotion": promotion_payload["promotions"][0] if promotion_payload.get("promotions") else None,
        "latest_hardware_run": hardware_payload["executed"][0] if hardware_payload.get("executed") else None,
    }
    return _write_report(output_root, report)


def run_e2e_local(
    *,
    output_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    build_missing: bool = False,
    timeout: int = 30,
) -> Dict[str, Any]:
    return run_e2e_dev(
        output_root=output_root,
        db_path=db_path,
        build_missing=build_missing,
        timeout=timeout,
        invoked_as="e2e-local",
    )


def _add_common_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--profile", default=PROFILE_SIM_SAFE)
    parser.add_argument("--generation-strategy", default=GENERATION_STRATEGY_BASELINE)
    parser.add_argument("--template-name", default=None)
    parser.add_argument("--wrapper", default=DEFAULT_WRAPPER)
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--benchmark-size", type=int, default=64)
    parser.add_argument("--dependency-distance", type=int, default=1)
    parser.add_argument("--strict-validation", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run generation, campaign execution, evolution, and vault summaries."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    status.add_argument("--limit", type=int, default=5)

    domains = subparsers.add_parser("domains")
    domains.add_argument("--recent-limit", type=int, default=5)

    diff = subparsers.add_parser("diff")
    diff.add_argument("--domain", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    _add_common_generation_args(generate)
    generate.add_argument("--count", type=int, default=16)
    generate.add_argument("--jobs", type=int, default=1)
    generate.add_argument("--output-dir", type=Path, default=None)

    evolve = subparsers.add_parser("evolve")
    evolve.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    evolve.add_argument("--output-dir", type=Path, default=DEFAULT_AGENT_OUTPUT_ROOT / "evolved")
    evolve.add_argument("--parent-limit", type=int, default=8)
    evolve.add_argument("--offspring-per-parent", type=int, default=2)
    evolve.add_argument("--max-offspring", type=int, default=16)
    evolve.add_argument("--sequence-length", type=int, default=8)
    evolve.add_argument("--benchmark-size", type=int, default=64)
    evolve.add_argument("--dependency-distance", type=int, default=1)
    evolve.add_argument("--strict-validation", action="store_true")
    evolve.add_argument("--min-memory-stride", type=int, default=8192)
    evolve.add_argument("--base-seed", type=int, default=211)
    evolve.add_argument("--wrapper-name", default=DEFAULT_WRAPPER)

    promote_hw = subparsers.add_parser("promote-hw")
    promote_hw.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    promote_hw.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_AGENT_OUTPUT_ROOT / "hardware-lane",
    )
    promote_hw.add_argument("--limit", type=int, default=4)
    promote_hw.add_argument("--backend-name", default="opendcdiag")
    promote_hw.add_argument("--dry-run", action="store_true")

    run_hw = subparsers.add_parser("run-hw")
    run_hw.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    run_hw.add_argument("--limit", type=int, default=4)
    run_hw.add_argument("--backend-name", default="opendcdiag")
    run_hw.add_argument("--machine-id", default="local-opendcdiag")
    run_hw.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_AGENT_OUTPUT_ROOT / "hardware-runtime",
    )
    run_hw.add_argument("--no-auto-ingest", action="store_true")

    ingest_hw = subparsers.add_parser("ingest-hw")
    ingest_hw.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    ingest_hw.add_argument("--result-json", type=Path, required=True)
    ingest_hw.add_argument("--machine-id", default=None)

    cycle = subparsers.add_parser("cycle")
    cycle.add_argument("--db", type=Path, default=DEFAULT_VAULT)
    cycle.add_argument("--output-root", type=Path, default=DEFAULT_AGENT_OUTPUT_ROOT)
    cycle.add_argument("--generate-count", type=int, default=16)
    cycle.add_argument("--generate-jobs", type=int, default=1)
    cycle.add_argument("--campaign-limit", type=int, default=4)
    cycle.add_argument("--parent-limit", type=int, default=8)
    cycle.add_argument("--offspring-per-parent", type=int, default=2)
    cycle.add_argument("--max-offspring", type=int, default=16)
    _add_common_generation_args(cycle)
    cycle.add_argument("--evolve-wrapper", default=DEFAULT_WRAPPER)
    cycle.add_argument("--compiler", default="aarch64-linux-gnu-gcc")
    cycle.add_argument("--qemu-binary", default="qemu-aarch64")
    cycle.add_argument("--gem5-binary", default=str(DEFAULT_GEM5_BINARY))
    cycle.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    cycle.add_argument("--fault-model", default="none")
    cycle.add_argument("--fault-target", default="")
    cycle.add_argument("--fault-bit", type=int, default=None)
    cycle.add_argument("--fault-tick", type=int, default=None)
    cycle.add_argument("--skip-gem5", action="store_true")
    cycle.add_argument("--skip-mcpat", action="store_true")
    cycle.add_argument("--skip-preflight", action="store_true")
    cycle.add_argument("--timeout", type=int, default=120)

    e2e_dev = subparsers.add_parser("e2e-dev")
    e2e_dev.add_argument("--output-root", type=Path, default=None)
    e2e_dev.add_argument("--db", type=Path, default=None)
    e2e_dev.add_argument("--build-missing", action="store_true")
    e2e_dev.add_argument("--timeout", type=int, default=30)

    e2e_sim = subparsers.add_parser("e2e-sim")
    e2e_sim.add_argument("--output-root", type=Path, default=None)
    e2e_sim.add_argument("--db", type=Path, default=None)
    e2e_sim.add_argument("--build-missing", action="store_true")
    e2e_sim.add_argument("--timeout", type=int, default=120)

    e2e_hw = subparsers.add_parser("e2e-hw")
    e2e_hw.add_argument("--output-root", type=Path, default=None)
    e2e_hw.add_argument("--db", type=Path, default=None)
    e2e_hw.add_argument("--build-missing", action="store_true")

    e2e_local = subparsers.add_parser("e2e-local")
    e2e_local.add_argument("--output-root", type=Path, default=None)
    e2e_local.add_argument("--db", type=Path, default=None)
    e2e_local.add_argument("--build-missing", action="store_true")
    e2e_local.add_argument("--timeout", type=int, default=30)

    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        if args.command == "status":
            payload = summarize_vault(args.db, limit=args.limit)
        elif args.command == "domains":
            payload = {
                "repo_root": str(REPO_ROOT),
                "domains": [
                    status.to_dict()
                    for status in collect_domain_statuses(REPO_ROOT, recent_limit=args.recent_limit)
                ],
            }
        elif args.command == "diff":
            payload = diff_for_domain(args.domain, REPO_ROOT)
        elif args.command == "generate":
            payload = generate_batch(
                db_path=args.db,
                target=args.target,
                policy=args.policy,
                profile_name=args.profile,
                generation_strategy=args.generation_strategy,
                template_name=args.template_name,
                wrapper=args.wrapper,
                count=args.count,
                jobs=args.jobs,
                sequence_length=args.sequence_length,
                benchmark_size=args.benchmark_size,
                dependency_distance=args.dependency_distance,
                strict_validation=args.strict_validation,
                output_dir=args.output_dir,
            )
        elif args.command == "evolve":
            payload = run_evolution(
                db_path=args.db,
                output_dir=args.output_dir,
                parent_limit=args.parent_limit,
                offspring_per_parent=args.offspring_per_parent,
                max_offspring=args.max_offspring,
                sequence_length=args.sequence_length,
                benchmark_size=args.benchmark_size,
                dependency_distance=args.dependency_distance,
                strict_validation=args.strict_validation,
                min_memory_stride=args.min_memory_stride,
                base_seed=args.base_seed,
                wrapper_name=args.wrapper_name,
            )
        elif args.command == "promote-hw":
            payload = run_hardware_promotion(
                db_path=args.db,
                output_root=args.output_root,
                limit=args.limit,
                backend_name=args.backend_name,
                dry_run=args.dry_run,
            )
        elif args.command == "run-hw":
            payload = execute_hardware_promotions(
                db_path=args.db,
                limit=args.limit,
                backend_name=args.backend_name,
                machine_id=args.machine_id,
                runtime_root=args.runtime_root,
                auto_ingest=not args.no_auto_ingest,
            )
        elif args.command == "ingest-hw":
            payload = ingest_hardware_result(
                db_path=args.db,
                result_json=args.result_json,
                machine_id=args.machine_id,
            )
        elif args.command == "e2e-dev":
            payload = run_e2e_dev(
                output_root=args.output_root,
                db_path=args.db,
                build_missing=args.build_missing,
                timeout=args.timeout,
            )
        elif args.command == "e2e-sim":
            payload = run_e2e_sim(
                output_root=args.output_root,
                db_path=args.db,
                build_missing=args.build_missing,
                timeout=args.timeout,
            )
        elif args.command == "e2e-hw":
            payload = run_e2e_hw(
                output_root=args.output_root,
                db_path=args.db,
                build_missing=args.build_missing,
            )
        elif args.command == "e2e-local":
            payload = run_e2e_local(
                output_root=args.output_root,
                db_path=args.db,
                build_missing=args.build_missing,
                timeout=args.timeout,
            )
        else:
            payload = run_cycle(
                db_path=args.db,
                output_root=args.output_root,
                generate_count=args.generate_count,
                generate_jobs=args.generate_jobs,
                campaign_limit=args.campaign_limit,
                parent_limit=args.parent_limit,
                offspring_per_parent=args.offspring_per_parent,
                max_offspring=args.max_offspring,
                target=args.target,
                policy=args.policy,
                generate_profile=args.profile,
                generation_strategy=args.generation_strategy,
                template_name=args.template_name,
                generate_wrapper=args.wrapper,
                evolve_wrapper=args.evolve_wrapper,
                sequence_length=args.sequence_length,
                benchmark_size=args.benchmark_size,
                dependency_distance=args.dependency_distance,
                strict_validation=args.strict_validation,
                compiler=args.compiler,
                qemu_binary=args.qemu_binary,
                gem5_binary=args.gem5_binary,
                gem5_config=args.gem5_config,
                fault_model=args.fault_model,
                fault_target=args.fault_target,
                fault_bit=args.fault_bit,
                fault_tick=args.fault_tick,
                skip_gem5=args.skip_gem5,
                skip_mcpat=args.skip_mcpat,
                skip_preflight=args.skip_preflight,
                timeout=args.timeout,
            )
    except AgentCommandError as exc:
        print(json.dumps(exc.payload, indent=2, ensure_ascii=False))
        return 1
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
