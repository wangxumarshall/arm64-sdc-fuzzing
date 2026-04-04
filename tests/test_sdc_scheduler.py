import json

from sdc_agent.scheduler import (
    FeedbackScheduler,
    compute_diversity_bonus,
    compute_fitness,
    compute_inner_value_score,
    normalize_runner_status,
)
from sdc_agent.vault import SDCVault, VaultEntry


def test_normalize_runner_status_maps_execution_results():
    assert normalize_runner_status("golden_only") == "GOLDEN_READY"
    assert normalize_runner_status("matched") == "MATCHED"
    assert normalize_runner_status("sdc_found") == "SDC_FOUND"
    assert normalize_runner_status("gem5_timeout") == "TIMEOUT"
    assert normalize_runner_status("compile_failed") == "INVALID"


def test_compute_fitness_prefers_lower_power_when_signal_matches():
    low_power = compute_fitness(0.8, 0.9, 0.5, 1.0, 2.0)
    high_power = compute_fitness(0.8, 0.9, 0.5, 1.0, 9.0)
    assert low_power > high_power


def test_inner_value_score_rewards_diversity_and_legality():
    low_diversity = compute_inner_value_score(
        0.8,
        status="PENDING",
        power_total=None,
        diversity_bonus=compute_diversity_bonus(["MOVZ_X_V0"]),
    )
    high_diversity = compute_inner_value_score(
        0.8,
        status="GOLDEN_READY",
        power_total=1.0,
        diversity_bonus=compute_diversity_bonus(
            ["MOVZ_X_V0", "LDR_XI", "STR_XI", "ADD_XI"],
            profile_name="HW_AGGRESSIVE",
        ),
    )
    assert high_diversity > low_diversity


def test_scheduler_records_execution_feedback_and_updates_vault(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-1",
                asm_content="// seed-1",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=0.8,
                ibr_score=0.9,
                memory_pressure_score=0.4,
                risk_score=0.7,
            )
        )
        scheduler = FeedbackScheduler()
        ranked = scheduler.record_result(
            vault,
            "seed-1",
            {
                "status": "sdc_found",
                "golden_digest": "1111",
                "faulted_digest": "2222",
                "mcpat": {"power_total": 3.5},
                "mcpat_error": None,
            },
        )
        row = vault.get_testcase("seed-1")
        assert row is not None
        metadata = json.loads(row["metadata_json"])

        assert row["status"] == "SDC_FOUND"
        assert row["qemu_golden_hash"] == "1111"
        assert row["gem5_fault_hash"] == "2222"
        assert row["mcpat_power"] == 3.5
        assert metadata["scheduler"]["normalized_status"] == "SDC_FOUND"
        assert metadata["scheduler"]["sdc_signal"] == 1.0
        assert ranked.fitness > 0.0
    finally:
        vault.close()


def test_scheduler_select_candidates_prefers_sdc_hits_over_pending(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="pending-high-risk",
                asm_content="// pending",
                target_name="arm64",
                ace_score=0.9,
                ibr_score=0.9,
                memory_pressure_score=0.9,
                risk_score=0.95,
                status="PENDING",
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="sdc-hit",
                asm_content="// hit",
                target_name="arm64",
                ace_score=0.8,
                ibr_score=0.85,
                memory_pressure_score=0.4,
                risk_score=0.6,
                status="SDC_FOUND",
                mcpat_power=1.5,
                metadata={
                    "scheduler": {
                        "normalized_status": "SDC_FOUND",
                        "sdc_signal": 1.0,
                        "power_total": 1.5,
                        "fitness": 0.0,
                    }
                },
            )
        )
        scheduler = FeedbackScheduler()
        ranked = scheduler.select_candidates(vault, 2)

        assert [candidate.testcase_key for candidate in ranked] == [
            "sdc-hit",
            "pending-high-risk",
        ]
    finally:
        vault.close()


def test_scheduler_select_candidates_prefers_inner_ready_over_pending(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="pending-seed",
                asm_content="// pending",
                target_name="arm64",
                ace_score=0.95,
                ibr_score=0.95,
                memory_pressure_score=0.95,
                risk_score=0.99,
                status="PENDING",
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="inner-ready-seed",
                asm_content="// ready",
                target_name="arm64",
                ace_score=0.7,
                ibr_score=0.8,
                memory_pressure_score=0.5,
                risk_score=0.75,
                status="INNER_READY",
            )
        )

        scheduler = FeedbackScheduler()
        ranked = scheduler.select_candidates(vault, 2)
        assert [candidate.testcase_key for candidate in ranked] == [
            "inner-ready-seed",
            "pending-seed",
        ]
    finally:
        vault.close()


def test_scheduler_select_candidates_prefers_observed_outer_loop_signal(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        common_fields = {
            "asm_content": "// outer",
            "target_name": "arm64",
            "ace_score": 0.8,
            "ibr_score": 0.8,
            "memory_pressure_score": 0.4,
            "risk_score": 0.7,
            "status": "SDC_FOUND",
        }
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="manifest-only-seed",
                metadata={
                    "scheduler": {
                        "normalized_status": "SDC_FOUND",
                        "sdc_signal": 1.0,
                        "power_total": 2.0,
                    },
                    "outer_loop": {
                        "outer_value_score": 0.2,
                        "injector_confidence_score": 0.0,
                        "promotion_readiness_score": 0.0,
                        "promotion_ready": False,
                    },
                },
                **common_fields,
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="observed-seed",
                metadata={
                    "scheduler": {
                        "normalized_status": "SDC_FOUND",
                        "sdc_signal": 1.0,
                        "power_total": 2.0,
                    },
                    "outer_loop": {
                        "outer_value_score": 0.2,
                        "injector_confidence_score": 1.0,
                        "promotion_readiness_score": 0.2,
                        "promotion_ready": True,
                    },
                },
                **common_fields,
            )
        )

        scheduler = FeedbackScheduler()
        ranked = scheduler.select_candidates(vault, 2)
        assert [candidate.testcase_key for candidate in ranked] == [
            "observed-seed",
            "manifest-only-seed",
        ]
    finally:
        vault.close()


def test_scheduler_select_candidates_prefers_higher_inner_value_score_when_outer_signals_tie(
    tmp_path,
):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        common_fields = {
            "asm_content": "// inner",
            "target_name": "arm64",
            "ace_score": 0.8,
            "ibr_score": 0.8,
            "memory_pressure_score": 0.4,
            "risk_score": 0.8,
            "status": "GOLDEN_READY",
        }
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="narrow-seed",
                metadata={
                    "profile_name": "SIM_SAFE",
                    "instruction_names": ["MOVZ_X_V0", "MOVZ_X_V0", "MOVZ_X_V0"],
                },
                **common_fields,
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="diverse-seed",
                metadata={
                    "profile_name": "HW_AGGRESSIVE",
                    "instruction_names": ["MOVZ_X_V0", "LDR_XI", "STR_XI", "ADD_XI"],
                },
                **common_fields,
            )
        )

        scheduler = FeedbackScheduler()
        ranked = scheduler.select_candidates(vault, 2)
        assert [candidate.testcase_key for candidate in ranked] == [
            "diverse-seed",
            "narrow-seed",
        ]
        assert ranked[0].inner_value_score > ranked[1].inner_value_score
        assert ranked[0].diversity_bonus > ranked[1].diversity_bonus
    finally:
        vault.close()


def test_scheduler_promotion_plan_filters_and_orders_candidates(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="pending-seed",
                asm_content="// pending",
                target_name="arm64",
                risk_score=0.5,
                status="PENDING",
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="matched-seed",
                asm_content="// matched",
                target_name="arm64",
                ace_score=0.7,
                ibr_score=0.7,
                memory_pressure_score=0.3,
                risk_score=0.6,
                status="MATCHED",
                metadata={
                    "outer_loop": {
                        "outer_value_score": 0.15,
                        "injector_confidence_score": 0.5,
                        "promotion_readiness_score": 0.075,
                        "promotion_ready": False,
                        "execution_planes": {"manifest_only": 2},
                    }
                },
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="promote-seed",
                asm_content="// promote",
                target_name="arm64",
                ace_score=0.75,
                ibr_score=0.8,
                memory_pressure_score=0.4,
                risk_score=0.8,
                status="SDC_FOUND",
                metadata={
                    "outer_loop": {
                        "outer_value_score": 0.25,
                        "injector_confidence_score": 1.0,
                        "promotion_readiness_score": 0.25,
                        "promotion_ready": True,
                        "execution_planes": {"gem5_scripted": 2},
                    }
                },
            )
        )

        scheduler = FeedbackScheduler()
        plan = scheduler.promotion_plan(vault, 5)

        assert [item["testcase_key"] for item in plan] == [
            "promote-seed",
            "matched-seed",
        ]
        assert plan[0]["promotion_ready"] is True
        assert plan[0]["fault_execution_plane"] == {"gem5_scripted": 2}
    finally:
        vault.close()


def test_scheduler_mutation_plan_exposes_phase3_feedback_breakdown(tmp_path):
    vault = SDCVault(tmp_path / "vault.sqlite3")
    try:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-feedback",
                asm_content="// feedback",
                target_name="arm64",
                ace_score=0.8,
                ibr_score=0.7,
                memory_pressure_score=0.5,
                risk_score=0.8,
                status="INNER_READY",
                metadata={
                    "profile_name": "HW_AGGRESSIVE",
                    "instruction_names": ["MOVZ_X_V0", "LDR_XI", "STR_XI", "ADD_XI"],
                    "preferred_stride_bytes": 12288,
                },
            )
        )

        scheduler = FeedbackScheduler()
        plan = scheduler.mutation_plan(vault, 1)

        assert len(plan) == 1
        assert plan[0]["parent_testcase_key"] == "seed-feedback"
        assert plan[0]["profile_name"] == "HW_AGGRESSIVE"
        assert plan[0]["inner_value_score"] > 0.0
        assert plan[0]["diversity_bonus"] > 1.0
        assert "LDR" in plan[0]["instruction_families"]
        assert plan[0]["generation_strategy"] == "pcfg"
        assert plan[0]["template_name"] == "neon_fma_heavy"
        assert plan[0]["mutation_advice"]["recommended_fault_model"] == "memory_bit_flip"
        assert plan[0]["mutation_advice"]["recommended_template_name"] == "neon_fma_heavy"
    finally:
        vault.close()
