#!/usr/bin/env python3
"""Feedback-driven scheduler for the ARM64 SDC fuzzing loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from sdc_vault import SDCVault


DEFAULT_CANDIDATE_STATUSES = ("PENDING", "GOLDEN_READY", "MATCHED", "SDC_FOUND")


@dataclass(frozen=True)
class SchedulerConfig:
    """Tunable knobs for seed ranking and feedback integration."""

    candidate_statuses: Sequence[str] = DEFAULT_CANDIDATE_STATUSES
    scan_limit_per_status: int = 128
    memory_bonus_weight: float = 0.25
    pending_signal: float = 0.35
    golden_ready_signal: float = 0.45
    matched_signal: float = 0.25
    sdc_signal: float = 1.0
    invalid_signal: float = 0.0


@dataclass(frozen=True)
class RankedCandidate:
    testcase_key: str
    target_name: str
    policy_name: str
    status: str
    static_score: float
    sdc_signal: float
    power_total: float
    fitness: float
    metadata: Dict[str, Any]
    row: Mapping[str, Any]


def _row_to_dict(row: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(row)


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw_value = row.get("metadata_json", "{}")
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(raw_value)


def normalize_runner_status(status: str) -> str:
    normalized = status.strip().lower()
    mapping = {
        "golden_only": "GOLDEN_READY",
        "matched": "MATCHED",
        "sdc_found": "SDC_FOUND",
        "gem5_timeout": "TIMEOUT",
        "compile_failed": "INVALID",
        "golden_failed": "INVALID",
        "digest_missing": "INVALID",
        "gem5_failed": "CRASHED",
    }
    return mapping.get(normalized, normalized.upper())


def compute_static_score(
    ace_score: float,
    ibr_score: float,
    memory_pressure_score: float,
    *,
    memory_bonus_weight: float = 0.25,
) -> float:
    ace = max(float(ace_score), 0.0)
    ibr = max(float(ibr_score), 0.0)
    mem = max(float(memory_pressure_score), 0.0)
    return ace * ibr * (1.0 + (mem * memory_bonus_weight))


def compute_fitness(
    ace_score: float,
    ibr_score: float,
    memory_pressure_score: float,
    sdc_signal: float,
    power_total: Optional[float],
    *,
    memory_bonus_weight: float = 0.25,
) -> float:
    static_score = compute_static_score(
        ace_score,
        ibr_score,
        memory_pressure_score,
        memory_bonus_weight=memory_bonus_weight,
    )
    power = max(float(power_total or 0.0), 0.0)
    return static_score * max(float(sdc_signal), 0.0) / (power + 1.0)


class FeedbackScheduler:
    """Select candidates and fold execution feedback back into the vault."""

    def __init__(self, config: SchedulerConfig | None = None):
        self.config = config or SchedulerConfig()

    def status_signal(self, status: str) -> float:
        normalized = normalize_runner_status(status)
        if normalized == "SDC_FOUND":
            return self.config.sdc_signal
        if normalized == "GOLDEN_READY":
            return self.config.golden_ready_signal
        if normalized == "MATCHED":
            return self.config.matched_signal
        if normalized == "PENDING":
            return self.config.pending_signal
        return self.config.invalid_signal

    def status_priority(self, status: str) -> int:
        normalized = normalize_runner_status(status)
        priorities = {
            "SDC_FOUND": 4,
            "GOLDEN_READY": 3,
            "PENDING": 2,
            "MATCHED": 1,
        }
        return priorities.get(normalized, 0)

    def rank_row(self, row: Mapping[str, Any]) -> RankedCandidate:
        payload = _row_to_dict(row)
        metadata = _decode_metadata(payload)
        scheduler_metadata = metadata.get("scheduler", {})
        sdc_signal = float(
            scheduler_metadata.get(
                "sdc_signal", self.status_signal(payload.get("status", "PENDING"))
            )
        )
        power_total = scheduler_metadata.get("power_total", payload.get("mcpat_power"))
        fitness = compute_fitness(
            payload.get("ace_score", 0.0),
            payload.get("ibr_score", 0.0),
            payload.get("memory_pressure_score", 0.0),
            sdc_signal,
            power_total,
            memory_bonus_weight=self.config.memory_bonus_weight,
        )
        static_score = compute_static_score(
            payload.get("ace_score", 0.0),
            payload.get("ibr_score", 0.0),
            payload.get("memory_pressure_score", 0.0),
            memory_bonus_weight=self.config.memory_bonus_weight,
        )
        return RankedCandidate(
            testcase_key=str(payload["testcase_key"]),
            target_name=str(payload["target_name"]),
            policy_name=str(payload["policy_name"]),
            status=str(payload["status"]),
            static_score=static_score,
            sdc_signal=sdc_signal,
            power_total=float(power_total or 0.0),
            fitness=fitness,
            metadata=metadata,
            row=payload,
        )

    def select_candidates(self, vault: SDCVault, limit: int) -> List[RankedCandidate]:
        rows: List[Mapping[str, Any]] = []
        for status in self.config.candidate_statuses:
            rows.extend(
                vault.list_testcases(
                    limit=self.config.scan_limit_per_status,
                    status=status,
                )
            )

        deduped: Dict[str, Mapping[str, Any]] = {}
        for row in rows:
            payload = _row_to_dict(row)
            deduped[payload["testcase_key"]] = payload

        ranked = [self.rank_row(row) for row in deduped.values()]
        ranked.sort(
            key=lambda item: (
                self.status_priority(item.status),
                item.fitness,
                float(item.row.get("risk_score", 0.0)),
                float(item.row.get("memory_pressure_score", 0.0)),
                -int(item.row.get("test_id", 0)),
            ),
            reverse=True,
        )
        return ranked[:limit]

    def mutation_plan(self, vault: SDCVault, limit: int) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []
        for candidate in self.select_candidates(vault, limit):
            plan.append(
                {
                    "parent_testcase_key": candidate.testcase_key,
                    "target_name": candidate.target_name,
                    "policy_name": candidate.policy_name,
                    "fitness": candidate.fitness,
                    "preferred_stride_bytes": candidate.metadata.get(
                        "preferred_stride_bytes", 8192
                    ),
                    "instruction_names": candidate.metadata.get("instruction_names", []),
                    "status": candidate.status,
                }
            )
        return plan

    def record_result(
        self,
        vault: SDCVault,
        testcase_key: str,
        result: Mapping[str, Any],
    ) -> RankedCandidate:
        row = vault.get_testcase(testcase_key)
        if row is None:
            raise KeyError(f"Unknown testcase_key: {testcase_key}")

        payload = _row_to_dict(row)
        metadata = _decode_metadata(payload)
        normalized_status = normalize_runner_status(str(result.get("status", "INVALID")))
        mcpat_summary = result.get("mcpat") or {}
        power_total = mcpat_summary.get("power_total", payload.get("mcpat_power"))
        sdc_signal = self.status_signal(normalized_status)
        fitness = compute_fitness(
            payload.get("ace_score", 0.0),
            payload.get("ibr_score", 0.0),
            payload.get("memory_pressure_score", 0.0),
            sdc_signal,
            power_total,
            memory_bonus_weight=self.config.memory_bonus_weight,
        )

        scheduler_metadata = {
            "source_status": result.get("status"),
            "normalized_status": normalized_status,
            "sdc_signal": sdc_signal,
            "power_total": power_total if power_total is not None else 0.0,
            "fitness": fitness,
            "mcpat_error": result.get("mcpat_error"),
        }

        metadata.update(
            {
                "golden_digest": result.get("golden_digest"),
                "faulted_digest": result.get("faulted_digest"),
                "scheduler": scheduler_metadata,
            }
        )

        vault.update_execution_result(
            testcase_key,
            qemu_golden_hash=result.get("golden_digest"),
            gem5_fault_hash=result.get("faulted_digest"),
            mcpat_power=(
                float(power_total) if power_total is not None else None
            ),
            status=normalized_status,
            metadata=metadata,
        )

        updated = vault.get_testcase(testcase_key)
        assert updated is not None
        return self.rank_row(updated)


def select_candidates(
    vault: SDCVault, limit: int, config: SchedulerConfig | None = None
) -> List[RankedCandidate]:
    return FeedbackScheduler(config=config).select_candidates(vault, limit)


def record_result(
    vault: SDCVault,
    testcase_key: str,
    result: Mapping[str, Any],
    config: SchedulerConfig | None = None,
) -> RankedCandidate:
    return FeedbackScheduler(config=config).record_result(vault, testcase_key, result)
