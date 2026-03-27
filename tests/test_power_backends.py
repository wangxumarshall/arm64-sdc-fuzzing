import types

import pytest

from power_backends.mcpat_backend import McPATBackend
from power_backends.opendcdiag_backend import OpenDCDiagBackend


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


def test_opendcdiag_backend_is_deferred(tmp_path):
    backend = OpenDCDiagBackend()
    with pytest.raises(NotImplementedError):
        backend.run(tmp_path)
