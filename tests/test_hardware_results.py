import json
from pathlib import Path

from sdc_agent.hardware_results import execute_hardware_promotions, ingest_hardware_result
from sdc_agent.vault import SDCVault, VaultEntry


def test_ingest_hardware_result_records_run_and_updates_promotion(tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-a",
                asm_content="mov x0, x0",
                target_name="arm64",
            )
        )
        promotion_id = vault.upsert_hardware_promotion(
            "seed-a",
            external_test_name="arm64_sdc_seed_a",
            status="EMITTED",
            metadata={"bundle_dir": str(tmp_path / "bundle")},
        )

    result_json = tmp_path / "result.json"
    result_json.write_text(
        json.dumps(
            {
                "backend_name": "opendcdiag",
                "testcase_key": "seed-a",
                "external_test_name": "arm64_sdc_seed_a",
                "result_status": "PASS",
                "detectors": {"digest_match": "pass"},
                "machine_id": "kunpeng920-a",
                "machine_metadata": {"machine": "aarch64", "cpu_count": 64},
                "log_path": str(tmp_path / "sandstone.stdout"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = ingest_hardware_result(
        db_path=db_path,
        result_json=result_json,
    )

    assert payload["promotion_id"] == promotion_id
    assert payload["result_status"] == "PASS"
    assert payload["machine_metadata"]["machine"] == "aarch64"

    with SDCVault(db_path) as vault:
        runs = vault.list_hardware_runs("seed-a")
        assert len(runs) == 1
        assert runs[0]["result_status"] == "PASS"
        promotions = vault.list_hardware_promotions("seed-a")
        assert promotions[0]["status"] == "PASS"


def test_execute_hardware_promotions_runs_backend_and_auto_ingests(monkeypatch, tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "promotion.json").write_text(
        json.dumps(
            {
                "backend_name": "opendcdiag",
                "testcase_key": "seed-b",
                "external_test_name": "arm64_sdc_seed_b",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "arm64_sdc_seed_b.cpp").write_text("int x = 1;\n", encoding="utf-8")

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-b",
                asm_content="mov x0, x0",
                target_name="arm64",
            )
        )
        vault.upsert_hardware_promotion(
            "seed-b",
            external_test_name="arm64_sdc_seed_b",
            status="EMITTED",
            metadata={"bundle_dir": str(bundle_dir)},
        )

    class FakeBackend:
        def run(self, target_dir):
            target_dir = Path(target_dir)
            runtime_dir = target_dir / "opendcdiag-run"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            result_json = runtime_dir / "result.json"
            payload = {
                "backend": "opendcdiag",
                "backend_name": "opendcdiag",
                "testcase_key": "seed-b",
                "external_test_name": "arm64_sdc_seed_b",
                "result_status": "PASS",
                "detectors": {"digest_match": "pass"},
                "machine_id": "local-opendcdiag",
                "machine_metadata": {"machine": "aarch64", "cpu_count": 64},
                "log_path": str(runtime_dir / "sandstone.stdout"),
                "result_json": str(result_json),
            }
            result_json.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            return payload

    monkeypatch.setattr("sdc_agent.hardware_results.OpenDCDiagBackend", FakeBackend)

    payload = execute_hardware_promotions(
        db_path=db_path,
        limit=4,
        backend_name="opendcdiag",
        machine_id="kunpeng920-b",
        runtime_root=tmp_path / "runtime",
        auto_ingest=True,
    )

    assert payload["count"] == 1
    executed = payload["executed"][0]
    assert executed["result_status"] == "PASS"

    with SDCVault(db_path) as vault:
        runs = vault.list_hardware_runs("seed-b")
        assert len(runs) == 1
        assert runs[0]["machine_id"] == "kunpeng920-b"
