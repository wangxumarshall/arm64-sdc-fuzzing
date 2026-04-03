#!/usr/bin/env python3
"""Feedback-driven scheduler for the ARM64 SDC fuzzing loop."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .vault import SDCVault


DEFAULT_CANDIDATE_STATUSES = (
    "INNER_READY",
    "POWER_READY",
    "PENDING",
    "GOLDEN_READY",
    "MATCHED",
    "SDC_FOUND",
)


@dataclass(frozen=True)
class SchedulerConfig:
    """Tunable knobs for seed ranking and feedback integration."""

    candidate_statuses: Sequence[str] = DEFAULT_CANDIDATE_STATUSES
    promotion_candidate_statuses: Sequence[str] = ("SDC_FOUND", "MATCHED")
    scan_limit_per_status: int = 128
    memory_bonus_weight: float = 0.25
    pending_signal: float = 0.35
    golden_ready_signal: float = 0.45
    power_ready_signal: float = 0.50
    inner_ready_signal: float = 0.60
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
    outer_value_score: float
    injector_confidence_score: float
    promotion_readiness_score: float
    promotion_ready: bool
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


def _command_summary(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    return {
        "command": list(payload.get("command", [])),
        "returncode": payload.get("returncode"),
        "timed_out": bool(payload.get("timed_out", False)),
        "status": "ok" if payload.get("returncode") == 0 else "failed",
    }


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool_or_default(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


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
        if normalized == "INNER_READY":
            return self.config.inner_ready_signal
        if normalized == "POWER_READY":
            return self.config.power_ready_signal
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
            "INNER_READY": 3,
            "POWER_READY": 2,
            "GOLDEN_READY": 2,
            "PENDING": 1,
            "MATCHED": 0,
        }
        return priorities.get(normalized, 0)

    def _outer_loop_metrics(self, metadata: Mapping[str, Any]) -> Dict[str, Any]:
        outer_loop = metadata.get("outer_loop", {})
        if not isinstance(outer_loop, Mapping):
            outer_loop = {}
        return {
            "outer_value_score": _float_or_default(outer_loop.get("outer_value_score"), 0.0),
            "injector_confidence_score": _float_or_default(
                outer_loop.get("injector_confidence_score"), 0.0
            ),
            "promotion_readiness_score": _float_or_default(
                outer_loop.get("promotion_readiness_score"), 0.0
            ),
            "promotion_ready": _bool_or_default(
                outer_loop.get("promotion_ready"),
                False,
            ),
        }

    def _selection_sort_key(self, candidate: RankedCandidate) -> tuple[Any, ...]:
        return (
            self.status_priority(candidate.status),
            candidate.promotion_ready,
            candidate.promotion_readiness_score,
            candidate.injector_confidence_score,
            candidate.outer_value_score,
            candidate.fitness,
            float(candidate.row.get("risk_score", 0.0)),
            float(candidate.row.get("memory_pressure_score", 0.0)),
            -int(candidate.row.get("test_id", 0)),
        )

    def _promotion_sort_key(self, candidate: RankedCandidate) -> tuple[Any, ...]:
        return (
            candidate.promotion_ready,
            candidate.promotion_readiness_score,
            candidate.injector_confidence_score,
            candidate.outer_value_score,
            candidate.fitness,
            float(candidate.row.get("risk_score", 0.0)),
            -int(candidate.row.get("test_id", 0)),
        )

    def rank_row(self, row: Mapping[str, Any]) -> RankedCandidate:
        payload = _row_to_dict(row)
        metadata = _decode_metadata(payload)
        outer_loop_metrics = self._outer_loop_metrics(metadata)
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
            outer_value_score=float(outer_loop_metrics["outer_value_score"]),
            injector_confidence_score=float(
                outer_loop_metrics["injector_confidence_score"]
            ),
            promotion_readiness_score=float(
                outer_loop_metrics["promotion_readiness_score"]
            ),
            promotion_ready=bool(outer_loop_metrics["promotion_ready"]),
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
        ranked.sort(key=self._selection_sort_key, reverse=True)
        return ranked[:limit]

    def select_promotion_candidates(
        self,
        vault: SDCVault,
        limit: int,
    ) -> List[RankedCandidate]:
        statuses = tuple(self.config.promotion_candidate_statuses)
        rows: List[Mapping[str, Any]] = []
        for status in statuses:
            rows.extend(
                vault.list_testcases(
                    limit=self.config.scan_limit_per_status,
                    status=status,
                )
            )

        ranked = [self.rank_row(row) for row in rows]
        ranked = [
            candidate
            for candidate in ranked
            if candidate.outer_value_score > 0.0 or candidate.promotion_ready
        ]
        ranked.sort(key=self._promotion_sort_key, reverse=True)
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

    def promotion_plan(self, vault: SDCVault, limit: int) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []
        for candidate in self.select_promotion_candidates(vault, limit):
            plan.append(
                {
                    "testcase_key": candidate.testcase_key,
                    "status": candidate.status,
                    "fitness": candidate.fitness,
                    "outer_value_score": candidate.outer_value_score,
                    "injector_confidence_score": candidate.injector_confidence_score,
                    "promotion_readiness_score": candidate.promotion_readiness_score,
                    "promotion_ready": candidate.promotion_ready,
                    "fault_execution_plane": candidate.metadata.get("outer_loop", {}).get(
                        "execution_planes", {}
                    ),
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
                "mcpat": mcpat_summary,
                "fault_request": result.get("fault_request") or {},
                "execution": {
                    "compile": _command_summary(result.get("compile")),
                    "qemu": _command_summary(result.get("qemu")),
                    "gem5": _command_summary(result.get("gem5")),
                },
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


def _ranked_candidate_to_dict(candidate: RankedCandidate) -> Dict[str, Any]:
    return {
        "testcase_key": candidate.testcase_key,
        "target_name": candidate.target_name,
        "policy_name": candidate.policy_name,
        "status": candidate.status,
        "static_score": candidate.static_score,
        "sdc_signal": candidate.sdc_signal,
        "power_total": candidate.power_total,
        "fitness": candidate.fitness,
        "outer_value_score": candidate.outer_value_score,
        "injector_confidence_score": candidate.injector_confidence_score,
        "promotion_readiness_score": candidate.promotion_readiness_score,
        "promotion_ready": candidate.promotion_ready,
        "risk_score": candidate.row.get("risk_score", 0.0),
        "memory_pressure_score": candidate.row.get("memory_pressure_score", 0.0),
        "metadata": candidate.metadata,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank, plan, and record feedback for the ARM64 SDC vault."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ["rank", "plan", "promotion-plan"]:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--db", type=Path, required=True, help="Vault path.")
        subparser.add_argument(
            "--limit", type=int, default=10, help="Number of candidates to emit."
        )

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--db", type=Path, required=True, help="Vault path.")
    record_parser.add_argument(
        "--testcase-key", required=True, help="Testcase key to update."
    )
    record_parser.add_argument(
        "--result-json",
        type=Path,
        required=True,
        help="JSON file emitted by tools/run_sdc_differential.py.",
    )

    return parser


def main() -> int:
    args = _build_parser().parse_args()
    scheduler = FeedbackScheduler()

    with SDCVault(args.db) as vault:
        if args.command == "rank":
            payload = [
                _ranked_candidate_to_dict(candidate)
                for candidate in scheduler.select_candidates(vault, args.limit)
            ]
        elif args.command == "promotion-plan":
            payload = scheduler.promotion_plan(vault, args.limit)
        elif args.command == "plan":
            payload = scheduler.mutation_plan(vault, args.limit)
        else:
            result_payload = json.loads(args.result_json.read_text(encoding="utf-8"))
            candidate = scheduler.record_result(
                vault, args.testcase_key, result_payload
            )
            payload = _ranked_candidate_to_dict(candidate)

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
