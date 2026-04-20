from microprobe.utils.arm64_isa_catalog import (
    DEFAULT_CATALOG_PATH,
    load_catalog,
    select_catalog_encodings,
)

from sdc_agent.generation import (
    PROFILE_ALL_GENERATABLE,
    PROFILE_ARMV82_TO_ARMV92_EXECUTABLE,
    PROFILE_ARMV82_TO_ARMV92_GENERATABLE,
    PROFILE_EXECUTABLE_SAFE,
    PROFILE_HW_AGGRESSIVE,
    PROFILE_KUNPENG920_STRESS,
    PROFILE_SIM_SAFE,
    generate_testcase,
    normalize_profile_name,
    resolve_profile_contract,
)


def test_normalize_profile_name_accepts_supported_profiles():
    assert normalize_profile_name("sim_safe") == PROFILE_SIM_SAFE
    assert normalize_profile_name("HW_AGGRESSIVE") == PROFILE_HW_AGGRESSIVE
    assert normalize_profile_name("all_generatable") == PROFILE_ALL_GENERATABLE
    assert normalize_profile_name("executable_safe") == PROFILE_EXECUTABLE_SAFE
    assert normalize_profile_name("kunpeng920_stress") == PROFILE_KUNPENG920_STRESS
    assert (
        normalize_profile_name("armv82_to_armv92_generatable")
        == PROFILE_ARMV82_TO_ARMV92_GENERATABLE
    )
    assert (
        normalize_profile_name("armv82_to_armv92_executable")
        == PROFILE_ARMV82_TO_ARMV92_EXECUTABLE
    )


def test_resolve_profile_contract_keeps_aggressive_profile_active():
    contract = resolve_profile_contract(
        profile_name=PROFILE_HW_AGGRESSIVE,
        instruction_names=None,
    )

    assert contract["requested_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert contract["effective_profile_name"] == PROFILE_HW_AGGRESSIVE
    assert contract["fallback_reason"] is None
    assert contract["generation_mode"] == "synthesizer"


def test_resolve_profile_contract_marks_catalog_profiles():
    contract = resolve_profile_contract(
        profile_name=PROFILE_ALL_GENERATABLE,
        instruction_names=None,
    )

    assert contract["requested_profile_name"] == PROFILE_ALL_GENERATABLE
    assert contract["effective_profile_name"] == PROFILE_ALL_GENERATABLE
    assert contract["generation_mode"] == "catalog"

    windowed = resolve_profile_contract(
        profile_name=PROFILE_ARMV82_TO_ARMV92_EXECUTABLE,
        instruction_names=None,
    )

    assert windowed["requested_profile_name"] == PROFILE_ARMV82_TO_ARMV92_EXECUTABLE
    assert windowed["effective_profile_name"] == PROFILE_ARMV82_TO_ARMV92_EXECUTABLE
    assert windowed["generation_mode"] == "catalog"


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


def test_generate_testcase_supports_catalog_profiles(tmp_path):
    generated = generate_testcase(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "profile_name": PROFILE_ALL_GENERATABLE,
            "wrapper": "BareMetalDiffWrapper",
            "sequence_length": 2,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 41,
            "output_dir": str(tmp_path / "generated"),
        }
    )

    metadata = generated["metadata"]
    output_file = tmp_path / "generated" / f"{generated['entry'].testcase_key}.s"

    assert metadata["requested_profile_name"] == PROFILE_ALL_GENERATABLE
    assert metadata["effective_profile_name"] == PROFILE_ALL_GENERATABLE
    assert metadata["profile_contract"]["generation_mode"] == "catalog"
    assert metadata["requested_wrapper_name"] == "BareMetalDiffWrapper"
    assert generated["wrapper_name"] == "Arm64AsmWrapper"
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8").startswith(".arch armv8-a")


def test_generate_testcase_supports_armv82_to_armv92_catalog_profiles(tmp_path):
    catalog = load_catalog(DEFAULT_CATALOG_PATH)

    for profile_name in [
        PROFILE_ARMV82_TO_ARMV92_GENERATABLE,
        PROFILE_ARMV82_TO_ARMV92_EXECUTABLE,
    ]:
        generated = generate_testcase(
            {
                "target": "armv8_common-armv8_common-aarch64_linux_gcc",
                "policy": "sdc_fuzzing",
                "profile_name": profile_name,
                "wrapper": "BareMetalDiffWrapper",
                "sequence_length": 4,
                "benchmark_size": 32,
                "dependency_distance": 1,
                "memory_stream_stride": 8192,
                "strict_validation": False,
                "seed": 123,
                "output_dir": str(tmp_path / profile_name.lower()),
            }
        )

        expected_encodings = select_catalog_encodings(
            catalog,
            profile_name=profile_name,
            sequence_length=4,
            offset=0,
        )
        metadata = generated["metadata"]
        output_file = (
            tmp_path / profile_name.lower() / f"{generated['entry'].testcase_key}.s"
        )
        rendered = output_file.read_text(encoding="utf-8")

        assert metadata["requested_profile_name"] == profile_name
        assert metadata["effective_profile_name"] == profile_name
        assert metadata["profile_contract"]["generation_mode"] == "catalog"
        assert (
            metadata["profile_contract"]["fallback_reason"]
            == "catalog_profiles_force_arm64_asm_wrapper"
        )
        assert metadata["instruction_mnemonics"] == [
            encoding["mnemonic"] for encoding in expected_encodings
        ]
        assert all(
            encoding["minimum_arch"] != "armv8-a"
            for encoding in expected_encodings
        )
        assert metadata["clang_validation"]["ok"] is True
        assert generated["wrapper_name"] == "Arm64AsmWrapper"
        assert output_file.exists()
        assert rendered.splitlines()[0].startswith(".arch armv")
        assert not rendered.startswith(".arch armv8-a")
