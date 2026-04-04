from sdc_agent.generation import (
    PROFILE_HW_AGGRESSIVE,
    PROFILE_SIM_SAFE,
    generate_testcase,
    normalize_profile_name,
    resolve_profile_contract,
)


def test_normalize_profile_name_accepts_supported_profiles():
    assert normalize_profile_name("sim_safe") == PROFILE_SIM_SAFE
    assert normalize_profile_name("HW_AGGRESSIVE") == PROFILE_HW_AGGRESSIVE


def test_resolve_profile_contract_keeps_aggressive_profile_active():
    contract = resolve_profile_contract(
        profile_name=PROFILE_HW_AGGRESSIVE,
        instruction_names=None,
    )

    assert contract["requested_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert contract["effective_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert contract["fallback_reason"] is None


def test_generate_testcase_records_requested_and_effective_profile(tmp_path):
    generated = generate_testcase(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "profile_name": PROFILE_HW_AGGRESSIVE,
            "wrapper": "Arm64AsmWrapper",
            "sequence_length": 4,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 23,
            "output_dir": str(tmp_path / "generated"),
        }
    )

    metadata = generated["metadata"]
    assert metadata["requested_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert metadata["profile_name"] == PROFILE_HW_AGGRESSIVE
    assert metadata["effective_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert metadata["profile_contract"]["fallback_reason"] is None
