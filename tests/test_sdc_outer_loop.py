import json
from pathlib import Path

from sdc_agent.differential import CommandResult, DifferentialResult
from sdc_agent.outer_loop import plan_fault_matrix, run_outer_loop
from sdc_agent.vault import SDCVault, VaultEntry


def _seed_inner_ready(db_path: Path, *, testcase_key: str, source_path: Path) -> None:
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key=testcase_key,
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=1.0,
                ibr_score=0.8,
                memory_pressure_score=0.5,
                risk_score=0.9,
                status="INNER_READY",
                metadata={"source_path": str(source_path)},
            )
        )


def test_plan_fault_matrix_cross_product_and_none_handling():
    specs = plan_fault_matrix(
        fault_models=("register_bit_flip", "none"),
        fault_targets=("x0", "x1"),
        fault_bits=(0, 1),
        fault_ticks=(100, 200),
    )
    assert len(specs) == 9
    assert any(spec.fault_model == "none" for spec in specs)
    assert any(
        spec.fault_model == "register_bit_flip"
        and spec.fault_target == "x1"
        and spec.fault_bit == 1
        and spec.fault_tick == 200
        for spec in specs
    )


def test_outer_loop_dry_run_plans_multiple_faults(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    source_path = tmp_path / "seed-a.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    _seed_inner_ready(db_path, testcase_key="seed-a", source_path=source_path)

    monkeypatch.setattr(
        "sdc_agent.outer_loop.run_preflight",
        lambda **kwargs: {"ready": True, "checks": [], "repo_root": str(tmp_path)},
    )

    payload = run_outer_loop(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=tmp_path / "outer",
        fault_models=("register_bit_flip",),
        fault_targets=("x0", "x1"),
        fault_bits=(0, 1),
        fault_ticks=(100,),
        dry_run=True,
        skip_preflight=False,
        compiler="cc",
        qemu_binary="qemu-aarch64",
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        timeout=30,
    )

    assert payload["ok"] is True
    assert payload["counts"]["selected"] == 1
    assert payload["counts"]["planned_runs"] == 4
    assert len(payload["planned_runs"]) == 4
    assert payload["campaign"]["status"] == "PLANNED"
    with SDCVault(db_path) as vault:
        campaigns = vault.list_fault_campaigns(limit=5)
        assert len(campaigns) == 1
        assert campaigns[0]["status"] == "PLANNED"
        fetched = vault.get_fault_campaign(payload["campaign_key"])
        assert fetched is not None
        assert fetched["campaign_key"] == payload["campaign_key"]


def test_outer_loop_executes_fault_runs_and_aggregates(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    source_path = tmp_path / "seed-b.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    _seed_inner_ready(db_path, testcase_key="seed-b", source_path=source_path)

    monkeypatch.setattr(
        "sdc_agent.outer_loop.run_preflight",
        lambda **kwargs: {"ready": True, "checks": [], "repo_root": str(tmp_path)},
    )

    def fake_run_differential(**kwargs):
        if kwargs["fault_target"] == "x0":
            status = "sdc_found"
            faulted = "2222"
            fault_request = {
                "fault_model": kwargs["fault_model"],
                "fault_target": kwargs["fault_target"],
                "fault_bit": kwargs["fault_bit"],
                "fault_tick": kwargs["fault_tick"],
                "execution_plane": "gem5_scripted",
                "implemented_in_script": True,
                "injection_observed": True,
            }
        else:
            status = "matched"
            faulted = "1111"
            fault_request = {
                "fault_model": kwargs["fault_model"],
                "fault_target": kwargs["fault_target"],
                "fault_bit": kwargs["fault_bit"],
                "fault_tick": kwargs["fault_tick"],
                "execution_plane": "manifest_only",
                "implemented_in_script": False,
                "injection_observed": False,
            }
        return DifferentialResult(
            status=status,
            golden_digest="1111",
            faulted_digest=faulted,
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=1111", ""),
            gem5=CommandResult(["gem5"], 0, f"SDC_DIGEST={faulted}", ""),
            mcpat={"power_total": 2.0},
            fault_request=fault_request,
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.outer_loop.run_differential", fake_run_differential)

    payload = run_outer_loop(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=tmp_path / "outer",
        fault_models=("register_bit_flip",),
        fault_targets=("x0", "x1"),
        fault_bits=(0,),
        fault_ticks=(100,),
        dry_run=False,
        skip_preflight=False,
        compiler="cc",
        qemu_binary="qemu-aarch64",
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        timeout=30,
    )

    assert payload["counts"]["executed_runs"] == 2
    assert payload["counts"]["aggregated"] == 1
    assert len(payload["aggregates"]) == 1
    assert payload["aggregates"][0]["testcase_key"] == "seed-b"
    assert payload["aggregates"][0]["summary_status"] == "SDC_FOUND"
    assert payload["campaign"]["status"] == "COMPLETED"
    assert payload["campaign"]["fault_run_count"] >= 2

    with SDCVault(db_path) as vault:
        row = vault.get_testcase("seed-b")
        assert row is not None
        assert row["status"] == "SDC_FOUND"
        metadata = json.loads(row["metadata_json"])
        assert metadata["outer_loop"]["total_runs"] == 2
        assert metadata["outer_loop"]["active_fault_runs"] == 2
        assert metadata["outer_loop"]["sdc_hits"] == 1
        assert metadata["outer_loop"]["fault_detection_rate"] == 0.5
        assert metadata["outer_loop"]["observed_injection_runs"] == 1
        assert metadata["outer_loop"]["manifest_only_runs"] == 1
        assert metadata["outer_loop"]["injector_confidence_score"] == 0.5
        assert metadata["outer_loop"]["promotion_ready"] is True
        assert metadata["outer_loop"]["summary_status"] == "SDC_FOUND"
        fault_runs = vault.list_fault_runs("seed-b", limit=10)
        assert len(fault_runs) >= 2
        run_metadata = [json.loads(row["metadata_json"]) for row in fault_runs]
        execution_planes = {
            item["fault_execution_plane"]
            for item in run_metadata
            if "fault_execution_plane" in item
        }
        assert execution_planes == {
            "gem5_scripted",
            "manifest_only",
        }
        campaigns = vault.list_fault_campaigns(limit=5)
        assert campaigns[0]["status"] == "COMPLETED"
        fetched = vault.get_fault_campaign(payload["campaign_key"])
        assert fetched is not None
        by_campaign = vault.list_fault_runs_for_campaign(int(fetched["campaign_id"]), limit=10)
        assert len(by_campaign) >= 2
