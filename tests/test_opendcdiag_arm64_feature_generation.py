from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "opendcdiag" / "framework" / "device" / "cpu" / "scripts" / "arm64_features_generate.pl"
CONFIG = REPO_ROOT / "opendcdiag" / "framework" / "device" / "cpu" / "arm64_features.conf"


def test_arm64_feature_generation_script_emits_sve2_support(tmp_path):
    header_path = tmp_path / "cpu_features.h"
    completed = subprocess.run(
        ["perl", str(SCRIPT), str(CONFIG), str(header_path.name)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    generated = completed.stdout

    assert "#define cpu_feature_sve2" in generated
    assert "#define cpu_armv9_sve2" in generated
    assert "struct Arm64HwcapLocator" in generated
    assert "arm64_architectures" in generated


def test_arm64_hwcap_parser_recognizes_sve2_profile(tmp_path):
    header_path = tmp_path / "cpu_features.h"
    generated = subprocess.run(
        ["perl", str(SCRIPT), str(CONFIG), str(header_path.name)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    header_path.write_text(generated, encoding="utf-8")

    source_path = tmp_path / "arm64_feature_probe.cpp"
    binary_path = tmp_path / "arm64_feature_probe"
    source_path.write_text(
        textwrap.dedent(
            """
            #include "device/cpu/arm64/arm64_cpuid.h"

            int main()
            {{
                const unsigned long hwcap =
                    (1UL << 0) |   // fp
                    (1UL << 1) |   // asimd
                    (1UL << 22);   // sve
                const unsigned long hwcap2 =
                    (1UL << 1);    // sve2

                const device_features_t features =
                    arm64_detect_cpu_features_from_hwcap(hwcap, hwcap2);

                if (!arm64_has_feature_mask(features, cpu_feature_fp)) {{
                    return 1;
                }}
                if (!arm64_has_feature_mask(features, cpu_feature_asimd)) {{
                    return 2;
                }}
                if (!arm64_has_feature_mask(features, cpu_feature_sve)) {{
                    return 3;
                }}
                if (!arm64_has_feature_mask(features, cpu_feature_sve2)) {{
                    return 4;
                }}
                if (!arm64_has_feature_mask(features, cpu_armv9_sve2)) {{
                    return 5;
                }}
                return 0;
            }}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    compile_result = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-I",
            str(tmp_path),
            "-I",
            str(REPO_ROOT / "opendcdiag" / "framework"),
            str(source_path),
            "-o",
            str(binary_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert compile_result.returncode == 0, compile_result.stderr

    run_result = subprocess.run(
        [str(binary_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
