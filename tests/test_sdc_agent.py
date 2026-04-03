from sdc_agent.agent import run_cycle, summarize_vault
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
                    }
                },
            )
        )

    payload = summarize_vault(db_path, limit=2)

    assert payload["counts"]["ALL"] == 2
    assert payload["counts"]["PENDING"] == 1
    assert payload["counts"]["SDC_FOUND"] == 1
    assert payload["top_candidates"][0]["testcase_key"] == "sdc-seed"


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
