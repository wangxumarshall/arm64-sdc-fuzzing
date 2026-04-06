from pathlib import Path

from sdc_agent.preflight import (
    PROFILE_DEV,
    PROFILE_HW,
    PROFILE_SIM,
    check_command,
    check_path,
    run_preflight,
)
from sdc_agent.tooling import HostContext, LocalToolResolution, resolve_local_tools


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
        profile=PROFILE_SIM,
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
    assert any(step["step_id"] == "install_qemu_user" for step in result["missing_steps"])


def test_run_preflight_dev_profile_only_requires_compiler(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sdc_agent.preflight.resolve_local_tools",
        lambda **kwargs: LocalToolResolution(
            compiler="/usr/bin/cc",
            qemu_user_binary=None,
            qemu_system_binary=None,
            gem5_binary=None,
            gem5_config=None,
            mcpat_binary=None,
            meson_binary=None,
            ninja_binary=None,
            opendcdiag_root=None,
        ),
    )
    monkeypatch.setattr(
        "sdc_agent.preflight.get_host_context",
        lambda: HostContext(system="Darwin", machine="arm64", python_version="3.12.2"),
    )

    result = run_preflight(
        profile=PROFILE_DEV,
        vault_path=tmp_path / "artifacts" / "vault.sqlite3",
        check_build_deps=False,
    )

    assert result["ready"] is True
    failed_required = [check["name"] for check in result["checks"] if check["required"] and not check["ok"]]
    assert failed_required == []


def test_run_preflight_hw_profile_requires_hardware_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sdc_agent.preflight.resolve_local_tools",
        lambda **kwargs: LocalToolResolution(
            compiler=None,
            qemu_user_binary=None,
            qemu_system_binary=None,
            gem5_binary=None,
            gem5_config=None,
            mcpat_binary=None,
            meson_binary="/usr/bin/meson",
            ninja_binary=None,
            opendcdiag_root=None,
        ),
    )
    monkeypatch.setattr(
        "sdc_agent.preflight.get_host_context",
        lambda: HostContext(system="Linux", machine="aarch64", python_version="3.12.2"),
    )

    result = run_preflight(
        profile=PROFILE_HW,
        vault_path=tmp_path / "artifacts" / "vault.sqlite3",
        check_build_deps=False,
    )

    assert result["ready"] is False
    failed_required = {check["name"] for check in result["checks"] if check["required"] and not check["ok"]}
    assert {"ninja", "opendcdiag_root"}.issubset(failed_required)


def test_run_preflight_sim_profile_reports_host_incompatibility(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sdc_agent.preflight.get_host_context",
        lambda: HostContext(system="Darwin", machine="arm64", python_version="3.12.2"),
    )

    result = run_preflight(
        profile=PROFILE_SIM,
        compiler="cc",
        qemu_binary="qemu-aarch64",
        qemu_system_binary="qemu-system-aarch64",
        gem5_binary=tmp_path / "missing-gem5.opt",
        mcpat_binary=tmp_path / "missing-mcpat",
        gem5_config=tmp_path / "missing-config.py",
        vault_path=tmp_path / "artifacts" / "vault.sqlite3",
        check_build_deps=False,
    )

    failed_required = {check["name"] for check in result["checks"] if check["required"] and not check["ok"]}
    assert "host_profile_compatibility" in failed_required
    assert any(step["step_id"] == "use_linux_arm_runner" for step in result["missing_steps"])


def test_resolve_local_tools_accepts_native_gcc_on_linux_arm(monkeypatch):
    fake_host = HostContext(system="Linux", machine="aarch64", python_version="3.12.2")
    monkeypatch.setattr("sdc_agent.tooling.get_host_context", lambda: fake_host)

    def fake_which(name: str):
        if name == "gcc":
            return "/usr/bin/gcc"
        return None

    monkeypatch.setattr("shutil.which", fake_which)
    resolved = resolve_local_tools(
        compiler=None,
        qemu_user_binary="__missing__",
        qemu_system_binary="__missing__",
        gem5_binary="__missing__",
        mcpat_binary="__missing__",
        gem5_config="__missing__",
        meson_binary="__missing__",
        ninja_binary="__missing__",
        opendcdiag_root="__missing__",
    )

    assert resolved.compiler == "/usr/bin/gcc"


def test_resolve_local_tools_prefers_env_over_repo_and_path(monkeypatch, tmp_path):
    env_compiler = tmp_path / "env-gcc"
    env_compiler.write_text("#!/bin/sh\n", encoding="utf-8")
    env_compiler.chmod(0o755)

    monkeypatch.setenv("SDC_COMPILER", str(env_compiler))
    monkeypatch.setattr(
        "sdc_agent.tooling.get_host_context",
        lambda: HostContext(system="Linux", machine="aarch64", python_version="3.12.2"),
    )
    monkeypatch.setattr("shutil.which", lambda name: None)

    resolved = resolve_local_tools(
        compiler=None,
        qemu_user_binary="__missing__",
        qemu_system_binary="__missing__",
        gem5_binary="__missing__",
        mcpat_binary="__missing__",
        gem5_config="__missing__",
        meson_binary="__missing__",
        ninja_binary="__missing__",
        opendcdiag_root="__missing__",
    )

    assert resolved.compiler == str(env_compiler.resolve())
