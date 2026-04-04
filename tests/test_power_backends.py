import types
import subprocess
from pathlib import Path

import pytest

from sdc_agent.power_backends.mcpat_backend import McPATBackend
from sdc_agent.power_backends.opendcdiag_backend import OpenDCDiagBackend


def test_mcpat_backend_normalizes_conversion_result(monkeypatch, tmp_path):
    fake_convert_module = types.ModuleType("pypat.conversion.convert")

    def fake_run(target_dir, **kwargs):
        assert kwargs["template_profile"] == "arm64-kunpeng920"
        return {
            "template_profile": kwargs["template_profile"],
            "power_total": 12.5,
            "power_dynamic": 9.25,
            "power_leakage": 3.25,
            "power_peak_dynamic": 14.0,
            "mcpat_input": tmp_path / "conv.xml",
            "mcpat_output": tmp_path / "mcpat_results.txt",
            "mcpat_area_output": tmp_path / "out.area",
            "mcpat_power_trace": tmp_path / "out.ptrace",
            "stats_file": tmp_path / "stats.txt",
            "config_file": tmp_path / "config.json",
        }

    fake_pypat_module = types.ModuleType("pypat")
    fake_conversion_module = types.ModuleType("pypat.conversion")
    monkeypatch.setitem(__import__("sys").modules, "pypat", fake_pypat_module)
    monkeypatch.setitem(
        __import__("sys").modules, "pypat.conversion", fake_conversion_module
    )
    monkeypatch.setitem(
        __import__("sys").modules, "pypat.conversion.convert", fake_convert_module
    )
    fake_convert_module.run = fake_run

    backend = McPATBackend()
    result = backend.run(tmp_path)

    assert result["backend"] == "mcpat"
    assert result["power_total"] == 12.5
    assert result["power_dynamic"] == 9.25
    assert result["power_leakage"] == 3.25
    assert result["target_dir"] == tmp_path.resolve()


def test_opendcdiag_backend_executes_staged_bundle(monkeypatch, tmp_path):
    opendcdiag_root = tmp_path / "opendcdiag"
    meson_path = opendcdiag_root / "tests" / "cpu" / "arm64" / "meson.build"
    meson_path.parent.mkdir(parents=True, exist_ok=True)
    meson_path.write_text(
        "\n".join(
            [
                "arm64_tests = files(",
                "    'sdc_test.cpp',",
                ")",
                "",
            ]
        ),
        encoding="utf-8",
    )
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "arm64_sdc_seed.cpp").write_text("int x = 1;\n", encoding="utf-8")
    (bundle_dir / "promotion.json").write_text(
        '{"testcase_key":"seed","external_test_name":"arm64_sdc_seed","backend_name":"opendcdiag"}\n',
        encoding="utf-8",
    )

    def fake_run(command, *, cwd):
        if command[:2] == ["meson", "setup"]:
            build_dir = Path(command[2])
            build_dir.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(command, 0, "setup ok\n", "")
        if command[:2] == ["meson", "compile"]:
            build_dir = cwd / "builddir"
            build_dir.mkdir(parents=True, exist_ok=True)
            (build_dir / "sandstone").write_text("#!/bin/sh\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "compile ok\n", "")
        return subprocess.CompletedProcess(command, 0, "run ok\n", "")

    monkeypatch.setattr(
        "sdc_agent.power_backends.opendcdiag_backend._run_command",
        fake_run,
    )

    backend = OpenDCDiagBackend(opendcdiag_root=opendcdiag_root)
    result = backend.run(bundle_dir)

    assert result["backend"] == "opendcdiag"
    assert result["result_status"] == "PASS"
    assert Path(result["result_json"]).exists()
    assert result["detectors"]["tap_assertion_count"] == 0
    assert "machine_metadata" in result
    patched_meson = Path(result["meson_file"]).read_text(encoding="utf-8")
    assert "'arm64_sdc_seed.cpp'," in patched_meson
