import json
import stat
import sys
from pathlib import Path


MCPAT_ROOT = Path(__file__).resolve().parents[1]
if str(MCPAT_ROOT) not in sys.path:
    sys.path.insert(0, str(MCPAT_ROOT))

from pypat.conversion.calibration import (  # noqa: E402
    DEFAULT_CALIBRATION_FILENAME,
    build_kunpeng920_calibration,
)
from pypat.conversion.convert import run  # noqa: E402
from pypat.conversion.profiles import normalize_gem5_config  # noqa: E402


def _write_run(root: Path, name: str, *, label: str, duration_s: int, energy_uj: int,
               hpre_recv: int = 0, sec_recv: int = 0, zip_recv: int = 0,
               perf_lines: list[str] | None = None) -> Path:
    run_dir = root / name
    (run_dir / "meta").mkdir(parents=True)
    (run_dir / "delta").mkdir(parents=True)
    (run_dir / "before").mkdir(parents=True)
    (run_dir / "after").mkdir(parents=True)

    (run_dir / "meta" / "run.env").write_text(
        "\n".join(
            [
                f"label={label}",
                "command=sleep 1",
                f"workload_duration_s={duration_s}",
                "workload_exit_code=0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "delta" / "powercap.tsv").write_text(
        f"/sys/class/powercap/intel-rapl:0/energy_uj\t0\t{energy_uj}\t{energy_uj}\n",
        encoding="utf-8",
    )
    (run_dir / "delta" / "hisi_hpre.tsv").write_text(
        f"/sys/kernel/debug/hisi_hpre/0000:00:00.0/hpre_dfx/recv_cnt\t0\t{hpre_recv}\t{hpre_recv}\n",
        encoding="utf-8",
    )
    (run_dir / "delta" / "hisi_sec2.tsv").write_text(
        f"/sys/kernel/debug/hisi_sec2/0000:00:00.0/sec_dfx/recv_cnt\t0\t{sec_recv}\t{sec_recv}\n",
        encoding="utf-8",
    )
    (run_dir / "delta" / "hisi_zip.tsv").write_text(
        f"/sys/kernel/debug/hisi_zip/0000:00:00.0/zip_dfx/recv_cnt\t0\t{zip_recv}\t{zip_recv}\n",
        encoding="utf-8",
    )
    if perf_lines:
        (run_dir / "perf_stat.csv").write_text("\n".join(perf_lines) + "\n", encoding="utf-8")
    return run_dir


def test_build_kunpeng920_calibration_generates_override_table(tmp_path):
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    (dataset_root / "area_overrides.json").write_text(
        json.dumps(
            {
                "custom_hpre_area": 12.5,
                "custom_hccs_area": 8.0,
            }
        ),
        encoding="utf-8",
    )

    _write_run(dataset_root, "idle", label="idle", duration_s=2, energy_uj=4_000_000)
    _write_run(dataset_root, "hpre", label="hpre rsa2048", duration_s=2, energy_uj=12_000_000, hpre_recv=4)
    _write_run(
        dataset_root,
        "hccs",
        label="hccs stream remote-numa",
        duration_s=1,
        energy_uj=5_000_000,
        perf_lines=["100,,hisi_sccl0_hha0/rx_operations/,0,0,"],
    )

    output_file = dataset_root / DEFAULT_CALIBRATION_FILENAME
    payload = build_kunpeng920_calibration(dataset_root, output_file)

    assert output_file.exists()
    assert payload["overrides"]["custom_hpre_area"] == 12.5
    assert payload["overrides"]["custom_hccs_area"] == 8.0
    assert payload["overrides"]["custom_hpre_switch_energy"] == 2.0
    assert payload["overrides"]["custom_hccs_switch_energy"] == 0.03


def test_normalize_gem5_config_applies_calibration_file(tmp_path):
    calibration_file = tmp_path / DEFAULT_CALIBRATION_FILENAME
    calibration_file.write_text(
        json.dumps(
            {
                "profile_name": "arm64-kunpeng920",
                "overrides": {
                    "custom_hpre_switch_energy": 1.25,
                    "custom_hpre_static_power": 0.75,
                },
            }
        ),
        encoding="utf-8",
    )
    config = {
        "system": {"isa": "ArmISA"},
        "board": {"processor": {"num_cores": 64}},
    }

    normalized, selected = normalize_gem5_config(
        config,
        "arm64-kunpeng920",
        calibration_file=calibration_file,
    )

    assert selected == "arm64-kunpeng920"
    assert normalized["profile"]["custom_hpre_switch_energy"] == 1.25
    assert normalized["profile"]["custom_hpre_static_power"] == 0.75


def test_run_uses_calibration_dataset_to_generate_runtime_overrides(tmp_path):
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    _write_run(dataset_root, "idle", label="idle", duration_s=1, energy_uj=2_000_000)
    _write_run(dataset_root, "zip", label="zip gzip compress", duration_s=1, energy_uj=5_000_000, zip_recv=3)

    target_dir = tmp_path / "m5out"
    target_dir.mkdir()
    (target_dir / "config.json").write_text(
        json.dumps(
            {
                "system": {"isa": "ArmISA"},
                "board": {"processor": {"num_cores": 64}},
            }
        ),
        encoding="utf-8",
    )
    (target_dir / "stats.txt").write_text("simTicks 1000000\n---------- End Simulation Statistics ----------\n", encoding="utf-8")

    fake_mcpat = tmp_path / "fake-mcpat.sh"
    fake_mcpat.write_text(
        "#!/bin/sh\n"
        "echo 'Total Leakage = 1 W'\n"
        "echo 'Runtime Dynamic = 2 W'\n",
        encoding="utf-8",
    )
    fake_mcpat.chmod(fake_mcpat.stat().st_mode | stat.S_IXUSR)

    result = run(
        target_dir=target_dir,
        template_profile="arm64-kunpeng920",
        mcpat_binary=fake_mcpat,
        calibration_dataset=dataset_root,
    )

    calibration_file = target_dir / DEFAULT_CALIBRATION_FILENAME
    assert calibration_file.exists()
    payload = json.loads(calibration_file.read_text(encoding="utf-8"))
    assert payload["overrides"]["custom_zip_switch_energy"] == 1.0
    assert result["calibration_file"] == str(calibration_file)
