#!/usr/bin/env python3
"""Shared generation helpers for the ARM64 SDC fuzzing pipeline."""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
MICROPROBE_ROOT = REPO_ROOT / "microprobe"
MICROPROBE_SRC = MICROPROBE_ROOT / "src"
TARGETS_ROOT = MICROPROBE_ROOT / "targets"
DEFAULT_TARGET = "armv8_common-armv8_common-aarch64_linux_gcc"
DEFAULT_POLICY = "sdc_fuzzing"
DEFAULT_WRAPPER = "Arm64AsmWrapper"


def bootstrap_microprobe_paths() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(MICROPROBE_SRC) not in sys.path:
        sys.path.insert(0, str(MICROPROBE_SRC))

    from microprobe import MICROPROBE_RC

    for key in [
        "default_paths",
        "architecture_paths",
        "microarchitecture_paths",
        "environment_paths",
        "wrapper_paths",
    ]:
        if str(TARGETS_ROOT) not in MICROPROBE_RC[key]:
            MICROPROBE_RC[key].append(str(TARGETS_ROOT))


bootstrap_microprobe_paths()

from microprobe.code import get_wrapper  # noqa: E402
from microprobe.target import import_definition  # noqa: E402
from microprobe.utils.policy import find_policy  # noqa: E402

from .vault import SDCVault, VaultEntry  # noqa: E402


@dataclass(frozen=True)
class GeneratedTestcase:
    entry: VaultEntry
    output_file: Optional[str]
    wrapper_name: str
    metadata: Dict[str, Any]


def _merge_nested_dicts(
    base: Dict[str, Any], extra: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    if not extra:
        return base
    for key, value in extra.items():
        if (
            isinstance(value, Mapping)
            and isinstance(base.get(key), dict)
        ):
            base[key] = _merge_nested_dicts(dict(base[key]), value)
        elif isinstance(value, Mapping):
            base[key] = _merge_nested_dicts({}, value)
        else:
            base[key] = value
    return base


def resolve_wrapper(wrapper_name: str) -> tuple[Any, str]:
    try:
        wrapper_cls = get_wrapper(wrapper_name)
        return wrapper_cls, wrapper_name
    except Exception:
        fallback_name = DEFAULT_WRAPPER
        return get_wrapper(fallback_name), fallback_name


def resolve_instruction_names(target: Any, instruction_names: Sequence[str]) -> List[Any]:
    available = getattr(target.isa, "instructions", {})
    if not available:
        return []

    by_mnemonic: Dict[str, List[Any]] = {}
    for instruction in available.values():
        by_mnemonic.setdefault(instruction.mnemonic.upper(), []).append(instruction)

    resolved: List[Any] = []
    for raw_name in instruction_names:
        name = str(raw_name).strip()
        if not name:
            continue
        if name in available:
            resolved.append(available[name])
            continue

        upper_name = name.upper()
        mnemonic = upper_name.split("_")[0]
        candidates = by_mnemonic.get(upper_name) or by_mnemonic.get(mnemonic) or []
        if candidates:
            resolved.append(sorted(candidates, key=lambda item: item.name)[0])

    return resolved


def collect_sensitive_instructions(target: Any) -> List[Any]:
    try:
        from microprobe.targets.arm64.policies.sdc_fuzzing_policy import (
            SDCSensitiveAnalyzer,
        )

        return SDCSensitiveAnalyzer(target).collect()
    except Exception:
        instructions = list(getattr(target.isa, "instructions", {}).values())
        instructions.sort(key=lambda item: item.name)
        return instructions


def select_instructions(
    target: Any,
    *,
    sequence_length: int,
    seed: int,
    instruction_names: Optional[Sequence[str]] = None,
) -> List[Any]:
    rng = random.Random(seed)
    preferred = (
        resolve_instruction_names(target, instruction_names)
        if instruction_names is not None
        else []
    )
    sensitive = collect_sensitive_instructions(target)
    candidates = sensitive or list(getattr(target.isa, "instructions", {}).values())

    if not candidates and not preferred:
        raise RuntimeError("No instructions available in target ISA")

    selected: List[Any] = []
    if preferred:
        selected.extend(preferred[:sequence_length])

    fill_pool = preferred or candidates
    while len(selected) < sequence_length:
        selected.append(rng.choice(fill_pool))

    return selected[:sequence_length]


def compute_risk_score(metadata: Mapping[str, Any]) -> float:
    ace = float(metadata.get("ace_score", 0.0))
    ibr = float(metadata.get("ibr_score", 0.0))
    mem = float(metadata.get("memory_pressure_score", 0.0))
    return (ace * 0.45) + (ibr * 0.35) + (mem * 0.20)


def generate_testcase(task: Mapping[str, Any]) -> Dict[str, Any]:
    bootstrap_microprobe_paths()

    target_name = str(task.get("target", DEFAULT_TARGET))
    policy_name = str(task.get("policy", DEFAULT_POLICY))
    wrapper_name = str(task.get("wrapper", DEFAULT_WRAPPER))
    sequence_length = int(task.get("sequence_length", 8))
    benchmark_size = int(task.get("benchmark_size", 64))
    dependency_distance = int(task.get("dependency_distance", 1))
    memory_stream_stride = int(task.get("memory_stream_stride", 8192))
    strict_validation = bool(task.get("strict_validation", False))
    seed = int(task.get("seed", 13))
    output_dir_raw = task.get("output_dir")
    instruction_names = task.get("instruction_names")
    metadata_extra = task.get("metadata_extra")

    target = import_definition(target_name)
    wrapper_cls, resolved_wrapper_name = resolve_wrapper(wrapper_name)
    wrapper = wrapper_cls()
    policy = find_policy(target_name, policy_name)
    instructions = select_instructions(
        target,
        sequence_length=sequence_length,
        seed=seed,
        instruction_names=instruction_names,
    )

    synth = policy.apply(
        target,
        wrapper,
        instructions=instructions,
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        sequence_length=sequence_length,
        memory_stream_stride=memory_stream_stride,
        strict_validation=strict_validation,
    )
    benchmark = synth.synthesize()
    rendered = "".join(str(elem) for elem in synth._wrap(benchmark))
    testcase_key = hashlib.sha1(rendered.encode("utf-8")).hexdigest()

    metadata = dict(getattr(benchmark, "metadata", {}))
    metadata["wrapper_name"] = resolved_wrapper_name
    metadata["instruction_names"] = [instruction.name for instruction in instructions]
    metadata["seed"] = seed
    metadata["sequence_length"] = sequence_length
    metadata["benchmark_size"] = benchmark_size
    metadata["dependency_distance"] = dependency_distance
    metadata["memory_stream_stride"] = memory_stream_stride
    metadata = _merge_nested_dicts(metadata, metadata_extra)
    risk_score = compute_risk_score(metadata)
    metadata["risk_score"] = risk_score

    output_file: Optional[Path] = None
    if output_dir_raw is not None:
        output_dir = Path(output_dir_raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = (
            ".s"
            if resolved_wrapper_name in {"Assembly", "Arm64AsmWrapper"}
            else ".c"
        )
        output_file = output_dir / f"{testcase_key}{suffix}"
        output_file.write_text(rendered, encoding="utf-8")
        metadata["rendered_path"] = str(output_file.resolve())
        metadata["rendered_format"] = suffix.lstrip(".")
        if suffix == ".c":
            metadata["source_path"] = str(output_file.resolve())

    entry = VaultEntry(
        testcase_key=testcase_key,
        asm_content=rendered,
        target_name=target_name,
        policy_name=policy_name,
        ace_score=float(metadata.get("ace_score", 0.0)),
        ibr_score=float(metadata.get("ibr_score", 0.0)),
        memory_pressure_score=float(metadata.get("memory_pressure_score", 0.0)),
        risk_score=risk_score,
        metadata=metadata,
    )
    result = GeneratedTestcase(
        entry=entry,
        output_file=str(output_file) if output_file is not None else None,
        wrapper_name=resolved_wrapper_name,
        metadata=metadata,
    )
    return {
        "entry": result.entry,
        "output_file": result.output_file,
        "wrapper_name": result.wrapper_name,
        "metadata": result.metadata,
    }


def build_generation_tasks(
    *,
    target: str,
    policy: str,
    wrapper: str,
    count: int,
    sequence_length: int,
    benchmark_size: int,
    dependency_distance: int,
    memory_stream_stride: int,
    strict_validation: bool,
    seed: int,
    output_dir: Optional[Path],
) -> Iterable[Dict[str, Any]]:
    for index in range(count):
        yield {
            "target": target,
            "policy": policy,
            "wrapper": wrapper,
            "sequence_length": sequence_length,
            "benchmark_size": benchmark_size,
            "dependency_distance": dependency_distance,
            "memory_stream_stride": memory_stream_stride,
            "strict_validation": strict_validation,
            "seed": seed + index,
            "output_dir": str(output_dir) if output_dir is not None else None,
        }


def generate_batch(
    *,
    db_path: Path,
    target: str = DEFAULT_TARGET,
    policy: str = DEFAULT_POLICY,
    wrapper: str = DEFAULT_WRAPPER,
    count: int = 16,
    jobs: int = 1,
    sequence_length: int = 8,
    benchmark_size: int = 64,
    dependency_distance: int = 1,
    memory_stream_stride: int = 8192,
    strict_validation: bool = False,
    seed: int = 13,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    successes = 0
    failures: List[Dict[str, Any]] = []
    testcase_keys: List[str] = []

    with SDCVault(db_path) as vault:
        tasks = list(
            build_generation_tasks(
                target=target,
                policy=policy,
                wrapper=wrapper,
                count=count,
                sequence_length=sequence_length,
                benchmark_size=benchmark_size,
                dependency_distance=dependency_distance,
                memory_stream_stride=memory_stream_stride,
                strict_validation=strict_validation,
                seed=seed,
                output_dir=output_dir,
            )
        )

        if jobs <= 1:
            iterator = map(generate_testcase, tasks)
        else:
            with mp.Pool(processes=jobs) as pool:
                iterator = pool.imap_unordered(generate_testcase, tasks)

        for index, task in enumerate(tasks):
            try:
                result = next(iterator)
            except StopIteration:
                break
            except Exception as exc:
                failures.append(
                    {
                        "index": index,
                        "seed": task["seed"],
                        "error": str(exc),
                    }
                )
                continue

            vault.upsert_testcase(result["entry"])
            successes += 1
            testcase_keys.append(result["entry"].testcase_key)

    return {
        "requested": count,
        "inserted": successes,
        "testcase_keys": testcase_keys,
        "failed": failures,
        "db": str(db_path),
    }


def summarize_generation_result(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), indent=2, ensure_ascii=False)
