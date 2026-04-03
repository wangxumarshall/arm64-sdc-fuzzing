import sqlite3

from sdc_agent.vault import SDCVault, VaultEntry


def test_vault_v2_upsert_populates_normalized_projections(tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    rendered_path = tmp_path / "seed-1.s"
    source_path = tmp_path / "seed-1.c"

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-1",
                asm_content="mov x0, x0",
                target_name="arm64",
                ace_score=0.8,
                ibr_score=0.6,
                memory_pressure_score=0.4,
                risk_score=0.7,
                metadata={
                    "profile_name": "HW_AGGRESSIVE",
                    "capstone_validated": True,
                    "preferred_stride_bytes": 16384,
                    "rendered_path": str(rendered_path),
                    "rendered_format": "s",
                    "source_path": str(source_path),
                    "lineage": {
                        "generation": 2,
                        "parents": ["parent-a", "parent-b"],
                        "driver": "SDCFuzzingGeneticDriver",
                        "operators": ["one_point_crossover"],
                    },
                },
            )
        )

        assert vault.get_schema_version() == 2

        projection = vault.get_testcase_projection("seed-1")
        assert projection is not None
        assert projection["profile_name"] == "HW_AGGRESSIVE"
        assert projection["state"] == "PENDING"

        metrics = vault.get_static_metrics("seed-1")
        assert metrics is not None
        assert metrics["static_risk_score"] == 0.7
        assert metrics["capstone_validated"] == 1
        assert metrics["preferred_stride_bytes"] == 16384

        artifacts = vault.list_artifacts("seed-1")
        assert {row["artifact_kind"] for row in artifacts} >= {"rendered", "source"}

        lineage = vault.list_lineage_events("seed-1")
        assert len(lineage) == 1
        assert lineage[0]["generation"] == 2


def test_vault_v2_records_execution_history_without_metadata_duplicates(tmp_path):
    db_path = tmp_path / "vault.sqlite3"

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-2",
                asm_content="mov x1, x1",
                target_name="arm64",
                risk_score=0.5,
            )
        )

        vault.update_execution_result(
            "seed-2",
            qemu_golden_hash="aaaa",
            gem5_fault_hash="bbbb",
            mcpat_power=1.25,
            status="SDC_FOUND",
            metadata={
                "golden_digest": "aaaa",
                "faulted_digest": "bbbb",
                "fault_request": {
                    "fault_model": "register_bit_flip",
                    "fault_target": "x0",
                    "fault_bit": 7,
                    "fault_tick": 1234,
                },
                "execution": {
                    "compile": {"status": "ok", "returncode": 0},
                    "qemu": {"status": "ok", "returncode": 0},
                    "gem5": {"status": "ok", "returncode": 0},
                },
                "mcpat": {
                    "power_total": 1.25,
                    "power_dynamic": 0.8,
                    "power_leakage": 0.2,
                    "template_profile": "arm64-kunpeng920",
                },
                "scheduler": {
                    "normalized_status": "SDC_FOUND",
                    "source_status": "sdc_found",
                },
            },
        )

        assert len(vault.list_inner_runs("seed-2")) == 1
        assert len(vault.list_power_annotations("seed-2")) == 1
        assert len(vault.list_fault_runs("seed-2")) == 1

        fault_run = vault.list_fault_runs("seed-2")[0]
        assert fault_run["fault_model"] == "register_bit_flip"
        assert fault_run["fault_target"] == "x0"
        assert fault_run["fault_bit"] == 7
        assert fault_run["fault_tick"] == 1234

        vault.update_execution_result(
            "seed-2",
            metadata={
                "source_path": str(tmp_path / "seed-2.c"),
                "campaign": {
                    "artifact_dir": str(tmp_path / "campaign" / "seed-2"),
                    "result_json": str(tmp_path / "campaign" / "seed-2" / "result.json"),
                },
            },
        )

        assert len(vault.list_inner_runs("seed-2")) == 1
        assert len(vault.list_power_annotations("seed-2")) == 1
        assert len(vault.list_fault_runs("seed-2")) == 1

        artifact_kinds = {row["artifact_kind"] for row in vault.list_artifacts("seed-2")}
        assert artifact_kinds >= {"source", "campaign_artifact_dir", "campaign_result_json"}


def test_vault_v2_backfills_from_legacy_summary_table(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE vault_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO vault_meta(key, value) VALUES ('schema_version', '1')
            """
        )
        conn.execute(
            """
            CREATE TABLE offline_testcases (
                test_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL UNIQUE,
                target_name TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                asm_content TEXT NOT NULL,
                ace_score REAL NOT NULL DEFAULT 0.0,
                ibr_score REAL NOT NULL DEFAULT 0.0,
                memory_pressure_score REAL NOT NULL DEFAULT 0.0,
                risk_score REAL NOT NULL DEFAULT 0.0,
                qemu_golden_hash TEXT,
                gem5_fault_hash TEXT,
                mcpat_power REAL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO offline_testcases (
                testcase_key,
                target_name,
                policy_name,
                asm_content,
                ace_score,
                ibr_score,
                memory_pressure_score,
                risk_score,
                status,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-seed",
                "arm64",
                "sdc_fuzzing",
                "mov x2, x2",
                0.9,
                0.7,
                0.4,
                0.8,
                "PENDING",
                '{"profile_name":"SIM_SAFE","capstone_validated":true}',
                "2026-04-02T00:00:00+00:00",
                "2026-04-02T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with SDCVault(db_path) as vault:
        assert vault.get_schema_version() == 2
        projection = vault.get_testcase_projection("legacy-seed")
        metrics = vault.get_static_metrics("legacy-seed")

        assert projection is not None
        assert projection["profile_name"] == "SIM_SAFE"
        assert metrics is not None
        assert metrics["static_risk_score"] == 0.8
        assert metrics["capstone_validated"] == 1


def test_vault_v2_supports_fault_campaign_and_hardware_records(tmp_path):
    db_path = tmp_path / "vault.sqlite3"

    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-3",
                asm_content="mov x3, x3",
                target_name="arm64",
                risk_score=0.4,
            )
        )

        campaign_id = vault.upsert_fault_campaign(
            "campaign-1",
            selector={"status": "INNER_READY"},
            matrix_hash="abc123",
            status="RUNNING",
            metadata={"planner": "fault_matrix_v1"},
        )
        assert campaign_id > 0
        assert vault.list_fault_campaigns(limit=1)[0]["campaign_key"] == "campaign-1"

        promotion_id = vault.upsert_hardware_promotion(
            "seed-3",
            external_test_name="arm64_sdc_seed_3",
            status="PROMOTED",
            metadata={"backend": "opendcdiag"},
        )
        assert promotion_id > 0

        hardware_run_id = vault.record_hardware_run(
            "seed-3",
            promotion_id=promotion_id,
            machine_id="kunpeng920-node-a",
            result_status="PASS",
            detectors={"crc32": "pass", "checksum": "pass"},
            log_path=str(tmp_path / "hw.log"),
            metadata={"attempt": 1},
        )
        assert hardware_run_id > 0
        assert len(vault.list_hardware_promotions("seed-3")) == 1
        assert len(vault.list_hardware_runs("seed-3")) == 1
