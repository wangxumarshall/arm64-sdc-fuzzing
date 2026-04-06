import json
from pathlib import Path

from sdc_agent.phase4_validation import run_phase4_validation


def test_phase4_validation_records_real_campaign_shape(monkeypatch, tmp_path):
    db_path = tmp_path / "phase4.sqlite3"
    output_root = tmp_path / "out"
    elf_path = tmp_path / "phase4.elf"
    elf_path.write_text("elf", encoding="utf-8")
    source_path = tmp_path / "phase4.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    monkeypatch.setattr(
        "sdc_agent.phase4_validation.build_semihost_validation_elf",
        lambda **kwargs: {
            "source_path": source_path.resolve(),
            "boot_obj": tmp_path / "boot.o",
            "linker_script": tmp_path / "kernel.ld",
            "elf_path": elf_path.resolve(),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.phase4_validation.run_qemu_system_golden",
        lambda **kwargs: {
            "command": ["qemu-system-aarch64"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=1111\n",
            "stderr": "",
            "golden_digest": "1111",
        },
    )

    def fake_gem5(**kwargs):
        target = kwargs["output_root"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "stats.txt").write_text("", encoding="utf-8")
        (target / "config.json").write_text("{}", encoding="utf-8")
        return {
            "command": ["gem5"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=1111\n",
            "stderr": "",
            "gem5_digest": "1111",
            "semi_stdout": str(target / "semi.stdout"),
            "semi_stderr": str(target / "semi.stderr"),
        }

    monkeypatch.setattr("sdc_agent.phase4_validation.run_gem5_semihost_validation", fake_gem5)

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {
                "backend": "mcpat",
                "target_dir": target_dir,
                "template_profile": self.template_profile,
                "power_total": 1.5,
                "power_dynamic": 1.2,
                "power_leakage": 0.3,
                "power_peak_dynamic": 2.0,
                "mcpat_input": target_dir / "conv.xml",
                "mcpat_output": target_dir / "mcpat.txt",
                "mcpat_area_output": target_dir / "out.area",
                "mcpat_power_trace": target_dir / "out.ptrace",
                "stats_file": target_dir / "stats.txt",
                "config_file": target_dir / "config.json",
            }

    monkeypatch.setattr("sdc_agent.phase4_validation.McPATBackend", FakeBackend)

    payload = run_phase4_validation(
        db_path=db_path,
        output_root=output_root,
        profile_name="SIM_SAFE",
        compiler="cc",
        qemu_binary=tmp_path / "qemu-system-aarch64",
        gem5_binary=tmp_path / "gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        mcpat_binary=tmp_path / "mcpat",
        fault_models=("register_bit_flip",),
        fault_targets=("x0", "x1"),
        fault_bits=(0,),
        fault_ticks=(100,),
        timeout=5,
    )

    assert payload["summary_status"] == "INVALID"
    assert payload["total_runs"] == 2
    assert len(payload["fault_runs"]) == 2
    assert payload["qemu_golden_digest"] == "1111"
    assert {run["result_status"] for run in payload["fault_runs"]} == {"no_injection"}
    assert payload["fault_execution_plane"] == "phase4_no_injector"

    report_path = Path(payload["report_path"])
    assert report_path.exists()
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["campaign_key"] == payload["campaign_key"]


def test_phase4_validation_allows_none_fault_baseline(monkeypatch, tmp_path):
    db_path = tmp_path / "phase4-none.sqlite3"
    output_root = tmp_path / "out-none"
    elf_path = tmp_path / "phase4-none.elf"
    elf_path.write_text("elf", encoding="utf-8")
    source_path = tmp_path / "phase4-none.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    monkeypatch.setattr(
        "sdc_agent.phase4_validation.build_semihost_validation_elf",
        lambda **kwargs: {
            "source_path": source_path.resolve(),
            "boot_obj": tmp_path / "boot.o",
            "linker_script": tmp_path / "kernel.ld",
            "elf_path": elf_path.resolve(),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.phase4_validation.run_qemu_system_golden",
        lambda **kwargs: {
            "command": ["qemu-system-aarch64"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=abcd\n",
            "stderr": "",
            "golden_digest": "abcd",
        },
    )
    monkeypatch.setattr(
        "sdc_agent.phase4_validation.run_gem5_semihost_validation",
        lambda **kwargs: {
            "command": ["gem5"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=abcd\n",
            "stderr": "",
            "gem5_digest": "abcd",
            "semi_stdout": str((kwargs["output_root"] / "semi.stdout").resolve()),
            "semi_stderr": str((kwargs["output_root"] / "semi.stderr").resolve()),
        },
    )

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {
                "backend": "mcpat",
                "target_dir": target_dir,
                "template_profile": self.template_profile,
                "power_total": 1.0,
                "power_dynamic": 0.8,
                "power_leakage": 0.2,
                "power_peak_dynamic": 1.2,
                "mcpat_input": target_dir / "conv.xml",
                "mcpat_output": target_dir / "mcpat.txt",
                "mcpat_area_output": target_dir / "out.area",
                "mcpat_power_trace": target_dir / "out.ptrace",
                "stats_file": target_dir / "stats.txt",
                "config_file": target_dir / "config.json",
            }

    monkeypatch.setattr("sdc_agent.phase4_validation.McPATBackend", FakeBackend)

    payload = run_phase4_validation(
        db_path=db_path,
        output_root=output_root,
        profile_name="SIM_SAFE",
        compiler="cc",
        qemu_binary=tmp_path / "qemu-system-aarch64",
        gem5_binary=tmp_path / "gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        mcpat_binary=tmp_path / "mcpat",
        fault_models=("none",),
        fault_targets=("",),
        fault_bits=(None,),
        fault_ticks=(None,),
        timeout=5,
    )

    assert payload["summary_status"] == "MATCHED"
    assert payload["total_runs"] == 1
    assert payload["fault_runs"][0]["result_status"] == "matched"


def test_phase4_validation_can_skip_gem5(monkeypatch, tmp_path):
    db_path = tmp_path / "phase4-skip.sqlite3"
    output_root = tmp_path / "out-skip"
    elf_path = tmp_path / "phase4-skip.elf"
    source_path = tmp_path / "phase4-skip.c"
    elf_path.write_text("elf", encoding="utf-8")
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    monkeypatch.setattr(
        "sdc_agent.phase4_validation.build_semihost_validation_elf",
        lambda **kwargs: {
            "source_path": source_path.resolve(),
            "boot_obj": tmp_path / "boot.o",
            "linker_script": tmp_path / "kernel.ld",
            "elf_path": elf_path.resolve(),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.phase4_validation.run_qemu_system_golden",
        lambda **kwargs: {
            "command": ["qemu-system-aarch64"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=beef\n",
            "stderr": "",
            "golden_digest": "beef",
        },
    )

    payload = run_phase4_validation(
        db_path=db_path,
        output_root=output_root,
        profile_name="SIM_SAFE",
        compiler="cc",
        qemu_binary=tmp_path / "qemu-system-aarch64",
        gem5_binary=tmp_path / "gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        mcpat_binary=tmp_path / "mcpat",
        skip_gem5=True,
        skip_mcpat=True,
        timeout=5,
    )

    assert payload["summary_status"] == "MATCHED"
    assert payload["fault_execution_plane"] == "skipped_gem5"
    assert payload["fault_runs"][0]["result_status"] == "matched"
