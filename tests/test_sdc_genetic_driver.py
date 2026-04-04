from sdc_agent.generation import bootstrap_microprobe_paths, generate_testcase
from sdc_agent.vault import SDCVault

bootstrap_microprobe_paths()

from microprobe.driver.genetic import EvolutionConfig, SDCFuzzingGeneticDriver


def test_sdc_genetic_driver_emits_offspring_into_vault(tmp_path):
    parent = generate_testcase(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "wrapper": "Arm64AsmWrapper",
            "profile_name": "SIM_SAFE",
            "sequence_length": 4,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 19,
            "output_dir": str(tmp_path / "parents"),
            "instruction_names": ["MOVZ_X_V0", "MOVZ_X_V0", "MOVZ_X_V0", "MOVZ_X_V0"],
        }
    )

    db_path = tmp_path / "vault.sqlite3"
    config = EvolutionConfig(
        parent_limit=1,
        offspring_per_parent=1,
        max_offspring=1,
        sequence_length=4,
        benchmark_size=32,
        wrapper_name="Arm64AsmWrapper",
        base_seed=301,
    )

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(parent["entry"])
        driver = SDCFuzzingGeneticDriver(config=config)
        records = driver.evolve(vault, output_dir=tmp_path / "evolved")

        assert len(records) == 1
        child = records[0]
        assert child.testcase_key != parent["entry"].testcase_key
        row = vault.get_testcase(child.testcase_key)
        assert row is not None
        assert row["status"] == "PENDING"
        metadata = child.metadata
        assert metadata["lineage"]["driver"] == "SDCFuzzingGeneticDriver"
        assert metadata["lineage"]["generation"] == 1
        assert metadata["lineage"]["selected_partner_reason"] == "single_parent_fallback"
        assert metadata["lineage"]["dependency_distance"] == 1
        assert metadata["lineage"]["preferred_stride_bytes"] >= 8192
        assert metadata["evolution_feedback"]["selected_partner"] == parent["entry"].testcase_key
        assert metadata["preferred_stride_bytes"] >= 8192
        assert metadata["requested_profile_name"] == "SIM_SAFE"


def test_sdc_genetic_driver_uses_profile_aware_instruction_fallback(monkeypatch):
    class Candidate:
        def __init__(self, profile_name: str):
            self.metadata = {
                "requested_profile_name": profile_name,
                "profile_name": profile_name,
            }

    driver = SDCFuzzingGeneticDriver(config=EvolutionConfig(sequence_length=4))

    observed = []

    def fake_fallback(target_name: str, *, profile_name: str = "SIM_SAFE"):
        observed.append((target_name, profile_name))
        return [f"{profile_name}_OP"]

    monkeypatch.setattr(driver, "_fallback_instruction_names", fake_fallback)

    names = driver._instruction_names_for(Candidate("HW_AGGRESSIVE"), "arm64-target")

    assert names == ["HW_AGGRESSIVE_OP"]
    assert observed == [("arm64-target", "HW_AGGRESSIVE")]
