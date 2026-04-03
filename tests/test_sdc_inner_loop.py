from pathlib import Path

from sdc_agent.differential import CommandResult, DifferentialResult
from sdc_agent.inner_loop import run_inner_loop
from sdc_agent.vault import SDCVault, VaultEntry


def _seed_candidate(db_path: Path, *, testcase_key: str, risk_score: float) -> None:
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key=testcase_key,
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=risk_score,
                ibr_score=0.5,
                memory_pressure_score=0.2,
                risk_score=risk_score,
            )
        )


def test_inner_loop_advances_candidates_through_golden_and_power(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    _seed_candidate(db_path, testcase_key="power-seed", risk_score=0.9)
    _seed_candidate(db_path, testcase_key="golden-seed", risk_score=0.4)

    def fake_materialize(vault, testcase_key, *, output_root):
        path = output_root / f"{testcase_key}.c"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        return path

    def fake_run_differential(**kwargs):
        if kwargs["skip_gem5"]:
            return DifferentialResult(
                status="golden_only",
                golden_digest="1111",
                faulted_digest=None,
                compile=CommandResult(["cc"], 0, "", ""),
                qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=1111", ""),
                gem5=None,
                mcpat=None,
                fault_request={"fault_model": "none", "fault_target": ""},
                mcpat_error=None,
            )
        return DifferentialResult(
            status="matched",
            golden_digest="aaaa",
            faulted_digest="aaaa",
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=aaaa", ""),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=aaaa", ""),
            mcpat={"power_total": 2.5, "power_dynamic": 1.1, "power_leakage": 0.3},
            fault_request={"fault_model": "none", "fault_target": ""},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.inner_loop.materialize_testcase", fake_materialize)
    monkeypatch.setattr("sdc_agent.inner_loop.run_differential", fake_run_differential)

    payload = run_inner_loop(
        db_path=db_path,
        output_root=tmp_path / "inner",
        process_limit=2,
        power_limit=1,
        skip_preflight=True,
        enable_evolution=False,
    )

    assert payload["counts"]["processed"] == 2
    assert payload["counts"]["inner_ready"] == 1
    assert payload["counts"]["golden_ready"] == 1

    with SDCVault(db_path) as vault:
        power_row = vault.get_testcase("power-seed")
        golden_row = vault.get_testcase("golden-seed")
        assert power_row is not None
        assert golden_row is not None
        assert power_row["status"] == "INNER_READY"
        assert golden_row["status"] == "GOLDEN_READY"
        assert len(vault.list_inner_runs("power-seed")) == 1
        assert len(vault.list_inner_runs("golden-seed")) == 1
        assert len(vault.list_power_annotations("power-seed")) == 1
        assert len(vault.list_fault_runs("power-seed")) == 0


def test_inner_loop_can_chain_into_evolution(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    _seed_candidate(db_path, testcase_key="seed-a", risk_score=0.7)

    def fake_materialize(vault, testcase_key, *, output_root):
        path = output_root / f"{testcase_key}.c"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        return path

    def fake_run_differential(**kwargs):
        return DifferentialResult(
            status="golden_only",
            golden_digest="beef",
            faulted_digest=None,
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=beef", ""),
            gem5=None,
            mcpat=None,
            fault_request={"fault_model": "none", "fault_target": ""},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.inner_loop.materialize_testcase", fake_materialize)
    monkeypatch.setattr("sdc_agent.inner_loop.run_differential", fake_run_differential)
    monkeypatch.setattr(
        "sdc_agent.inner_loop._run_evolution",
        lambda **kwargs: {"emitted": 2, "records": [{"testcase_key": "child-a"}, {"testcase_key": "child-b"}]},
    )

    payload = run_inner_loop(
        db_path=db_path,
        output_root=tmp_path / "inner",
        process_limit=1,
        power_limit=0,
        skip_preflight=True,
        enable_evolution=True,
    )

    assert payload["counts"]["golden_ready"] == 1
    assert payload["evolve"]["emitted"] == 2
