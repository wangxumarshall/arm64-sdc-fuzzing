import json
import subprocess
import sys
from pathlib import Path

import pytest

from sdc_agent.agent import (
    run_cycle,
    run_e2e_dev,
    run_e2e_hw,
    run_e2e_local,
    run_e2e_sim,
    summarize_vault,
)
from sdc_agent.vault import SDCVault, VaultEntry


def test_sdc_agent_summarizes_vault(tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="pending-seed",
                asm_content="mov x0, x0",
                target_name="arm64",
                risk_score=0.5,
                status="PENDING",
            )
        )
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="sdc-seed",
                asm_content="mov x1, x1",
                target_name="arm64",
                ace_score=0.8,
                ibr_score=0.9,
                memory_pressure_score=0.3,
                risk_score=0.9,
                status="SDC_FOUND",
                metadata={
                    "scheduler": {
                        "normalized_status": "SDC_FOUND",
                        "sdc_signal": 1.0,
                        "power_total": 1.0,
                    },
                    "outer_loop": {
                        "outer_value_score": 0.2,
                        "injector_confidence_score": 1.0,
                        "promotion_readiness_score": 0.2,
                        "promotion_ready": True,
                        "execution_planes": {"gem5_scripted": 1},
                    },
                },
            )
        )

    payload = summarize_vault(db_path, limit=2)

    assert payload["counts"]["ALL"] == 2
    assert payload["counts"]["PENDING"] == 1
    assert payload["counts"]["SDC_FOUND"] == 1
    assert payload["top_candidates"][0]["testcase_key"] == "sdc-seed"
    assert payload["top_candidates"][0]["inner_value_score"] > 0.0
    assert payload["top_candidates"][0]["promotion_ready"] is True
    assert payload["top_promotion_candidates"][0]["testcase_key"] == "sdc-seed"
    assert payload["managed_domains_summary"]["domain_count"] == 6
    assert set(payload["runtime_capabilities"]["profiles"].keys()) == {"dev", "sim", "hw"}


def test_sdc_agent_cli_help_runs_without_microprobe_runtime_bootstrap():
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str((repo_root / "tools" / "sdc_agent.py").resolve()), "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "e2e-sim" in completed.stdout


def test_sdc_agent_run_cycle_composes_generate_campaign_and_evolve(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-a",
                asm_content="mov x0, x0",
                target_name="arm64",
                ace_score=0.6,
                ibr_score=0.7,
                memory_pressure_score=0.2,
                risk_score=0.8,
                status="PENDING",
            )
        )

    monkeypatch.setattr(
        "sdc_agent.agent.generate_batch",
        lambda **kwargs: {"requested": 4, "inserted": 4, "failed": [], "db": str(db_path)},
    )
    monkeypatch.setattr(
        "sdc_agent.agent.execute_campaign",
        lambda **kwargs: {"ok": True, "counts": {"executed": 1}, "runs": []},
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_evolution",
        lambda **kwargs: {"emitted": 2, "records": []},
    )

    payload = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "agent",
        generate_count=4,
        generate_jobs=1,
        campaign_limit=1,
        parent_limit=1,
        offspring_per_parent=2,
        max_offspring=2,
        target="armv8_common-armv8_common-aarch64_linux_gcc",
        policy="sdc_fuzzing",
        generate_profile="SIM_SAFE",
        generation_strategy="baseline",
        template_name=None,
        generate_wrapper="Arm64AsmWrapper",
        evolve_wrapper="Arm64AsmWrapper",
        sequence_length=4,
        benchmark_size=32,
        dependency_distance=1,
        strict_validation=False,
        compiler="cc",
        qemu_binary="qemu-aarch64",
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        fault_model="none",
        fault_target="",
        fault_bit=None,
        fault_tick=None,
        skip_gem5=True,
        skip_mcpat=True,
        skip_preflight=True,
        timeout=5,
    )

    assert payload["generate"]["inserted"] == 4
    assert payload["campaign"]["ok"] is True
    assert payload["evolve"]["emitted"] == 2
    assert payload["summary"]["counts"]["ALL"] == 1


def test_sdc_agent_run_e2e_sim_writes_unified_report(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-sim"
    db_path = output_root / "vault.sqlite3"

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
                "gem5_config": str((tmp_path / "baremetal.py").resolve()),
                "mcpat_binary": str((tmp_path / "mcpat").resolve()),
                "meson_binary": "/opt/homebrew/bin/meson",
                "ninja_binary": "/opt/homebrew/bin/ninja",
                "opendcdiag_root": str((tmp_path / "opendcdiag").resolve()),
            },
            "missing_steps": [],
            "qemu_user_binary": "/tmp/qemu-aarch64",
            "qemu_system_binary": "/tmp/qemu-system-aarch64",
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_phase2_validation",
        lambda **kwargs: {
            "status": "INNER_READY",
            "report_path": str((output_root / "phase2" / "phase2-validation.json").resolve()),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_phase4_validation",
        lambda **kwargs: {
            "summary_status": "MATCHED",
            "report_path": str((output_root / "phase4" / "phase4-validation.json").resolve()),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_cycle",
        lambda **kwargs: {
            "generate": {"inserted": 4},
            "campaign": {"counts": {"executed": 2}},
            "evolve": {"emitted": 2},
            "summary": {"counts": {"ALL": 6}},
        },
    )
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

    assert payload["mode"] == "e2e-sim"
    assert payload["phase2"]["status"] == "INNER_READY"
    assert payload["phase4"]["summary_status"] == "MATCHED"

    report_path = Path(payload["report_json"])
    assert report_path.exists()
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["resolved_paths"]["compiler"] == "cc"
    assert report_payload["build"]["requested"] is False


def test_sdc_agent_run_e2e_sim_can_skip_gem5(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-sim-skip"
    db_path = output_root / "vault.sqlite3"

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
                "gem5_binary": None,
                "gem5_config": str((tmp_path / "baremetal.py").resolve()),
                "mcpat_binary": str((tmp_path / "mcpat").resolve()),
                "meson_binary": None,
                "ninja_binary": None,
                "opendcdiag_root": str((tmp_path / "opendcdiag").resolve()),
            },
            "missing_steps": [],
            "qemu_user_binary": "/tmp/qemu-aarch64",
            "qemu_system_binary": "/tmp/qemu-system-aarch64",
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_phase2_validation",
        lambda **kwargs: {
            "status": "GOLDEN_READY",
            "report_path": str((output_root / "phase2" / "phase2-validation.json").resolve()),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_phase4_validation",
        lambda **kwargs: {
            "summary_status": "MATCHED",
            "report_path": str((output_root / "phase4" / "phase4-validation.json").resolve()),
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_cycle",
        lambda **kwargs: {
            "generate": {"inserted": 4},
            "campaign": {"counts": {"executed": 2}},
            "evolve": {"emitted": 2},
            "summary": {"counts": {"ALL": 6}},
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.summarize_vault",
        lambda db_path, limit=5: {"counts": {"ALL": 6}, "db": str(db_path)},
    )

    payload = run_e2e_sim(
        output_root=output_root,
        db_path=db_path,
        build_missing=False,
        skip_gem5=True,
        skip_mcpat=True,
        timeout=5,
    )

    assert payload["mode"] == "e2e-sim"
    assert payload["skip_gem5"] is True
    assert payload["phase2"]["status"] == "GOLDEN_READY"


def test_sdc_agent_run_e2e_dev_generates_materialized_smoke(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-dev"
    db_path = output_root / "vault.sqlite3"

    monkeypatch.setattr(
        "sdc_agent.agent.run_preflight",
        lambda **kwargs: {
            "ready": True,
            "profile": "dev",
            "checks": [],
            "resolved_paths": {
                "compiler": "cc",
                "qemu_user_binary": None,
                "qemu_system_binary": None,
                "gem5_binary": None,
                "gem5_config": None,
                "mcpat_binary": None,
                "meson_binary": None,
                "ninja_binary": None,
                "opendcdiag_root": None,
            },
            "missing_steps": [],
            "qemu_user_binary": None,
            "qemu_system_binary": None,
        },
    )

    def fake_generate_batch(**kwargs):
        with SDCVault(kwargs["db_path"]) as vault:
            vault.upsert_testcase(
                VaultEntry(
                    testcase_key="dev-seed",
                    asm_content="mov x0, x0",
                    target_name="arm64",
                    status="PENDING",
                )
            )
        return {
            "requested": 1,
            "planned": 1,
            "inserted": 1,
            "testcase_keys": ["dev-seed"],
            "failed": [],
            "db": str(kwargs["db_path"]),
        }

    monkeypatch.setattr("sdc_agent.agent.generate_batch", fake_generate_batch)
    monkeypatch.setattr(
        "sdc_agent.agent.summarize_vault",
        lambda db_path, limit=5: {"counts": {"ALL": 1}, "db": str(db_path)},
    )

    payload = run_e2e_dev(
        output_root=output_root,
        db_path=db_path,
        build_missing=False,
        timeout=5,
    )

    assert payload["mode"] == "e2e-dev"
    assert payload["generate"]["inserted"] == 1
    assert payload["materialized_source"].endswith("dev-seed.c")
    report_payload = json.loads(Path(payload["report_json"]).read_text(encoding="utf-8"))
    assert report_payload["invoked_as"] == "e2e-dev"


def test_sdc_agent_run_e2e_dev_normalizes_materialized_asm(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-dev-normalized"
    db_path = output_root / "vault.sqlite3"

    monkeypatch.setattr(
        "sdc_agent.agent.run_preflight",
        lambda **kwargs: {
            "ready": True,
            "profile": "dev",
            "checks": [],
            "resolved_paths": {
                "compiler": "cc",
                "qemu_user_binary": None,
                "qemu_system_binary": None,
                "gem5_binary": None,
                "gem5_config": None,
                "mcpat_binary": None,
                "meson_binary": None,
                "ninja_binary": None,
                "opendcdiag_root": None,
            },
            "missing_steps": [],
            "qemu_user_binary": None,
            "qemu_system_binary": None,
        },
    )

    def fake_generate_batch(**kwargs):
        with SDCVault(kwargs["db_path"]) as vault:
            vault.upsert_testcase(
                VaultEntry(
                    testcase_key="dev-normalized",
                    asm_content="\n".join(
                        [
                            "MOVZ x29, 6189, 0",
                            "MOVK x29, 55662, 1",
                            "FMLA v11, v6, v4",
                            "FMSUB v8, v2, v11, v5",
                        ]
                    ),
                    target_name="arm64",
                    status="PENDING",
                )
            )
        return {
            "requested": 1,
            "planned": 1,
            "inserted": 1,
            "testcase_keys": ["dev-normalized"],
            "failed": [],
            "db": str(kwargs["db_path"]),
        }

    monkeypatch.setattr("sdc_agent.agent.generate_batch", fake_generate_batch)
    monkeypatch.setattr(
        "sdc_agent.agent.summarize_vault",
        lambda db_path, limit=5: {"counts": {"ALL": 1}, "db": str(db_path)},
    )

    payload = run_e2e_dev(
        output_root=output_root,
        db_path=db_path,
        build_missing=False,
        timeout=5,
    )

    materialized = Path(payload["materialized_source"]).read_text(encoding="utf-8")

    assert "movz x29, #6189, lsl #0" in materialized
    assert "movk x29, #55662, lsl #16" in materialized
    assert "fmadd d11, d6, d4, d11" in materialized
    assert "fmsub d8, d2, d11, d5" in materialized
    assert "MOVK x29, 55662, 1" not in materialized
    assert "FMLA v11, v6, v4" not in materialized


def test_sdc_agent_run_e2e_dev_fails_when_generation_emits_no_valid_testcases(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-dev-fail"
    db_path = output_root / "vault.sqlite3"

    monkeypatch.setattr(
        "sdc_agent.agent.run_preflight",
        lambda **kwargs: {
            "ready": True,
            "profile": "dev",
            "checks": [],
            "resolved_paths": {
                "compiler": "cc",
                "qemu_user_binary": None,
                "qemu_system_binary": None,
                "gem5_binary": None,
                "gem5_config": None,
                "mcpat_binary": None,
                "meson_binary": None,
                "ninja_binary": None,
                "opendcdiag_root": None,
            },
            "missing_steps": [],
            "qemu_user_binary": None,
            "qemu_system_binary": None,
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.generate_batch",
        lambda **kwargs: {
            "requested": 1,
            "planned": 1,
            "inserted": 0,
            "testcase_keys": [],
            "failed": [{"index": 0, "error": "schema mismatch"}],
            "db": str(kwargs["db_path"]),
        },
    )

    with pytest.raises(RuntimeError, match="generation emitted no valid testcases"):
        run_e2e_dev(
            output_root=output_root,
            db_path=db_path,
            build_missing=False,
            timeout=5,
        )


def test_sdc_agent_run_e2e_local_maps_to_dev_alias(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sdc_agent.agent.run_e2e_dev",
        lambda **kwargs: {
            "ok": True,
            "mode": "e2e-dev",
            "invoked_as": kwargs["invoked_as"],
            "report_json": str((tmp_path / "report.json").resolve()),
        },
    )

    payload = run_e2e_local(
        output_root=tmp_path / "e2e-local",
        db_path=tmp_path / "vault.sqlite3",
        build_missing=False,
        timeout=5,
    )

    assert payload["mode"] == "e2e-dev"
    assert payload["invoked_as"] == "e2e-local"


def test_sdc_agent_run_e2e_hw_writes_unified_report(monkeypatch, tmp_path):
    output_root = tmp_path / "e2e-hw"
    db_path = output_root / "vault.sqlite3"

    monkeypatch.setattr(
        "sdc_agent.agent.run_preflight",
        lambda **kwargs: {
            "ready": True,
            "profile": "hw",
            "checks": [],
            "resolved_paths": {
                "compiler": None,
                "qemu_user_binary": None,
                "qemu_system_binary": None,
                "gem5_binary": None,
                "gem5_config": None,
                "mcpat_binary": None,
                "meson_binary": "/usr/bin/meson",
                "ninja_binary": "/usr/bin/ninja",
                "opendcdiag_root": str((tmp_path / "opendcdiag").resolve()),
            },
            "missing_steps": [],
            "qemu_user_binary": None,
            "qemu_system_binary": None,
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.run_hardware_promotion",
        lambda **kwargs: {
            "promotions": [
                {
                    "promotion_id": 7,
                    "testcase_key": "seed-hw",
                    "status": "EMITTED",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.execute_hardware_promotions",
        lambda **kwargs: {
            "executed": [
                {
                    "promotion_id": 7,
                    "result_status": "PASS",
                    "ingest": {"hardware_run_id": 9},
                }
            ]
        },
    )
    monkeypatch.setattr(
        "sdc_agent.agent.summarize_vault",
        lambda db_path, limit=5: {"counts": {"ALL": 1}, "db": str(db_path)},
    )

    payload = run_e2e_hw(
        output_root=output_root,
        db_path=db_path,
        build_missing=False,
    )

    assert payload["mode"] == "e2e-hw"
    assert payload["latest_promotion"]["promotion_id"] == 7
    assert payload["latest_hardware_run"]["promotion_id"] == 7
