import json

from sdc_agent.hardware_lane import run_hardware_promotion
from sdc_agent.vault import SDCVault, VaultEntry


def test_hardware_promotion_dry_run_plans_without_persisting(tmp_path):
    db_path = tmp_path / "vault.sqlite3"

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-promote",
                asm_content="mov x0, x0",
                target_name="arm64",
                ace_score=0.8,
                ibr_score=0.8,
                memory_pressure_score=0.4,
                risk_score=0.7,
                status="SDC_FOUND",
                metadata={
                    "outer_loop": {
                        "outer_value_score": 0.2,
                        "injector_confidence_score": 1.0,
                        "promotion_readiness_score": 0.2,
                        "promotion_ready": True,
                        "execution_planes": {"gem5_scripted": 1},
                    }
                },
            )
        )

    payload = run_hardware_promotion(
        db_path=db_path,
        output_root=tmp_path / "hardware",
        limit=2,
        dry_run=True,
    )

    assert payload["counts"] == {"selected": 1, "planned": 1, "emitted": 0}
    assert payload["promotions"][0]["testcase_key"] == "seed-promote"
    assert payload["promotions"][0]["status"] == "PLANNED"

    with SDCVault(db_path) as vault:
        assert len(vault.list_hardware_promotions("seed-promote")) == 0


def test_hardware_promotion_emits_bundle_and_records_vault(tmp_path):
    db_path = tmp_path / "vault.sqlite3"

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-hw",
                asm_content="mov x0, x0\nadd x1, x1, x0",
                target_name="arm64",
                ace_score=0.85,
                ibr_score=0.8,
                memory_pressure_score=0.5,
                risk_score=0.75,
                status="SDC_FOUND",
                metadata={
                    "profile_name": "HW_AGGRESSIVE",
                    "preferred_stride_bytes": 8192,
                    "outer_loop": {
                        "outer_value_score": 0.25,
                        "injector_confidence_score": 1.0,
                        "promotion_readiness_score": 0.25,
                        "promotion_ready": True,
                        "execution_planes": {"gem5_scripted": 2},
                    },
                },
            )
        )

    payload = run_hardware_promotion(
        db_path=db_path,
        output_root=tmp_path / "hardware",
        limit=2,
        dry_run=False,
    )

    assert payload["counts"] == {"selected": 1, "planned": 0, "emitted": 1}
    promotion = payload["promotions"][0]
    assert promotion["testcase_key"] == "seed-hw"
    assert promotion["status"] == "EMITTED"
    assert promotion["promotion_id"] is not None

    manifest_path = tmp_path / "hardware" / "seed-hw" / promotion["external_test_name"] / "promotion.json"
    test_source_path = tmp_path / "hardware" / "seed-hw" / promotion["external_test_name"] / f"{promotion['external_test_name']}.cpp"
    asm_path = tmp_path / "hardware" / "seed-hw" / promotion["external_test_name"] / f"{promotion['external_test_name']}.s"
    meson_fragment_path = tmp_path / "hardware" / "seed-hw" / promotion["external_test_name"] / "meson.build.fragment"

    assert manifest_path.exists()
    assert test_source_path.exists()
    assert asm_path.exists()
    assert meson_fragment_path.exists()

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["testcase_key"] == "seed-hw"
    assert manifest_payload["backend_name"] == "opendcdiag"
    assert manifest_payload["promotion_components"]["promotion_score"] > 0.0

    with SDCVault(db_path) as vault:
        promotions = vault.list_hardware_promotions("seed-hw")
        assert len(promotions) == 1
        row = promotions[0]
        assert row["status"] == "EMITTED"

        testcase = vault.get_testcase("seed-hw")
        assert testcase is not None
        metadata = json.loads(testcase["metadata_json"])
        assert metadata["hardware_lane"]["external_test_name"] == promotion["external_test_name"]
        assert metadata["hardware_lane"]["promotion_score"] > 0.0

        artifact_kinds = {item["artifact_kind"] for item in vault.list_artifacts("seed-hw")}
        assert artifact_kinds >= {
            "hardware_bundle_dir",
            "hardware_manifest",
            "hardware_test_source",
            "hardware_asm",
            "hardware_meson_fragment",
        }
