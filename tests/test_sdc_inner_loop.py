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


def test_inner_loop_reuses_source_elf_and_golden_cache(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    output_root = tmp_path / "inner"
    source_path = tmp_path / "cached-source.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    elf_dir = output_root / "cached-seed"
    elf_dir.mkdir(parents=True, exist_ok=True)
    elf_path = elf_dir / "cached-seed.elf"
    elf_path.write_text("cached elf", encoding="utf-8")

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="cached-seed",
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=0.8,
                ibr_score=0.7,
                memory_pressure_score=0.3,
                risk_score=0.8,
                status="GOLDEN_READY",
                qemu_golden_hash="face",
                metadata={
                    "source_path": str(source_path),
                    "golden_digest": "face",
                    "execution": {
                        "compile": {"status": "ok", "returncode": 0},
                        "qemu": {"status": "ok", "returncode": 0},
                    },
                },
            )
        )

    observed = {}

    def fake_run_differential(**kwargs):
        observed["skip_compile"] = kwargs["skip_compile"]
        observed["skip_qemu"] = kwargs["skip_qemu"]
        observed["cached_golden_digest"] = kwargs["cached_golden_digest"]
        return DifferentialResult(
            status="matched",
            golden_digest="face",
            faulted_digest="face",
            compile=CommandResult([], 0, "", "Skipped compilation; reused cached ELF."),
            qemu=CommandResult([], 0, "SDC_DIGEST=face", "Skipped QEMU; reused cached golden digest."),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=face", ""),
            mcpat={"power_total": 1.0},
            fault_request={"fault_model": "none", "fault_target": ""},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.inner_loop.run_differential", fake_run_differential)

    payload = run_inner_loop(
        db_path=db_path,
        output_root=output_root,
        process_limit=1,
        power_limit=1,
        process_statuses=("GOLDEN_READY",),
        skip_preflight=True,
        enable_evolution=False,
    )

    assert payload["counts"]["processed"] == 1
    assert payload["counts"]["cached_source"] == 1
    assert payload["counts"]["cached_elf"] == 1
    assert payload["counts"]["cached_golden"] == 1
    assert observed == {
        "skip_compile": True,
        "skip_qemu": True,
        "cached_golden_digest": "face",
    }


def test_inner_loop_falls_back_to_artifact_index_when_metadata_paths_are_missing(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "vault.sqlite3"
    output_root = tmp_path / "inner"
    source_path = tmp_path / "artifact-source.c"
    source_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    elf_path = tmp_path / "artifact-seed.elf"
    elf_path.write_text("cached elf", encoding="utf-8")

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="artifact-seed",
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
                ace_score=0.8,
                ibr_score=0.7,
                memory_pressure_score=0.3,
                risk_score=0.8,
                status="GOLDEN_READY",
                qemu_golden_hash="cafe",
                metadata={
                    "source_path": str(source_path),
                    "golden_digest": "cafe",
                    "execution": {
                        "compile": {"status": "ok", "returncode": 0},
                        "qemu": {"status": "ok", "returncode": 0},
                    },
                    "inner_loop": {
                        "elf_path": str(elf_path),
                    },
                },
            )
        )
        vault.update_execution_result(
            "artifact-seed",
            metadata={
                "golden_digest": "cafe",
                "execution": {
                    "compile": {"status": "ok", "returncode": 0},
                    "qemu": {"status": "ok", "returncode": 0},
                },
            },
        )

    observed = {}

    def fake_run_differential(**kwargs):
        observed["source"] = str(kwargs["source"])
        observed["elf"] = str(kwargs["elf"])
        observed["skip_compile"] = kwargs["skip_compile"]
        observed["skip_qemu"] = kwargs["skip_qemu"]
        return DifferentialResult(
            status="matched",
            golden_digest="cafe",
            faulted_digest="cafe",
            compile=CommandResult([], 0, "", ""),
            qemu=CommandResult([], 0, "SDC_DIGEST=cafe", ""),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=cafe", ""),
            mcpat={"power_total": 1.2},
            fault_request={"fault_model": "none", "fault_target": ""},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.inner_loop.run_differential", fake_run_differential)

    payload = run_inner_loop(
        db_path=db_path,
        output_root=output_root,
        process_limit=1,
        power_limit=1,
        process_statuses=("GOLDEN_READY",),
        skip_preflight=True,
        enable_evolution=False,
    )

    assert payload["counts"]["processed"] == 1
    assert payload["counts"]["cached_source"] == 1
    assert payload["counts"]["cached_elf"] == 1
    assert observed["source"] == str(source_path.resolve())
    assert observed["elf"] == str(elf_path.resolve())
    assert observed["skip_compile"] is True
    assert observed["skip_qemu"] is True
