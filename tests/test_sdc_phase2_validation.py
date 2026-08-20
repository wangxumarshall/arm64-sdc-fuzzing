from pathlib import Path

from sdc_agent.phase2_validation import render_semihost_validation_source, run_phase2_validation


def test_render_semihost_validation_source_uses_defined_state_harness():
    source = render_semihost_validation_source("mov x0, x1\nfmov d0, d1", "phase2-seed")

    assert "Phase2 validation source for phase2-seed" in source
    assert "static void sdc_prepare_memory(void)" in source
    assert "static uint8_t sdc_memory[8192]" in source
    assert "str x30, [x16, #240]" in source
    assert "adrp x18, sdc_memory" in source


def test_run_phase2_validation_can_skip_gem5(monkeypatch, tmp_path):
    db_path = tmp_path / "phase2.sqlite3"
    output_root = tmp_path / "out"
    elf_path = tmp_path / "phase2.elf"
    source_path = tmp_path / "phase2.c"
    elf_path.write_text("elf", encoding="utf-8")
    source_path.write_text("int main(void){return 0;}\n", encoding="utf-8")

    monkeypatch.setattr(
        "sdc_agent.phase2_validation.build_semihost_validation_elf",
        lambda **kwargs: {
            "source_path": source_path.resolve(),
            "boot_obj": tmp_path / "boot.o",
            "linker_script": tmp_path / "kernel.ld",
            "elf_path": elf_path.resolve(),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.phase2_validation.run_qemu_system_golden",
        lambda **kwargs: {
            "command": ["qemu-system-aarch64"],
            "returncode": 0,
            "stdout": "SDC_DIGEST=abcd\n",
            "stderr": "",
            "golden_digest": "abcd",
        },
    )

    payload = run_phase2_validation(
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

    assert payload["status"] == "GOLDEN_READY"
    assert payload["gem5"]["fault_execution_plane"] == "skipped_gem5"
    assert payload["mcpat"] is None
