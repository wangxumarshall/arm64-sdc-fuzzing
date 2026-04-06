#!/usr/bin/env python3
"""Shared generation helpers for the ARM64 SDC fuzzing pipeline."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import multiprocessing as mp
import random
import re
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
PROFILE_SIM_SAFE = "SIM_SAFE"
PROFILE_HW_AGGRESSIVE = "HW_AGGRESSIVE"
PROFILE_ALL_GENERATABLE = "ALL_GENERATABLE"
PROFILE_EXECUTABLE_SAFE = "EXECUTABLE_SAFE"
PROFILE_KUNPENG920_STRESS = "KUNPENG920_STRESS"
SUPPORTED_PROFILES = (
    PROFILE_SIM_SAFE,
    PROFILE_HW_AGGRESSIVE,
    PROFILE_ALL_GENERATABLE,
    PROFILE_EXECUTABLE_SAFE,
    PROFILE_KUNPENG920_STRESS,
)
CATALOG_PROFILES = (
    PROFILE_ALL_GENERATABLE,
    PROFILE_EXECUTABLE_SAFE,
    PROFILE_KUNPENG920_STRESS,
)


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
from microprobe.utils.arm64_isa_catalog import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    build_catalog_summary,
    load_catalog,
    plan_catalog_task_count,
    select_catalog_encodings,
    validate_sequence_asm,
)

from .generation_strategies import (  # noqa: E402
    GENERATION_STRATEGY_BASELINE,
    normalize_generation_strategy,
    select_strategy_instructions,
)
from .vault import SDCVault, VaultEntry  # noqa: E402


@dataclass(frozen=True)
class GeneratedTestcase:
    entry: VaultEntry
    output_file: Optional[str]
    wrapper_name: str
    metadata: Dict[str, Any]


def normalize_profile_name(profile_name: Optional[str]) -> str:
    if not profile_name:
        return PROFILE_SIM_SAFE
    normalized = str(profile_name).strip().upper()
    if normalized not in SUPPORTED_PROFILES:
        raise ValueError(
            f"Unsupported profile_name: {profile_name}. "
            f"Expected one of: {', '.join(SUPPORTED_PROFILES)}"
        )
    return normalized


def resolve_profile_contract(
    *,
    profile_name: Optional[str],
    instruction_names: Optional[Sequence[str]],
) -> Dict[str, Any]:
    requested = normalize_profile_name(profile_name)
    effective = requested
    fallback_reason: Optional[str] = None

    return {
        "requested_profile_name": requested,
        "effective_profile_name": effective,
        "fallback_reason": fallback_reason,
        "contract_version": 1,
        "generation_mode": (
            "catalog" if effective in CATALOG_PROFILES else "synthesizer"
        ),
    }


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


def collect_sensitive_instructions(
    target: Any,
    *,
    profile_name: str = PROFILE_SIM_SAFE,
) -> List[Any]:
    try:
        from microprobe.targets.arm64.policies.sdc_fuzzing_policy import SDCSensitiveAnalyzer

        return SDCSensitiveAnalyzer(target).collect(profile_name=profile_name)
    except Exception:
        try:
            policy_path = (
                MICROPROBE_ROOT
                / "targets"
                / "arm64"
                / "policies"
                / "sdc_fuzzing_policy.py"
            ).resolve()
            spec = importlib.util.spec_from_file_location(
                "microprobe_arm64_sdc_fuzzing_policy",
                policy_path,
            )
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.SDCSensitiveAnalyzer(target).collect(
                    profile_name=profile_name
                )
        except Exception:
            pass

        instructions = list(getattr(target.isa, "instructions", {}).values())
        instructions.sort(key=lambda item: item.name)
        return instructions


_MOVE_WIDE_PATTERN = re.compile(
    r"^(?P<opc>MOV[ZNK])\s+(?P<reg>[A-Za-z0-9]+),\s*(?P<imm>[-]?[0-9]+),\s*(?P<hw>[0-3])$",
    re.IGNORECASE,
)
_SHIFT_REG_PATTERN = re.compile(
    r"^(?P<opc>ADD|ADDS|SUB|SUBS|AND|ORR|EOR)\s+"
    r"(?P<rd>[A-Za-z0-9]+),\s*(?P<rn>[A-Za-z0-9]+),\s*(?P<rm>[A-Za-z0-9]+),\s*"
    r"(?P<shift>[0-3])\s+(?P<amount>[0-9]+)$",
    re.IGNORECASE,
)
_SHIFT_NAMES = {
    "0": "lsl",
    "1": "lsr",
    "2": "asr",
    "3": "ror",
}


def normalize_arm64_asm(rendered: str) -> str:
    normalized: List[str] = []
    for line in rendered.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("."):
            normalized.append(line)
            continue

        move_match = _MOVE_WIDE_PATTERN.match(stripped)
        if move_match is not None:
            groups = move_match.groupdict()
            shift_amount = int(groups["hw"]) * 16
            normalized.append(
                f"{groups['opc'].lower()} {groups['reg']}, #{groups['imm']}, lsl #{shift_amount}"
            )
            continue

        shift_match = _SHIFT_REG_PATTERN.match(stripped)
        if shift_match is not None:
            groups = shift_match.groupdict()
            shift_name = _SHIFT_NAMES[str(groups["shift"])]
            normalized.append(
                f"{groups['opc'].lower()} {groups['rd']}, {groups['rn']}, {groups['rm']}, {shift_name} #{groups['amount']}"
            )
            continue

        normalized.append(stripped.lower())
    return "\n".join(normalized) + "\n"


def select_instructions(
    target: Any,
    *,
    sequence_length: int,
    seed: int,
    profile_name: str = PROFILE_SIM_SAFE,
    instruction_names: Optional[Sequence[str]] = None,
    generation_strategy: str = GENERATION_STRATEGY_BASELINE,
    template_name: Optional[str] = None,
) -> tuple[List[Any], Dict[str, Any]]:
    rng = random.Random(seed)
    preferred = (
        resolve_instruction_names(target, instruction_names)
        if instruction_names is not None
        else []
    )
    sensitive = collect_sensitive_instructions(target, profile_name=profile_name)
    candidates = sensitive or list(getattr(target.isa, "instructions", {}).values())

    if not candidates and not preferred:
        raise RuntimeError("No instructions available in target ISA")

    strategy = normalize_generation_strategy(generation_strategy)
    if not preferred and strategy != GENERATION_STRATEGY_BASELINE:
        selected, strategy_metadata = select_strategy_instructions(
            instructions=candidates,
            sequence_length=sequence_length,
            seed=seed,
            generation_strategy=strategy,
            template_name=template_name,
        )
        if selected:
            return selected, strategy_metadata

    selected: List[Any] = []
    if preferred:
        selected.extend(preferred[:sequence_length])

    fill_pool = preferred or candidates
    while len(selected) < sequence_length:
        selected.append(rng.choice(fill_pool))

    return selected[:sequence_length], {"generation_strategy": strategy}


def compute_risk_score(metadata: Mapping[str, Any]) -> float:
    ace = float(metadata.get("ace_score", 0.0))
    ibr = float(metadata.get("ibr_score", 0.0))
    mem = float(metadata.get("memory_pressure_score", 0.0))
    return (ace * 0.45) + (ibr * 0.35) + (mem * 0.20)


def _catalog_sequence_metrics(encodings: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    if not encodings:
        return {
            "ace_score": 0.0,
            "ibr_score": 0.0,
            "memory_pressure_score": 0.0,
        }

    memory = 0.0
    wide = 0.0
    ace = 0.0
    for encoding in encodings:
        mnemonic = str(encoding.get("mnemonic", "")).upper()
        instr_class = str(encoding.get("instr_class", ""))
        hotness = float(encoding.get("kunpeng_hotness", 0.0))
        if mnemonic.startswith(("LD", "ST", "CAS", "SWP", "PRFM")):
            memory += 1.0
        else:
            memory += min(hotness, 0.5)

        if instr_class in {"float", "advsimd"} or any(
            marker in mnemonic for marker in ("CRC", "AES", "SHA")
        ):
            wide += 1.0
        else:
            wide += 0.35

        ace += 0.65 if encoding.get("executable") else 0.2

    total = float(len(encodings))
    return {
        "ace_score": ace / total,
        "ibr_score": wide / total,
        "memory_pressure_score": memory / total,
    }


def _render_catalog_sequence(encodings: Sequence[Mapping[str, Any]]) -> str:
    result = validate_sequence_asm(encodings)
    return str(result["asm_text"])


def generate_catalog_testcase(task: Mapping[str, Any]) -> Dict[str, Any]:
    target_name = str(task.get("target", DEFAULT_TARGET))
    policy_name = str(task.get("policy", DEFAULT_POLICY))
    requested_wrapper_name = str(task.get("wrapper", DEFAULT_WRAPPER))
    output_dir_raw = task.get("output_dir")
    strict_validation = bool(task.get("strict_validation", False))
    profile_contract = resolve_profile_contract(
        profile_name=task.get("profile_name"),
        instruction_names=task.get("instruction_names"),
    )
    catalog = load_catalog(task.get("catalog_path", DEFAULT_CATALOG_PATH))
    catalog_offset = int(task.get("catalog_offset", 0))
    sequence_length = int(task.get("sequence_length", 8))
    seed = int(task.get("seed", 13))
    metadata_extra = task.get("metadata_extra")

    encodings = select_catalog_encodings(
        catalog,
        profile_name=profile_contract["effective_profile_name"],
        sequence_length=sequence_length,
        offset=catalog_offset,
    )
    if not encodings:
        raise RuntimeError(
            f"No catalog encodings available for profile "
            f"{profile_contract['effective_profile_name']}"
        )

    validation = validate_sequence_asm(encodings)
    if strict_validation and not validation["ok"]:
        raise RuntimeError(validation["stderr"] or "Catalog sequence validation failed")

    rendered = str(validation["asm_text"])
    testcase_key = hashlib.sha1(rendered.encode("utf-8")).hexdigest()

    metrics = _catalog_sequence_metrics(encodings)
    metadata: Dict[str, Any] = {
        **metrics,
        "profile_name": profile_contract["effective_profile_name"],
        "requested_profile_name": profile_contract["requested_profile_name"],
        "effective_profile_name": profile_contract["effective_profile_name"],
        "profile_contract": {
            "contract_version": profile_contract["contract_version"],
            "requested_profile_name": profile_contract["requested_profile_name"],
            "effective_profile_name": profile_contract["effective_profile_name"],
            "fallback_reason": profile_contract["fallback_reason"],
            "generation_mode": profile_contract["generation_mode"],
        },
        "wrapper_name": DEFAULT_WRAPPER,
        "requested_wrapper_name": requested_wrapper_name,
        "catalog_path": str(Path(task.get("catalog_path", DEFAULT_CATALOG_PATH)).resolve()),
        "catalog_offset": catalog_offset,
        "catalog_summary": build_catalog_summary(catalog),
        "instruction_names": [str(encoding["name"]) for encoding in encodings],
        "instruction_mnemonics": [str(encoding["mnemonic"]) for encoding in encodings],
        "doc_paths": [
            str(encoding["doc_path"])
            for encoding in encodings
            if encoding.get("doc_path")
        ],
        "seed": seed,
        "sequence_length": sequence_length,
        "clang_validation": {
            "ok": bool(validation["ok"]),
            "returncode": int(validation["returncode"]),
            "stderr": str(validation["stderr"]),
        },
    }
    if requested_wrapper_name != DEFAULT_WRAPPER:
        metadata["profile_contract"]["fallback_reason"] = (
            "catalog_profiles_force_arm64_asm_wrapper"
        )
    metadata = _merge_nested_dicts(metadata, metadata_extra)
    risk_score = compute_risk_score(metadata)
    metadata["risk_score"] = risk_score

    output_file: Optional[Path] = None
    if output_dir_raw is not None:
        output_dir = Path(output_dir_raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{testcase_key}.s"
        output_file.write_text(rendered, encoding="utf-8")
        metadata["rendered_path"] = str(output_file.resolve())
        metadata["rendered_format"] = "s"

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
    return {
        "entry": entry,
        "output_file": str(output_file) if output_file is not None else None,
        "wrapper_name": DEFAULT_WRAPPER,
        "metadata": metadata,
    }


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
    generation_strategy = normalize_generation_strategy(task.get("generation_strategy"))
    template_name = task.get("template_name")
    profile_contract = resolve_profile_contract(
        profile_name=task.get("profile_name"),
        instruction_names=instruction_names,
    )
    if profile_contract["generation_mode"] == "catalog":
        return generate_catalog_testcase(task)

    target = import_definition(target_name)
    wrapper_cls, resolved_wrapper_name = resolve_wrapper(wrapper_name)
    wrapper = wrapper_cls()
    policy = find_policy(target_name, policy_name)
    instructions, strategy_metadata = select_instructions(
        target,
        sequence_length=sequence_length,
        seed=seed,
        profile_name=profile_contract["effective_profile_name"],
        instruction_names=instruction_names,
        generation_strategy=generation_strategy,
        template_name=template_name,
    )

    synth = policy.apply(
        target,
        wrapper,
        instructions=instructions,
        profile_name=profile_contract["effective_profile_name"],
        benchmark_size=benchmark_size,
        dependency_distance=dependency_distance,
        sequence_length=sequence_length,
        memory_stream_stride=memory_stream_stride,
        strict_validation=strict_validation,
    )
    benchmark = synth.synthesize()
    rendered = "".join(str(elem) for elem in synth._wrap(benchmark))
    if "armv8_common" in target_name:
        rendered = normalize_arm64_asm(rendered)
    testcase_key = hashlib.sha1(rendered.encode("utf-8")).hexdigest()

    metadata = dict(getattr(benchmark, "metadata", {}))
    metadata["profile_name"] = profile_contract["effective_profile_name"]
    metadata["requested_profile_name"] = profile_contract["requested_profile_name"]
    metadata["effective_profile_name"] = profile_contract["effective_profile_name"]
    metadata["profile_contract"] = {
        "contract_version": profile_contract["contract_version"],
        "requested_profile_name": profile_contract["requested_profile_name"],
        "effective_profile_name": profile_contract["effective_profile_name"],
        "fallback_reason": profile_contract["fallback_reason"],
        "generation_mode": profile_contract["generation_mode"],
    }
    metadata["wrapper_name"] = resolved_wrapper_name
    metadata["instruction_names"] = [instruction.name for instruction in instructions]
    metadata["generation_strategy"] = strategy_metadata.get(
        "generation_strategy", generation_strategy
    )
    if strategy_metadata.get("template_name"):
        metadata["template_name"] = strategy_metadata["template_name"]
        metadata["template_version"] = strategy_metadata["template_version"]
        metadata["template_description"] = strategy_metadata["template_description"]
        metadata["template_mnemonics"] = strategy_metadata["template_mnemonics"]
        metadata["template_family_weights"] = strategy_metadata["template_family_weights"]
        metadata["template_recommended_profile"] = strategy_metadata[
            "template_recommended_profile"
        ]
        metadata.setdefault(
            "preferred_stride_bytes",
            strategy_metadata["template_preferred_stride_bytes"],
        )
        metadata.setdefault(
            "dependency_distance",
            strategy_metadata["template_recommended_dependency_distance"],
        )
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
    profile_name: str,
    catalog_path: Optional[Path] = None,
    generation_strategy: str = GENERATION_STRATEGY_BASELINE,
    template_name: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    for index in range(count):
        yield {
            "target": target,
            "policy": policy,
            "profile_name": profile_name,
            "generation_strategy": generation_strategy,
            "template_name": template_name,
            "wrapper": wrapper,
            "sequence_length": sequence_length,
            "benchmark_size": benchmark_size,
            "dependency_distance": dependency_distance,
            "memory_stream_stride": memory_stream_stride,
            "strict_validation": strict_validation,
            "seed": seed + index,
            "output_dir": str(output_dir) if output_dir is not None else None,
            "catalog_path": str(catalog_path) if catalog_path is not None else None,
            "catalog_offset": index * sequence_length,
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
    profile_name: str = PROFILE_SIM_SAFE,
    generation_strategy: str = GENERATION_STRATEGY_BASELINE,
    template_name: Optional[str] = None,
) -> Dict[str, Any]:
    requested_count = count
    successes = 0
    failures: List[Dict[str, Any]] = []
    testcase_keys: List[str] = []
    planned_count = count
    catalog_path = DEFAULT_CATALOG_PATH

    with SDCVault(db_path) as vault:
        if normalize_profile_name(profile_name) in CATALOG_PROFILES:
            catalog = load_catalog(catalog_path)
            planned_count = plan_catalog_task_count(
                catalog,
                profile_name=normalize_profile_name(profile_name),
                requested_count=count,
                sequence_length=sequence_length,
            )
        tasks = list(
            build_generation_tasks(
                target=target,
                policy=policy,
                profile_name=profile_name,
                wrapper=wrapper,
                count=planned_count,
                sequence_length=sequence_length,
                benchmark_size=benchmark_size,
                dependency_distance=dependency_distance,
                memory_stream_stride=memory_stream_stride,
                strict_validation=strict_validation,
                seed=seed,
                output_dir=output_dir,
                catalog_path=catalog_path,
                generation_strategy=generation_strategy,
                template_name=template_name,
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
        "requested": requested_count,
        "planned": planned_count,
        "inserted": successes,
        "testcase_keys": testcase_keys,
        "failed": failures,
        "db": str(db_path),
    }


def summarize_generation_result(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), indent=2, ensure_ascii=False)
