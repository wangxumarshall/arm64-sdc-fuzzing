from pathlib import Path

from sdc_agent.preflight import check_command, check_path, run_preflight


def test_check_command_reports_missing_binary():
    result = check_command("__definitely_missing_binary__")
    assert result.ok is False
    assert result.required is True


def test_check_path_reports_existing_file(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("ok", encoding="utf-8")
    result = check_path("sample", sample)
    assert result.ok is True
    assert result.path == str(sample.resolve())


def test_run_preflight_is_not_ready_when_required_binaries_are_missing(tmp_path):
    result = run_preflight(
        compiler="__missing_compiler__",
        qemu_binary="__missing_qemu__",
        qemu_system_binary="__missing_system_qemu__",
        gem5_binary=tmp_path / "missing-gem5.opt",
        mcpat_binary=tmp_path / "missing-mcpat",
        gem5_config=tmp_path / "missing-config.py",
        vault_path=tmp_path / "artifacts" / "vault.sqlite3",
        check_build_deps=False,
        check_hardware_tools=True,
        require_qemu_system=True,
    )

    assert result["ready"] is False
    failed_checks = {check["name"] for check in result["checks"] if not check["ok"]}
    assert {
        "compiler",
        "qemu_user_binary",
        "qemu_system_binary",
        "gem5_binary",
        "mcpat_binary",
        "gem5_config",
    }.issubset(failed_checks)
    assert "resolved_paths" in result
    assert result["qemu_user_binary"] is None
    assert result["qemu_system_binary"] is None
    assert any(step["step_id"] == "build_qemu" for step in result["missing_steps"])
