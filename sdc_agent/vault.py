#!/usr/bin/env python3
"""SQLite-backed testcase vault for ARM64 SDC fuzzing."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    if value is None:
        value = {}
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value in (None, ""):
        return {}
    return json.loads(str(value))


def _bool_to_sql(value: Any) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


@dataclass
class VaultEntry:
    testcase_key: str
    asm_content: str
    target_name: str
    policy_name: str = "sdc_fuzzing"
    ace_score: float = 0.0
    ibr_score: float = 0.0
    memory_pressure_score: float = 0.0
    risk_score: float = 0.0
    qemu_golden_hash: Optional[str] = None
    gem5_fault_hash: Optional[str] = None
    mcpat_power: Optional[float] = None
    status: str = "PENDING"
    metadata: Optional[Dict[str, Any]] = None

    def to_record(self) -> Dict[str, Any]:
        record = asdict(self)
        record["metadata_json"] = _json_dumps(record.pop("metadata"))
        return record


class SDCVault:
    """Persistent testcase storage for the offline/online SDC loop.

    The legacy `offline_testcases` table remains the compatibility surface for
    the current control plane. New v2 tables capture the normalized projections
    needed by future inner/outer/hardware loops.
    """

    DEFAULT_SCHEMA_VERSION = 2
    DEFAULT_PROFILE_NAME = "SIM_SAFE"
    OUTER_LOOP_STATUSES = {"MATCHED", "SDC_FOUND", "TIMEOUT", "CRASHED", "INVALID"}

    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    @property
    def path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        self._conn.close()

    def get_schema_version(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM vault_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return 0
        return int(row["value"])

    def _initialize(self) -> None:
        with self._conn:
            self._create_meta_table()
            self._create_legacy_summary_table()
            self._create_v2_tables()
            self._conn.execute(
                """
                INSERT INTO vault_meta(key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(self.DEFAULT_SCHEMA_VERSION),),
            )
            self._backfill_v2_from_legacy_summary()

    def _create_meta_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _create_legacy_summary_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_testcases (
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
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_offline_testcases_status_risk
            ON offline_testcases(status, risk_score DESC, ace_score DESC, ibr_score DESC)
            """
        )

    def _create_v2_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS testcases (
                testcase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL UNIQUE,
                target_name TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                profile_name TEXT NOT NULL DEFAULT 'SIM_SAFE',
                asm_content TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'PENDING',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_testcases_state_profile
            ON testcases(state, profile_name, updated_at DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS static_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL UNIQUE,
                ace_score REAL NOT NULL DEFAULT 0.0,
                ibr_score REAL NOT NULL DEFAULT 0.0,
                memory_pressure_score REAL NOT NULL DEFAULT 0.0,
                static_risk_score REAL NOT NULL DEFAULT 0.0,
                capstone_validated INTEGER,
                preferred_stride_bytes INTEGER,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_static_metrics_risk
            ON static_metrics(static_risk_score DESC, ace_score DESC, ibr_score DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL,
                artifact_kind TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                artifact_hash TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(testcase_key, artifact_kind, artifact_path),
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_testcase_kind
            ON artifacts(testcase_key, artifact_kind, updated_at DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inner_runs (
                inner_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL,
                run_label TEXT NOT NULL DEFAULT 'summary_sync',
                compile_status TEXT,
                qemu_status TEXT,
                qemu_golden_hash TEXT,
                result_status TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_inner_runs_testcase_created
            ON inner_runs(testcase_key, created_at DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS power_annotations (
                power_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL,
                source_kind TEXT NOT NULL DEFAULT 'mcpat',
                power_total REAL,
                power_dynamic REAL,
                power_leakage REAL,
                power_peak_dynamic REAL,
                template_profile TEXT,
                stats_file TEXT,
                config_file TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_power_annotations_testcase_created
            ON power_annotations(testcase_key, created_at DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fault_campaigns (
                campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_key TEXT UNIQUE,
                selector_json TEXT NOT NULL DEFAULT '{}',
                matrix_hash TEXT,
                status TEXT NOT NULL DEFAULT 'PLANNED',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fault_runs (
                fault_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                testcase_key TEXT NOT NULL,
                fault_model TEXT,
                fault_target TEXT,
                fault_bit INTEGER,
                fault_tick INTEGER,
                golden_digest TEXT,
                faulted_digest TEXT,
                result_status TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES fault_campaigns(campaign_id) ON DELETE SET NULL,
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fault_runs_testcase_created
            ON fault_runs(testcase_key, created_at DESC)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hardware_promotions (
                promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                testcase_key TEXT NOT NULL,
                backend_name TEXT NOT NULL DEFAULT 'opendcdiag',
                external_test_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PLANNED',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(testcase_key, backend_name, external_test_name),
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hardware_runs (
                hardware_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                promotion_id INTEGER,
                testcase_key TEXT NOT NULL,
                machine_id TEXT,
                result_status TEXT NOT NULL,
                detectors_json TEXT NOT NULL DEFAULT '{}',
                log_path TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(promotion_id) REFERENCES hardware_promotions(promotion_id) ON DELETE SET NULL,
                FOREIGN KEY(testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lineage_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_testcase_key TEXT NOT NULL,
                parent_testcase_keys_json TEXT NOT NULL DEFAULT '[]',
                generation INTEGER NOT NULL DEFAULT 0,
                driver TEXT NOT NULL DEFAULT '',
                operators_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(child_testcase_key, generation, driver),
                FOREIGN KEY(child_testcase_key) REFERENCES testcases(testcase_key) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_lineage_child_generation
            ON lineage_events(child_testcase_key, generation DESC)
            """
        )

    def _profile_name_from_metadata(self, metadata: Mapping[str, Any]) -> str:
        for key in ("profile_name", "generation_profile", "execution_profile"):
            value = metadata.get(key)
            if value:
                return str(value)
        lineage = _mapping(metadata.get("lineage"))
        if lineage.get("profile_name"):
            return str(lineage["profile_name"])
        return self.DEFAULT_PROFILE_NAME

    def _artifact_rows_from_metadata(
        self, metadata: Mapping[str, Any]
    ) -> List[tuple[str, str, Dict[str, Any]]]:
        rows: Dict[tuple[str, str], Dict[str, Any]] = {}

        def add(kind: str, path_value: Any, payload: Optional[Mapping[str, Any]] = None) -> None:
            if not path_value:
                return
            key = (kind, str(path_value))
            rows[key] = dict(payload or {})

        add(
            "rendered",
            metadata.get("rendered_path"),
            {"rendered_format": metadata.get("rendered_format")},
        )
        add("source", metadata.get("source_path"))

        materialized = _mapping(metadata.get("materialized"))
        add("materialized_source", materialized.get("source_path"), materialized)
        add("materialized_output_root", materialized.get("output_root"), materialized)

        campaign = _mapping(metadata.get("campaign"))
        add("campaign_artifact_dir", campaign.get("artifact_dir"), campaign)
        add("campaign_result_json", campaign.get("result_json"), campaign)

        return [(kind, path_value, payload) for (kind, path_value), payload in rows.items()]

    def _upsert_testcase_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        self._conn.execute(
            """
            INSERT INTO testcases (
                testcase_key,
                target_name,
                policy_name,
                profile_name,
                asm_content,
                state,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (
                :testcase_key,
                :target_name,
                :policy_name,
                :profile_name,
                :asm_content,
                :state,
                :metadata_json,
                :created_at,
                :updated_at
            )
            ON CONFLICT(testcase_key) DO UPDATE SET
                target_name = excluded.target_name,
                policy_name = excluded.policy_name,
                profile_name = excluded.profile_name,
                asm_content = excluded.asm_content,
                state = excluded.state,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            {
                "testcase_key": row["testcase_key"],
                "target_name": row["target_name"],
                "policy_name": row["policy_name"],
                "profile_name": self._profile_name_from_metadata(metadata),
                "asm_content": row["asm_content"],
                "state": row["status"],
                "metadata_json": row["metadata_json"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    def _upsert_static_metrics_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        metrics_payload = {
            "capstone_validated": metadata.get("capstone_validated"),
            "preferred_stride_bytes": metadata.get("preferred_stride_bytes"),
        }
        self._conn.execute(
            """
            INSERT INTO static_metrics (
                testcase_key,
                ace_score,
                ibr_score,
                memory_pressure_score,
                static_risk_score,
                capstone_validated,
                preferred_stride_bytes,
                metrics_json,
                created_at,
                updated_at
            ) VALUES (
                :testcase_key,
                :ace_score,
                :ibr_score,
                :memory_pressure_score,
                :static_risk_score,
                :capstone_validated,
                :preferred_stride_bytes,
                :metrics_json,
                :created_at,
                :updated_at
            )
            ON CONFLICT(testcase_key) DO UPDATE SET
                ace_score = excluded.ace_score,
                ibr_score = excluded.ibr_score,
                memory_pressure_score = excluded.memory_pressure_score,
                static_risk_score = excluded.static_risk_score,
                capstone_validated = excluded.capstone_validated,
                preferred_stride_bytes = excluded.preferred_stride_bytes,
                metrics_json = excluded.metrics_json,
                updated_at = excluded.updated_at
            """,
            {
                "testcase_key": row["testcase_key"],
                "ace_score": row["ace_score"],
                "ibr_score": row["ibr_score"],
                "memory_pressure_score": row["memory_pressure_score"],
                "static_risk_score": row["risk_score"],
                "capstone_validated": _bool_to_sql(metrics_payload["capstone_validated"]),
                "preferred_stride_bytes": _optional_int(
                    metrics_payload["preferred_stride_bytes"]
                ),
                "metrics_json": _json_dumps(metrics_payload),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    def _sync_artifacts_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        for artifact_kind, artifact_path, payload in self._artifact_rows_from_metadata(metadata):
            self._conn.execute(
                """
                INSERT INTO artifacts (
                    testcase_key,
                    artifact_kind,
                    artifact_path,
                    artifact_hash,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(testcase_key, artifact_kind, artifact_path) DO UPDATE SET
                    artifact_hash = excluded.artifact_hash,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    row["testcase_key"],
                    artifact_kind,
                    artifact_path,
                    None,
                    _json_dumps(payload),
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _sync_lineage_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        lineage = _mapping(metadata.get("lineage"))
        if not lineage:
            return

        driver = str(lineage.get("driver", ""))
        generation = int(lineage.get("generation", 0) or 0)
        parents = list(lineage.get("parents", []))
        operators = list(lineage.get("operators", []))

        self._conn.execute(
            """
            INSERT INTO lineage_events (
                child_testcase_key,
                parent_testcase_keys_json,
                generation,
                driver,
                operators_json,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(child_testcase_key, generation, driver) DO UPDATE SET
                parent_testcase_keys_json = excluded.parent_testcase_keys_json,
                operators_json = excluded.operators_json,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                row["testcase_key"],
                _json_dumps(parents),
                generation,
                driver,
                _json_dumps(operators),
                _json_dumps(lineage),
                row["created_at"],
                row["updated_at"],
            ),
        )

    def _record_inner_run_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        execution = _mapping(metadata.get("execution"))
        compile_meta = _mapping(execution.get("compile"))
        qemu_meta = _mapping(execution.get("qemu"))

        has_inner_signal = bool(
            row.get("qemu_golden_hash")
            or qemu_meta
            or compile_meta
            or metadata.get("golden_digest")
        )
        if not has_inner_signal:
            return

        self._conn.execute(
            """
            INSERT INTO inner_runs (
                testcase_key,
                run_label,
                compile_status,
                qemu_status,
                qemu_golden_hash,
                result_status,
                metadata_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["testcase_key"],
                "summary_sync",
                compile_meta.get("status"),
                qemu_meta.get("status"),
                row.get("qemu_golden_hash"),
                row.get("status"),
                _json_dumps(
                    {
                        "execution": execution,
                        "golden_digest": metadata.get("golden_digest"),
                    }
                ),
                row["updated_at"],
            ),
        )

    def _record_power_annotation_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        mcpat = _mapping(metadata.get("mcpat"))
        power_total = (
            float(row["mcpat_power"])
            if row.get("mcpat_power") is not None
            else mcpat.get("power_total")
        )
        if power_total is None:
            return

        self._conn.execute(
            """
            INSERT INTO power_annotations (
                testcase_key,
                source_kind,
                power_total,
                power_dynamic,
                power_leakage,
                power_peak_dynamic,
                template_profile,
                stats_file,
                config_file,
                metadata_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["testcase_key"],
                "mcpat",
                float(power_total),
                mcpat.get("power_dynamic"),
                mcpat.get("power_leakage"),
                mcpat.get("power_peak_dynamic"),
                mcpat.get("template_profile"),
                mcpat.get("stats_file"),
                mcpat.get("config_file"),
                _json_dumps(mcpat),
                row["updated_at"],
            ),
        )

    def _record_fault_run_projection(self, row: Mapping[str, Any]) -> None:
        metadata = _json_loads(row.get("metadata_json"))
        fault_request = _mapping(metadata.get("fault_request"))
        scheduler = _mapping(metadata.get("scheduler"))
        has_fault_signal = bool(
            row.get("gem5_fault_hash")
            or fault_request
            or row.get("status") in self.OUTER_LOOP_STATUSES
            or scheduler.get("source_status")
        )
        if not has_fault_signal:
            return

        self._conn.execute(
            """
            INSERT INTO fault_runs (
                campaign_id,
                testcase_key,
                fault_model,
                fault_target,
                fault_bit,
                fault_tick,
                golden_digest,
                faulted_digest,
                result_status,
                metadata_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                None,
                row["testcase_key"],
                fault_request.get("fault_model"),
                fault_request.get("fault_target"),
                _optional_int(fault_request.get("fault_bit")),
                _optional_int(fault_request.get("fault_tick")),
                row.get("qemu_golden_hash") or metadata.get("golden_digest"),
                row.get("gem5_fault_hash") or metadata.get("faulted_digest"),
                row.get("status"),
                _json_dumps(
                    {
                        "fault_request": fault_request,
                        "scheduler": scheduler,
                    }
                ),
                row["updated_at"],
            ),
        )

    def _sync_v2_from_summary_row(
        self, row: Mapping[str, Any], *, record_history: bool
    ) -> None:
        payload = dict(row)
        self._upsert_testcase_projection(payload)
        self._upsert_static_metrics_projection(payload)
        self._sync_artifacts_projection(payload)
        self._sync_lineage_projection(payload)
        if record_history:
            self._record_inner_run_projection(payload)
            self._record_power_annotation_projection(payload)
            self._record_fault_run_projection(payload)

    def _backfill_v2_from_legacy_summary(self) -> None:
        rows = self._conn.execute(
            """
            SELECT *
            FROM offline_testcases
            ORDER BY test_id ASC
            """
        ).fetchall()
        for row in rows:
            self._sync_v2_from_summary_row(row, record_history=False)

    def upsert_testcase(self, entry: VaultEntry) -> int:
        now = _utcnow()
        record = entry.to_record()
        with self._conn:
            self._conn.execute(
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
                    qemu_golden_hash,
                    gem5_fault_hash,
                    mcpat_power,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :testcase_key,
                    :target_name,
                    :policy_name,
                    :asm_content,
                    :ace_score,
                    :ibr_score,
                    :memory_pressure_score,
                    :risk_score,
                    :qemu_golden_hash,
                    :gem5_fault_hash,
                    :mcpat_power,
                    :status,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(testcase_key) DO UPDATE SET
                    target_name = excluded.target_name,
                    policy_name = excluded.policy_name,
                    asm_content = excluded.asm_content,
                    ace_score = excluded.ace_score,
                    ibr_score = excluded.ibr_score,
                    memory_pressure_score = excluded.memory_pressure_score,
                    risk_score = excluded.risk_score,
                    qemu_golden_hash = COALESCE(excluded.qemu_golden_hash, offline_testcases.qemu_golden_hash),
                    gem5_fault_hash = COALESCE(excluded.gem5_fault_hash, offline_testcases.gem5_fault_hash),
                    mcpat_power = COALESCE(excluded.mcpat_power, offline_testcases.mcpat_power),
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    **record,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            row = self._conn.execute(
                "SELECT * FROM offline_testcases WHERE testcase_key = ?",
                (entry.testcase_key,),
            ).fetchone()
            assert row is not None
            self._sync_v2_from_summary_row(row, record_history=False)
        assert row is not None
        return int(row["test_id"])

    def update_execution_result(
        self,
        testcase_key: str,
        *,
        qemu_golden_hash: Optional[str] = None,
        gem5_fault_hash: Optional[str] = None,
        mcpat_power: Optional[float] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        assignments: List[str] = ["updated_at = :updated_at"]
        params: Dict[str, Any] = {"testcase_key": testcase_key, "updated_at": _utcnow()}

        if qemu_golden_hash is not None:
            assignments.append("qemu_golden_hash = :qemu_golden_hash")
            params["qemu_golden_hash"] = qemu_golden_hash
        if gem5_fault_hash is not None:
            assignments.append("gem5_fault_hash = :gem5_fault_hash")
            params["gem5_fault_hash"] = gem5_fault_hash
        if mcpat_power is not None:
            assignments.append("mcpat_power = :mcpat_power")
            params["mcpat_power"] = mcpat_power
        if status is not None:
            assignments.append("status = :status")
            params["status"] = status
        if metadata is not None:
            assignments.append("metadata_json = :metadata_json")
            params["metadata_json"] = _json_dumps(metadata)

        with self._conn:
            self._conn.execute(
                f"""
                UPDATE offline_testcases
                SET {", ".join(assignments)}
                WHERE testcase_key = :testcase_key
                """,
                params,
            )
            updated = self.get_testcase(testcase_key)
            if updated is not None:
                self._sync_v2_from_summary_row(
                    updated,
                    record_history=any(
                        value is not None
                        for value in (
                            qemu_golden_hash,
                            gem5_fault_hash,
                            mcpat_power,
                            status,
                        )
                    ),
                )

    def mark_status(self, testcase_key: str, status: str) -> None:
        self.update_execution_result(testcase_key, status=status)

    def fetch_top_k_risky(
        self,
        limit: int,
        statuses: Sequence[str] = ("PENDING",),
    ) -> List[sqlite3.Row]:
        placeholders = ", ".join("?" for _ in statuses)
        query = f"""
            SELECT *
            FROM offline_testcases
            WHERE status IN ({placeholders})
            ORDER BY
                risk_score DESC,
                (ace_score * 0.6 + ibr_score * 0.4) DESC,
                memory_pressure_score DESC,
                test_id ASC
            LIMIT ?
        """
        cursor = self._conn.execute(query, [*statuses, limit])
        return cursor.fetchall()

    def list_testcases(
        self,
        *,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        if status is None:
            cursor = self._conn.execute(
                """
                SELECT *
                FROM offline_testcases
                ORDER BY test_id DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT *
                FROM offline_testcases
                WHERE status = ?
                ORDER BY test_id DESC
                LIMIT ?
                """,
                (status, limit),
            )
        return cursor.fetchall()

    def get_testcase(self, testcase_key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM offline_testcases WHERE testcase_key = ?",
            (testcase_key,),
        ).fetchone()

    def get_testcase_projection(self, testcase_key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM testcases WHERE testcase_key = ?",
            (testcase_key,),
        ).fetchone()

    def get_static_metrics(self, testcase_key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM static_metrics WHERE testcase_key = ?",
            (testcase_key,),
        ).fetchone()

    def list_artifacts(self, testcase_key: str, *, limit: int = 50) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM artifacts
            WHERE testcase_key = ?
            ORDER BY updated_at DESC, artifact_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def list_inner_runs(self, testcase_key: str, *, limit: int = 50) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM inner_runs
            WHERE testcase_key = ?
            ORDER BY created_at DESC, inner_run_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def list_power_annotations(
        self, testcase_key: str, *, limit: int = 50
    ) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM power_annotations
            WHERE testcase_key = ?
            ORDER BY created_at DESC, power_run_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def list_fault_runs(self, testcase_key: str, *, limit: int = 50) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM fault_runs
            WHERE testcase_key = ?
            ORDER BY created_at DESC, fault_run_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def list_lineage_events(
        self, testcase_key: str, *, limit: int = 50
    ) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM lineage_events
            WHERE child_testcase_key = ?
            ORDER BY generation DESC, updated_at DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def upsert_fault_campaign(
        self,
        campaign_key: str,
        *,
        selector: Optional[Mapping[str, Any]] = None,
        matrix_hash: Optional[str] = None,
        status: str = "PLANNED",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> int:
        now = _utcnow()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO fault_campaigns (
                    campaign_key,
                    selector_json,
                    matrix_hash,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_key) DO UPDATE SET
                    selector_json = excluded.selector_json,
                    matrix_hash = excluded.matrix_hash,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    campaign_key,
                    _json_dumps(selector),
                    matrix_hash,
                    status,
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )
            row = self._conn.execute(
                "SELECT campaign_id FROM fault_campaigns WHERE campaign_key = ?",
                (campaign_key,),
            ).fetchone()
        assert row is not None
        return int(row["campaign_id"])

    def list_fault_campaigns(
        self, *, limit: int = 50, status: Optional[str] = None
    ) -> List[sqlite3.Row]:
        if status is None:
            return self._conn.execute(
                """
                SELECT *
                FROM fault_campaigns
                ORDER BY updated_at DESC, campaign_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return self._conn.execute(
            """
            SELECT *
            FROM fault_campaigns
            WHERE status = ?
            ORDER BY updated_at DESC, campaign_id DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()

    def upsert_hardware_promotion(
        self,
        testcase_key: str,
        *,
        backend_name: str = "opendcdiag",
        external_test_name: str,
        status: str = "PLANNED",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> int:
        now = _utcnow()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO hardware_promotions (
                    testcase_key,
                    backend_name,
                    external_test_name,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(testcase_key, backend_name, external_test_name) DO UPDATE SET
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    testcase_key,
                    backend_name,
                    external_test_name,
                    status,
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )
            row = self._conn.execute(
                """
                SELECT promotion_id
                FROM hardware_promotions
                WHERE testcase_key = ? AND backend_name = ? AND external_test_name = ?
                """,
                (testcase_key, backend_name, external_test_name),
            ).fetchone()
        assert row is not None
        return int(row["promotion_id"])

    def record_hardware_run(
        self,
        testcase_key: str,
        *,
        promotion_id: Optional[int] = None,
        machine_id: Optional[str] = None,
        result_status: str,
        detectors: Optional[Mapping[str, Any]] = None,
        log_path: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> int:
        now = _utcnow()
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO hardware_runs (
                    promotion_id,
                    testcase_key,
                    machine_id,
                    result_status,
                    detectors_json,
                    log_path,
                    metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    promotion_id,
                    testcase_key,
                    machine_id,
                    result_status,
                    _json_dumps(detectors),
                    log_path,
                    _json_dumps(metadata),
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def list_hardware_promotions(
        self, testcase_key: str, *, limit: int = 50
    ) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM hardware_promotions
            WHERE testcase_key = ?
            ORDER BY updated_at DESC, promotion_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def list_hardware_runs(
        self, testcase_key: str, *, limit: int = 50
    ) -> List[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM hardware_runs
            WHERE testcase_key = ?
            ORDER BY created_at DESC, hardware_run_id DESC
            LIMIT ?
            """,
            (testcase_key, limit),
        ).fetchall()

    def count(self, *, status: Optional[str] = None) -> int:
        if status is None:
            row = self._conn.execute(
                "SELECT COUNT(*) AS count FROM offline_testcases"
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS count FROM offline_testcases WHERE status = ?",
                (status,),
            ).fetchone()
        assert row is not None
        return int(row["count"])

    def __enter__(self) -> "SDCVault":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
