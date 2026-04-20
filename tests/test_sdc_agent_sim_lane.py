import subprocess
from pathlib import Path

from sdc_agent.agent import _run_profile_preflight, run_e2e_sim
from sdc_agent.tooling import DEFAULT_GEM5_BAREMETAL_CONFIG


def test_run_profile_preflight_build_missing_runs_qemu_auto_build(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    calls = []
    responses = [
        {
            "ready": False,
            "missing_steps": [
                {
                    "step_id": "build_qemu",
                    "command": ["/repo/scripts/build_qemu_headless.sh"],
                    "cwd": "/repo",
                    "auto_build": True,
                }
            ],
        },
        {
            "ready": True,
            "missing_steps": [],
        },
    ]

    monkeypatch.setattr("sdc_agent.agent.run_preflight", lambda **kwargs: responses.pop(0))

    def fake_subprocess_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    preflight, build_results = _run_profile_preflight(
        profile="sim",
        db_path=db_path,
        build_missing=True,
        error_mode="e2e-sim",
        error_message="Simulation E2E preflight failed.",
    )

    assert preflight["ready"] is True
    assert build_results[0]["step_id"] == "build_qemu"
    assert calls[0][0] == ["bash", "/repo/scripts/build_qemu_headless.sh"]


def test_run_profile_preflight_build_missing_skips_auto_build_when_manual_steps_remain(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    preflight_response = {
        "ready": False,
        "missing_steps": [
            {
                "step_id": "install_build_dependencies",
                "command": ["/repo/scripts/bootstrap_ubuntu_24_04_arm.sh"],
                "cwd": "/repo",
                "auto_build": False,
            },
            {
                "step_id": "build_qemu",
                "command": ["/repo/scripts/build_qemu_headless.sh"],
                "cwd": "/repo",
                "auto_build": True,
            },
        ],
    }

    monkeypatch.setattr("sdc_agent.agent.run_preflight", lambda **kwargs: preflight_response)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("auto-build should not run")),
    )

    try:
        _run_profile_preflight(
            profile="sim",
            db_path=db_path,
            build_missing=True,
            error_mode="e2e-sim",
            error_message="Simulation E2E preflight failed.",
        )
    except RuntimeError as exc:
        assert "Simulation E2E preflight failed." in str(exc)
    else:
        raise AssertionError("expected preflight failure")


def test_run_e2e_sim_uses_baremetal_config_for_phase_validations(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-sim"
    db_path = output_root / "vault.sqlite3"
    se_config = tmp_path / "sdc_kunpeng920_se.py"
    se_config.write_text("# se\n", encoding="utf-8")
    captured = {}

    monkeypatch.setattr(
        "sdc_agent.agent.run_preflight",
        lambda **kwargs: {
            "ready": True,
            "profile": "sim",
            "checks": [],
            "resolved_paths": {
                "compiler": "cc",
                "qemu_user_binary": "/tmp/qemu-aarch64",
                "qemu_system_binary": "/tmp/qemu-system-aarch64",
                "gem5_binary": "/tmp/gem5.opt",
                "gem5_config": str(se_config.resolve()),
                "mcpat_binary": str((tmp_path / "mcpat").resolve()),
                "meson_binary": "/usr/bin/meson",
                "ninja_binary": "/usr/bin/ninja",
                "opendcdiag_root": str((tmp_path / "opendcdiag").resolve()),
            },
            "missing_steps": [],
            "qemu_user_binary": "/tmp/qemu-aarch64",
            "qemu_system_binary": "/tmp/qemu-system-aarch64",
        },
    )

    def fake_phase2(**kwargs):
        captured["phase2_gem5_config"] = kwargs["gem5_config"]
        return {"status": "INNER_READY"}

    def fake_phase4(**kwargs):
        captured["phase4_gem5_config"] = kwargs["gem5_config"]
        return {"summary_status": "MATCHED"}

    def fake_cycle(**kwargs):
        captured["cycle_gem5_config"] = kwargs["gem5_config"]
        return {
            "generate": {"inserted": 4},
            "campaign": {"counts": {"executed": 2}},
            "evolve": {"emitted": 2},
            "summary": {"counts": {"ALL": 6}},
        }

    monkeypatch.setattr("sdc_agent.agent.run_phase2_validation", fake_phase2)
    monkeypatch.setattr("sdc_agent.agent.run_phase4_validation", fake_phase4)
    monkeypatch.setattr("sdc_agent.agent.run_cycle", fake_cycle)
    monkeypatch.setattr(
        "sdc_agent.agent.summarize_vault",
        lambda db_path, limit=5: {"counts": {"ALL": 6}, "db": str(db_path)},
    )

    payload = run_e2e_sim(
        output_root=output_root,
        db_path=db_path,
        build_missing=False,
        timeout=5,
    )

    assert Path(captured["phase2_gem5_config"]).resolve() == DEFAULT_GEM5_BAREMETAL_CONFIG.resolve()
    assert Path(captured["phase4_gem5_config"]).resolve() == DEFAULT_GEM5_BAREMETAL_CONFIG.resolve()
    assert Path(captured["cycle_gem5_config"]).resolve() == se_config.resolve()
    assert Path(payload["resolved_paths"]["gem5_baremetal_config"]).resolve() == DEFAULT_GEM5_BAREMETAL_CONFIG.resolve()
    assert Path(payload["resolved_paths"]["gem5_cycle_config"]).resolve() == se_config.resolve()
