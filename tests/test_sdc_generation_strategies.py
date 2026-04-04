from sdc_agent.generation import generate_testcase
from sdc_agent.generation_strategies import (
    GENERATION_STRATEGY_PCFG,
    GENERATION_STRATEGY_TEMPLATE,
    normalize_generation_strategy,
    recommend_generation_recipe,
)


def test_normalize_generation_strategy_accepts_supported_values():
    assert normalize_generation_strategy("baseline") == "baseline"
    assert normalize_generation_strategy("template") == "template"
    assert normalize_generation_strategy("PCFG") == "pcfg"


def test_generate_testcase_records_template_strategy_metadata(tmp_path):
    generated = generate_testcase(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "profile_name": "SIM_SAFE",
            "generation_strategy": GENERATION_STRATEGY_TEMPLATE,
            "template_name": "cache_thrash",
            "wrapper": "Arm64AsmWrapper",
            "sequence_length": 6,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 31,
            "output_dir": str(tmp_path / "generated"),
        }
    )

    metadata = generated["metadata"]
    assert metadata["generation_strategy"] == "template"
    assert metadata["template_name"] == "cache_thrash"
    assert metadata["template_version"] == 1
    assert metadata["template_mnemonics"]
    assert len(metadata["instruction_names"]) == 6


def test_generate_testcase_records_pcfg_strategy_metadata(tmp_path):
    generated = generate_testcase(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "profile_name": "HW_AGGRESSIVE",
            "generation_strategy": GENERATION_STRATEGY_PCFG,
            "template_name": "neon_fma_heavy",
            "wrapper": "Arm64AsmWrapper",
            "sequence_length": 5,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 37,
            "output_dir": str(tmp_path / "generated"),
        }
    )

    metadata = generated["metadata"]
    assert metadata["generation_strategy"] == "pcfg"
    assert metadata["template_name"] == "neon_fma_heavy"
    assert metadata["template_family_weights"]
    assert len(metadata["instruction_names"]) == 5


def test_recommend_generation_recipe_prefers_aggressive_template_for_vector_families():
    recipe = recommend_generation_recipe(
        profile_name="HW_AGGRESSIVE",
        instruction_families=("FMADD", "LD1"),
    )

    assert recipe["generation_strategy"] == "pcfg"
    assert recipe["template_name"] == "neon_fma_heavy"
