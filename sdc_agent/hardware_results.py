#!/usr/bin/env python3
"""Hardware result ingestion and execution helpers."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .power_backends.opendcdiag_backend import OpenDCDiagBackend
from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = REPO_ROOT / "artifacts" / "hardware-runtime"


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
    if isinstance(raw, dict):
        return dict(raw)
    if raw in (None, ""):
        return {}
    return json.loads(str(raw))


def ingest_hardware_result(
    *,
    db_path: Path,
    result_json: Path,
    machine_id: Optional[str] = None,
) -> Dict[str, Any]:
    result_json = result_json.resolve()
    payload = _load_json(result_json)
    testcase_key = str(payload["testcase_key"])
    backend_name = str(payload.get("backend_name", payload.get("backend", "opendcdiag")))
    external_test_name = str(payload["external_test_name"])
    result_status = str(payload["result_status"])
    detectors = dict(payload.get("detectors") or {})
    effective_machine_id = machine_id or str(payload.get("machine_id") or "unknown-machine")
    machine_metadata = dict(payload.get("machine_metadata") or {})
    log_path = str(payload.get("log_path") or result_json)

    with SDCVault(db_path) as vault:
        promotion = vault.get_hardware_promotion(
            testcase_key,
            backend_name=backend_name,
            external_test_name=external_test_name,
        )
        if promotion is None:
            raise KeyError(
                f"Unknown promotion for testcase={testcase_key}, backend={backend_name}, test={external_test_name}"
            )

        promotion_id = int(promotion["promotion_id"])
        hardware_run_id = vault.record_hardware_run(
            testcase_key,
            promotion_id=promotion_id,
            machine_id=effective_machine_id,
            result_status=result_status,
            detectors=detectors,
            log_path=log_path,
            metadata={
                "result_json": str(result_json),
                "backend_payload": payload,
                "machine_metadata": machine_metadata,
            },
        )

        previous_metadata = _decode_metadata(promotion)
        merged_metadata = {
            **previous_metadata,
            "latest_result_json": str(result_json),
            "latest_result_status": result_status,
            "latest_machine_id": effective_machine_id,
            "latest_hardware_run_id": hardware_run_id,
            "latest_machine_metadata": machine_metadata,
        }
        vault.upsert_hardware_promotion(
            testcase_key,
            backend_name=backend_name,
            external_test_name=external_test_name,
            status=result_status,
            metadata=merged_metadata,
        )

        testcase = vault.get_testcase(testcase_key)
        if testcase is not None:
            metadata = _decode_metadata(testcase)
            metadata["hardware_lane"] = {
                **dict(metadata.get("hardware_lane") or {}),
                "latest_result_json": str(result_json),
                "latest_result_status": result_status,
                "latest_machine_id": effective_machine_id,
                "latest_hardware_run_id": hardware_run_id,
                "latest_machine_metadata": machine_metadata,
            }
            vault.update_execution_result(testcase_key, metadata=metadata)

    return {
        "ok": True,
        "testcase_key": testcase_key,
        "promotion_id": promotion_id,
        "hardware_run_id": hardware_run_id,
        "result_status": result_status,
        "machine_id": effective_machine_id,
        "machine_metadata": machine_metadata,
        "result_json": str(result_json),
    }


def execute_hardware_promotions(
    *,
    db_path: Path,
    limit: int = 4,
    backend_name: str = "opendcdiag",
    machine_id: str = "local-opendcdiag",
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    auto_ingest: bool = True,
) -> Dict[str, Any]:
    runtime_root = runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    backend = OpenDCDiagBackend()
    executed: List[Dict[str, Any]] = []

    with SDCVault(db_path) as vault:
        promotions = vault.list_all_hardware_promotions(
            limit=limit,
            backend_name=backend_name,
        )

    for promotion in promotions:
        metadata = _decode_metadata(promotion)
        bundle_dir = metadata.get("bundle_dir")
        if not bundle_dir:
            continue
        source_bundle_dir = Path(str(bundle_dir)).resolve()
        execution_dir = (
            runtime_root
            / str(promotion["testcase_key"])
            / str(promotion["external_test_name"])
        ).resolve()
        if execution_dir.exists():
            shutil.rmtree(execution_dir)
        shutil.copytree(source_bundle_dir, execution_dir)

        result = backend.run(execution_dir)
        result["machine_id"] = machine_id
        result["backend_name"] = backend_name
        result_json = Path(str(result["result_json"]))
        result_json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        record = {
            "testcase_key": str(promotion["testcase_key"]),
            "promotion_id": int(promotion["promotion_id"]),
            "external_test_name": str(promotion["external_test_name"]),
            "result_json": str(result_json),
            "result_status": str(result["result_status"]),
        }
        if auto_ingest:
            record["ingest"] = ingest_hardware_result(
                db_path=db_path,
                result_json=result_json,
                machine_id=machine_id,
            )
        executed.append(record)

    return {
        "ok": True,
        "backend_name": backend_name,
        "machine_id": machine_id,
        "count": len(executed),
        "executed": executed,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest or execute hardware-lane results."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--db", type=Path, required=True)
    ingest.add_argument("--result-json", type=Path, required=True)
    ingest.add_argument("--machine-id", default=None)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--db", type=Path, required=True)
    execute.add_argument("--limit", type=int, default=4)
    execute.add_argument("--backend-name", default="opendcdiag")
    execute.add_argument("--machine-id", default="local-opendcdiag")
    execute.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    execute.add_argument("--no-auto-ingest", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.command == "ingest":
        payload = ingest_hardware_result(
            db_path=args.db,
            result_json=args.result_json,
            machine_id=args.machine_id,
        )
    else:
        payload = execute_hardware_promotions(
            db_path=args.db,
            limit=args.limit,
            backend_name=args.backend_name,
            machine_id=args.machine_id,
            runtime_root=args.runtime_root,
            auto_ingest=not args.no_auto_ingest,
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
