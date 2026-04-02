import json
from pathlib import Path

import pytest

from sdc_agent.differential import CommandResult, DifferentialResult
from sdc_agent.campaign import execute_campaign
from sdc_agent.vault import SDCVault, VaultEntry


def _seed_vault(db_path: Path, *, testcase_key: str, source_path: Path) -> None:
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key=testcase_key,
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=4.0,
                ibr_score=3.0,
                memory_pressure_score=1.0,
                risk_score=9.0,
                metadata={"source_path": str(source_path)},
            )
        )


def test_execute_campaign_dry_run_plans_candidates(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    source_path = tmp_path / "seed-a.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    _seed_vault(db_path, testcase_key="seed-a", source_path=source_path)

    monkeypatch.setattr(
        "sdc_agent.campaign.run_preflight",
        lambda **kwargs: {"ready": False, "checks": [], "repo_root": str(tmp_path)},
    )

    result = execute_campaign(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=tmp_path / "campaign",
        dry_run=True,
        skip_preflight=False,
        compiler="cc",
        compiler_flags=[],
        qemu_binary="qemu-aarch64",
        qemu_args=[],
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        gem5_args=[],
        gem5_cmd_flag="auto",
        fault_model="none",
        fault_target="",
        fault_bit=None,
        fault_tick=None,
        skip_gem5=False,
        skip_mcpat=False,
        mcpat_template_profile="arm64-kunpeng920",
        mcpat_binary=tmp_path / "mcpat",
        timeout=30,
    )

    assert result["ok"] is True
    assert result["counts"]["planned"] == 1
    assert result["runs"][0]["action"] == "planned"
    assert result["runs"][0]["source_path"] == str(source_path.resolve())


def test_execute_campaign_records_results(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    source_path = tmp_path / "seed-b.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    _seed_vault(db_path, testcase_key="seed-b", source_path=source_path)

    monkeypatch.setattr(
        "sdc_agent.campaign.run_preflight",
        lambda **kwargs: {"ready": True, "checks": [], "repo_root": str(tmp_path)},
    )

    def fake_run_differential(**kwargs):
        assert kwargs["fault_model"] == "register_bit_flip"
        assert kwargs["fault_target"] == "x0"
        assert kwargs["fault_bit"] == 3
        assert kwargs["fault_tick"] == 900
        return DifferentialResult(
            status="sdc_found",
            golden_digest="1111",
            faulted_digest="2222",
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=1111", ""),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=2222", ""),
            mcpat={"power_total": 2.5},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.campaign.run_differential", fake_run_differential)

    output_root = tmp_path / "campaign"
    result = execute_campaign(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=output_root,
        dry_run=False,
        skip_preflight=False,
        compiler="cc",
        compiler_flags=[],
        qemu_binary="qemu-aarch64",
        qemu_args=[],
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        gem5_args=[],
        gem5_cmd_flag="auto",
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=3,
        fault_tick=900,
        skip_gem5=False,
        skip_mcpat=False,
        mcpat_template_profile="arm64-kunpeng920",
        mcpat_binary=tmp_path / "mcpat",
        timeout=30,
    )

    assert result["ok"] is True
    assert result["counts"]["executed"] == 1
    assert result["runs"][0]["action"] == "executed"
    assert result["runs"][0]["result_status"] == "sdc_found"
    assert result["runs"][0]["artifact_dir"] is not None

    result_json = output_root / "seed-b" / "result.json"
    assert result_json.exists()
    payload = json.loads(result_json.read_text(encoding="utf-8"))
    assert payload["status"] == "sdc_found"

    with SDCVault(db_path) as vault:
        row = vault.get_testcase("seed-b")
        assert row is not None
        assert row["status"] == "SDC_FOUND"
        metadata = json.loads(row["metadata_json"])
        assert metadata["campaign"]["result_json"] == str(result_json.resolve())
        assert metadata["scheduler"]["normalized_status"] == "SDC_FOUND"


def test_execute_campaign_materializes_source_from_vault(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-m",
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=4.0,
                ibr_score=3.0,
                memory_pressure_score=1.0,
                risk_score=9.0,
                metadata={},
            )
        )

    monkeypatch.setattr(
        "sdc_agent.campaign.run_preflight",
        lambda **kwargs: {"ready": True, "checks": [], "repo_root": str(tmp_path)},
    )

    def fake_run_differential(**kwargs):
        source = kwargs["source"]
        assert source.exists()
        assert "mov x0, x0" in source.read_text(encoding="utf-8")
        return DifferentialResult(
            status="matched",
            golden_digest="aaaa",
            faulted_digest="aaaa",
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=aaaa", ""),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=aaaa", ""),
            mcpat={"power_total": 1.0},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.campaign.run_differential", fake_run_differential)

    result = execute_campaign(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=tmp_path / "campaign",
        dry_run=False,
        skip_preflight=False,
        compiler="cc",
        compiler_flags=[],
        qemu_binary="qemu-aarch64",
        qemu_args=[],
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        gem5_args=[],
        gem5_cmd_flag="auto",
        fault_model="none",
        fault_target="",
        fault_bit=None,
        fault_tick=None,
        skip_gem5=False,
        skip_mcpat=False,
        mcpat_template_profile="arm64-kunpeng920",
        mcpat_binary=tmp_path / "mcpat",
        timeout=30,
    )

    assert result["ok"] is True
    assert result["counts"]["executed"] == 1
    with SDCVault(db_path) as vault:
        row = vault.get_testcase("seed-m")
        assert row is not None
        metadata = json.loads(row["metadata_json"])
        assert metadata["source_path"].endswith("seed-m.c")
        assert metadata["materialized"]["source_path"].endswith("seed-m.c")


def test_execute_campaign_blocks_when_preflight_fails(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    source_path = tmp_path / "seed-c.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    _seed_vault(db_path, testcase_key="seed-c", source_path=source_path)

    monkeypatch.setattr(
        "sdc_agent.campaign.run_preflight",
        lambda **kwargs: {"ready": False, "checks": [], "repo_root": str(tmp_path)},
    )

    with pytest.raises(RuntimeError):
        execute_campaign(
            db_path=db_path,
            limit=1,
            source_root=None,
            output_root=tmp_path / "campaign",
            dry_run=False,
            skip_preflight=False,
            compiler="cc",
            compiler_flags=[],
            qemu_binary="qemu-aarch64",
            qemu_args=[],
            gem5_binary="gem5.opt",
            gem5_config=tmp_path / "cfg.py",
            gem5_args=[],
            gem5_cmd_flag="auto",
            fault_model="none",
            fault_target="",
            fault_bit=None,
            fault_tick=None,
            skip_gem5=False,
            skip_mcpat=False,
            mcpat_template_profile="arm64-kunpeng920",
            mcpat_binary=tmp_path / "mcpat",
            timeout=30,
        )
