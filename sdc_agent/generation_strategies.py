#!/usr/bin/env python3
"""Template and PCFG-style helpers for ARM64 testcase generation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


GENERATION_STRATEGY_BASELINE = "baseline"
GENERATION_STRATEGY_TEMPLATE = "template"
GENERATION_STRATEGY_PCFG = "pcfg"
SUPPORTED_GENERATION_STRATEGIES = (
    GENERATION_STRATEGY_BASELINE,
    GENERATION_STRATEGY_TEMPLATE,
    GENERATION_STRATEGY_PCFG,
)


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    description: str
    recommended_profile: str
    template_mnemonics: Tuple[str, ...]
    family_weights: Mapping[str, float]
    preferred_stride_bytes: int
    recommended_dependency_distance: int
    version: int = 1


TEMPLATE_LIBRARY: Dict[str, TemplateSpec] = {
    "cache_thrash": TemplateSpec(
        name="cache_thrash",
        description="Memory-heavy stride pattern intended to amplify cache pressure.",
        recommended_profile="SIM_SAFE",
        template_mnemonics=("LDUR", "STUR", "LDR", "STR", "ADD", "SUB", "EOR", "CMP"),
        family_weights={
            "LDUR": 0.24,
            "STUR": 0.24,
            "LDR": 0.16,
            "STR": 0.16,
            "ADD": 0.10,
            "SUB": 0.05,
            "EOR": 0.03,
            "CMP": 0.02,
        },
        preferred_stride_bytes=16384,
        recommended_dependency_distance=1,
    ),
    "long_dependency_chain": TemplateSpec(
        name="long_dependency_chain",
        description="Dependent ALU chain intended to amplify propagation sensitivity.",
        recommended_profile="SIM_SAFE",
        template_mnemonics=("MOVZ", "ADD", "EOR", "SUB", "ADD", "EOR", "CMP"),
        family_weights={
            "ADD": 0.36,
            "SUB": 0.18,
            "EOR": 0.18,
            "MOVZ": 0.14,
            "CMP": 0.08,
            "LSL": 0.03,
            "LSR": 0.03,
        },
        preferred_stride_bytes=8192,
        recommended_dependency_distance=4,
    ),
    "neon_fma_heavy": TemplateSpec(
        name="neon_fma_heavy",
        description="Aggressive NEON/FMA-heavy pattern targeting vector datapaths.",
        recommended_profile="HW_AGGRESSIVE",
        template_mnemonics=("FMADD", "FMLA", "LDP", "STP", "ADD", "CRC32X"),
        family_weights={
            "FMADD": 0.32,
            "FMLA": 0.24,
            "LDP": 0.14,
            "STP": 0.10,
            "ADD": 0.10,
            "CRC32X": 0.10,
        },
        preferred_stride_bytes=12288,
        recommended_dependency_distance=2,
    ),
}


def normalize_generation_strategy(strategy: Optional[str]) -> str:
    if not strategy:
        return GENERATION_STRATEGY_BASELINE
    normalized = str(strategy).strip().lower()
    if normalized not in SUPPORTED_GENERATION_STRATEGIES:
        raise ValueError(
            f"Unsupported generation_strategy: {strategy}. "
            f"Expected one of: {', '.join(SUPPORTED_GENERATION_STRATEGIES)}"
        )
    return normalized


def get_template_spec(template_name: Optional[str]) -> Optional[TemplateSpec]:
    if not template_name:
        return None
    normalized = str(template_name).strip().lower()
    if normalized not in TEMPLATE_LIBRARY:
        raise ValueError(
            f"Unsupported template_name: {template_name}. "
            f"Expected one of: {', '.join(sorted(TEMPLATE_LIBRARY))}"
        )
    return TEMPLATE_LIBRARY[normalized]


def _instruction_map(instructions: Sequence[Any]) -> Dict[str, List[Any]]:
    by_mnemonic: Dict[str, List[Any]] = {}
    for instruction in instructions:
        by_mnemonic.setdefault(instruction.mnemonic.upper(), []).append(instruction)
    for values in by_mnemonic.values():
        values.sort(key=lambda item: item.name)
    return by_mnemonic


def _fallback_instruction(
    instructions: Sequence[Any],
    selected: Sequence[Any],
    rng: random.Random,
) -> Any:
    pool = list(selected) or list(instructions)
    if not pool:
        raise RuntimeError("No instruction candidates available for intelligent generation.")
    return rng.choice(pool)


def _select_template_sequence(
    *,
    instructions: Sequence[Any],
    by_mnemonic: Mapping[str, Sequence[Any]],
    sequence_length: int,
    rng: random.Random,
    template: TemplateSpec,
) -> List[Any]:
    selected: List[Any] = []
    for index in range(sequence_length):
        mnemonic = template.template_mnemonics[index % len(template.template_mnemonics)]
        candidates = list(by_mnemonic.get(mnemonic, ()))
        selected.append(
            rng.choice(candidates)
            if candidates
            else _fallback_instruction(instructions, selected, rng)
        )
    return selected


def _select_pcfg_sequence(
    *,
    instructions: Sequence[Any],
    by_mnemonic: Mapping[str, Sequence[Any]],
    sequence_length: int,
    rng: random.Random,
    template: TemplateSpec,
) -> List[Any]:
    weighted = [
        (family, float(weight))
        for family, weight in template.family_weights.items()
        if by_mnemonic.get(family)
    ]
    if not weighted:
        return _select_template_sequence(
            instructions=instructions,
            by_mnemonic=by_mnemonic,
            sequence_length=sequence_length,
            rng=rng,
            template=template,
        )

    families = [family for family, _ in weighted]
    weights = [weight for _, weight in weighted]
    selected: List[Any] = []
    for _ in range(sequence_length):
        family = rng.choices(families, weights=weights, k=1)[0]
        candidates = list(by_mnemonic.get(family, ()))
        selected.append(
            rng.choice(candidates)
            if candidates
            else _fallback_instruction(instructions, selected, rng)
        )
    return selected


def select_strategy_instructions(
    *,
    instructions: Sequence[Any],
    sequence_length: int,
    seed: int,
    generation_strategy: str,
    template_name: Optional[str],
) -> tuple[List[Any], Dict[str, Any]]:
    strategy = normalize_generation_strategy(generation_strategy)
    if strategy == GENERATION_STRATEGY_BASELINE:
        return [], {"generation_strategy": strategy}

    template = get_template_spec(template_name)
    if template is None:
        raise ValueError("template_name is required for template/pcfg generation strategies.")

    rng = random.Random(seed)
    by_mnemonic = _instruction_map(instructions)
    if strategy == GENERATION_STRATEGY_TEMPLATE:
        selected = _select_template_sequence(
            instructions=instructions,
            by_mnemonic=by_mnemonic,
            sequence_length=sequence_length,
            rng=rng,
            template=template,
        )
    else:
        selected = _select_pcfg_sequence(
            instructions=instructions,
            by_mnemonic=by_mnemonic,
            sequence_length=sequence_length,
            rng=rng,
            template=template,
        )

    metadata = {
        "generation_strategy": strategy,
        "template_name": template.name,
        "template_version": template.version,
        "template_description": template.description,
        "template_mnemonics": list(template.template_mnemonics),
        "template_family_weights": dict(template.family_weights),
        "template_recommended_profile": template.recommended_profile,
        "template_preferred_stride_bytes": template.preferred_stride_bytes,
        "template_recommended_dependency_distance": template.recommended_dependency_distance,
    }
    return selected, metadata


def recommend_generation_recipe(
    *,
    profile_name: str,
    instruction_families: Sequence[str],
) -> Dict[str, str]:
    normalized_profile = str(profile_name).strip().upper()
    families = {str(family).strip().upper() for family in instruction_families if str(family).strip()}
    if normalized_profile == "HW_AGGRESSIVE" or families & {"FMADD", "FMLA", "LD1", "ST1", "CRC32X"}:
        return {
            "generation_strategy": GENERATION_STRATEGY_PCFG,
            "template_name": "neon_fma_heavy",
        }
    if families & {"LDUR", "STUR", "LDR", "STR", "LDP", "STP"}:
        return {
            "generation_strategy": GENERATION_STRATEGY_TEMPLATE,
            "template_name": "cache_thrash",
        }
    return {
        "generation_strategy": GENERATION_STRATEGY_TEMPLATE,
        "template_name": "long_dependency_chain",
    }
