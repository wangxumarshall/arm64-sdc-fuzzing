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
        assert metadata["preferred_stride_bytes"] >= 8192
        assert metadata["requested_profile_name"] == "SIM_SAFE"
