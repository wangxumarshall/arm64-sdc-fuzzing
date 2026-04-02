import json

from sdc_agent.scheduler import FeedbackScheduler, compute_fitness, normalize_runner_status
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
