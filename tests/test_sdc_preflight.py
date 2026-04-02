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
        gem5_binary=tmp_path / "missing-gem5.opt",
        mcpat_binary=tmp_path / "missing-mcpat",
        gem5_config=tmp_path / "missing-config.py",
        vault_path=tmp_path / "artifacts" / "vault.sqlite3",
    )

    assert result["ready"] is False
    failed_checks = {check["name"] for check in result["checks"] if not check["ok"]}
    assert {
        "__missing_compiler__",
        "__missing_qemu__",
        "gem5_binary",
        "mcpat_binary",
        "gem5_config",
    }.issubset(failed_checks)
