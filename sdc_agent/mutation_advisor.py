#!/usr/bin/env python3
"""Heuristic mutation-advice builder for intelligent testcase generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from .generation_strategies import (
    get_template_spec,
    recommend_generation_recipe,
)

if TYPE_CHECKING:
    from .scheduler import RankedCandidate


def build_mutation_advice(candidate: "RankedCandidate") -> Dict[str, Any]:
    recipe = recommend_generation_recipe(
        profile_name=candidate.profile_name,
        instruction_families=candidate.instruction_families,
    )
    template = get_template_spec(recipe["template_name"])
    preferred_stride = int(candidate.metadata.get("preferred_stride_bytes", 8192) or 8192)
    current_dependency_distance = int(candidate.metadata.get("dependency_distance", 1) or 1)
    recommended_dependency_distance = current_dependency_distance
    recommended_memory_stream_stride = preferred_stride
    recommended_fault_model = "register_bit_flip"
    rationale: List[str] = []

    if template is not None:
        recommended_dependency_distance = max(
            current_dependency_distance,
            template.recommended_dependency_distance,
        )
        recommended_memory_stream_stride = max(
            preferred_stride,
            template.preferred_stride_bytes,
        )
        rationale.append(f"template={template.name}")

    if candidate.profile_name == "HW_AGGRESSIVE":
        rationale.append("profile=hw_aggressive")

    memory_family_count = sum(
        1
        for family in candidate.instruction_families
        if family in {"LDUR", "STUR", "LDR", "STR", "LDP", "STP", "LDAR", "STLR", "LDXR", "STXR"}
    )
    vector_family_count = sum(
        1
        for family in candidate.instruction_families
        if family in {"FMADD", "FMLA", "CRC32X", "CRC32W", "CRC32B", "CRC32H"}
    )

    if memory_family_count >= 2:
        recommended_fault_model = "memory_bit_flip"
        rationale.append("memory_families")
    elif vector_family_count > 0 or candidate.profile_name == "HW_AGGRESSIVE":
        recommended_fault_model = "vector_register_bit_flip"
        rationale.append("vector_or_aggressive_profile")

    if candidate.diversity_bonus <= 1.05:
        rationale.append("increase_diversity")
    if candidate.inner_value_score > 0.0:
        rationale.append("preserve_inner_value")

    return {
        "recommended_profile_name": (
            template.recommended_profile if template is not None else candidate.profile_name
        ),
        "recommended_generation_strategy": recipe["generation_strategy"],
        "recommended_template_name": recipe["template_name"],
        "recommended_dependency_distance": recommended_dependency_distance,
        "recommended_memory_stream_stride": recommended_memory_stream_stride,
        "recommended_fault_model": recommended_fault_model,
        "rationale": rationale,
    }
