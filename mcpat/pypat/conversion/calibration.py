from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable


DEFAULT_CALIBRATION_FILENAME = "kunpeng920_calibration.json"


@dataclass
class CalibrationRun:
    path: Path
    label: str
    command: str
    duration_s: float
    average_power_w: float | None
    hpre_ops: float
    sec_ops: float
    zip_ops: float
    hccs_ops: float
    metadata: Dict[str, Any]


def _read_env_file(path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_delta_file(path: Path) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        delta = _safe_float(parts[3])
        if delta is None:
            continue
        result[parts[0]] = delta
    return result


def _parse_perf_stat_csv(path: Path) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 3:
            continue
        value = _safe_float(parts[0])
        if value is None:
            continue
        event_name = parts[2]
        result[event_name] = result.get(event_name, 0.0) + value
    return result


def _sum_matching_suffix(delta: Dict[str, float], suffix: str) -> float:
    total = 0.0
    for key, value in delta.items():
        if key.endswith(suffix):
            total += value
    return total


def _sum_matching_event(perf_events: Dict[str, float], needles: Iterable[str]) -> float:
    lowered_needles = tuple(needle.lower() for needle in needles)
    total = 0.0
    for event_name, value in perf_events.items():
        lowered = event_name.lower()
        if any(needle in lowered for needle in lowered_needles):
            total += value
    return total


def _estimate_average_power_w(run_dir: Path, duration_s: float) -> float | None:
    if duration_s <= 0:
        return None

    powercap_delta = _read_delta_file(run_dir / "delta" / "powercap.tsv")
    energy_uj = sum(value for key, value in powercap_delta.items() if key.endswith("/energy_uj"))
    if energy_uj > 0:
        return energy_uj / 1_000_000.0 / duration_s

    hwmon_before = _read_delta_file(run_dir / "before" / "hwmon.tsv")
    hwmon_after = _read_delta_file(run_dir / "after" / "hwmon.tsv")
    samples: list[float] = []
    for key, after_value in hwmon_after.items():
        if not key.endswith("/power1_input") and "power" not in Path(key).name:
            continue
        before_value = hwmon_before.get(key)
        if before_value is None:
            continue
        # hwmon power inputs are typically microwatts.
        samples.append(((before_value + after_value) / 2.0) / 1_000_000.0)
    if samples:
        return sum(samples) / len(samples)

    return None


def _classify_run(label: str, command: str) -> set[str]:
    text = f"{label} {command}".lower()
    tags: set[str] = set()
    if "idle" in text:
        tags.add("idle")
    if any(token in text for token in ("hpre", "rsa", "dh", "ecdh", "ecdsa", "sm2", "x25519", "x448")):
        tags.add("hpre")
    if any(token in text for token in ("sec", "aes", "sm4", "sha", "sm3", "digest", "aead", "cipher")):
        tags.add("sec")
    if any(token in text for token in ("zip", "zlib", "gzip", "deflate", "lz4", "lz77", "compress", "decompress")):
        tags.add("zip")
    if any(token in text for token in ("hccs", "hha", "sccl", "remote numa", "remote-numa", "stream", "uncore")):
        tags.add("hccs")
    return tags


def _load_run(run_dir: Path) -> CalibrationRun:
    env = _read_env_file(run_dir / "meta" / "run.env")
    label = env.get("label", run_dir.name)
    command = env.get("command", "")
    duration_s = _safe_float(env.get("workload_duration_s")) or 0.0
    average_power_w = _estimate_average_power_w(run_dir, duration_s)

    hpre_delta = _read_delta_file(run_dir / "delta" / "hisi_hpre.tsv")
    sec_delta = _read_delta_file(run_dir / "delta" / "hisi_sec2.tsv")
    zip_delta = _read_delta_file(run_dir / "delta" / "hisi_zip.tsv")
    perf_delta = _parse_perf_stat_csv(run_dir / "perf_stat.csv")

    hpre_ops = _sum_matching_suffix(hpre_delta, "/recv_cnt")
    if hpre_ops <= 0:
        hpre_ops = _sum_matching_suffix(hpre_delta, "/send_cnt")

    sec_ops = _sum_matching_suffix(sec_delta, "/recv_cnt")
    if sec_ops <= 0:
        sec_ops = _sum_matching_suffix(sec_delta, "/send_cnt")

    zip_ops = _sum_matching_suffix(zip_delta, "/recv_cnt")
    if zip_ops <= 0:
        zip_ops = _sum_matching_suffix(zip_delta, "/send_cnt")

    hccs_ops = _sum_matching_event(
        perf_delta,
        (
            "hha",
            "sccl",
            "ddrc",
            "l3c",
            "rx_operations",
            "tx_operations",
            "flux",
        ),
    )

    tags = sorted(_classify_run(label, command))

    return CalibrationRun(
        path=run_dir,
        label=label,
        command=command,
        duration_s=duration_s,
        average_power_w=average_power_w,
        hpre_ops=hpre_ops,
        sec_ops=sec_ops,
        zip_ops=zip_ops,
        hccs_ops=hccs_ops,
        metadata={
            "tags": tags,
            "exit_code": env.get("workload_exit_code", ""),
        },
    )


def _discover_run_dirs(dataset_root: Path) -> list[Path]:
    if (dataset_root / "meta" / "run.env").exists():
        return [dataset_root]
    result: list[Path] = []
    for candidate in sorted(dataset_root.iterdir()):
        if not candidate.is_dir():
            continue
        if (candidate / "meta" / "run.env").exists():
            result.append(candidate)
    return result


def _load_area_overrides(dataset_root: Path) -> Dict[str, float]:
    for name in ("area_overrides.json", "kunpeng920_area_overrides.json"):
        path = dataset_root / name
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return {str(key): float(value) for key, value in payload.items()}
    return {}


def _fit_switch_energy(energy_j: float, operations: float) -> float:
    if energy_j <= 0 or operations <= 0:
        return 0.0
    return energy_j / operations


def build_kunpeng920_calibration(
    dataset_root: Path | str,
    output_file: Path | str | None = None,
) -> Dict[str, Any]:
    dataset_root = Path(dataset_root)
    run_dirs = _discover_run_dirs(dataset_root)
    if not run_dirs:
        raise FileNotFoundError(
            f"No Kunpeng920 collection runs found under {dataset_root}"
        )

    runs = [_load_run(run_dir) for run_dir in run_dirs]
    area_overrides = _load_area_overrides(dataset_root)

    idle_run = next((run for run in runs if "idle" in run.metadata["tags"]), None)
    idle_power_w = idle_run.average_power_w if idle_run is not None else 0.0

    def fit_block(tag: str, op_attr: str) -> Dict[str, Any]:
        active_run = next(
            (
                run
                for run in runs
                if tag in run.metadata["tags"]
                and "idle" not in run.metadata["tags"]
                and run.average_power_w is not None
            ),
            None,
        )
        idle_tag_run = next(
            (
                run
                for run in runs
                if tag in run.metadata["tags"]
                and "idle" in run.metadata["tags"]
                and run.average_power_w is not None
            ),
            None,
        )
        if active_run is None or active_run.average_power_w is None:
            return {
                "static_power_w": 0.0,
                "switch_energy_j": 0.0,
                "evidence": {
                    "run": None,
                    "reason": "no isolated run with power data",
                },
            }
        operations = float(getattr(active_run, op_attr))
        dynamic_power_w = max(0.0, active_run.average_power_w - idle_power_w)
        dynamic_energy_j = dynamic_power_w * active_run.duration_s
        switch_energy_j = _fit_switch_energy(dynamic_energy_j, operations)
        static_power_w = 0.0
        if idle_tag_run is not None and idle_tag_run.average_power_w is not None:
            static_power_w = max(0.0, idle_tag_run.average_power_w - idle_power_w)
        return {
            "static_power_w": static_power_w,
            "switch_energy_j": switch_energy_j,
            "evidence": {
                "run": str(active_run.path),
                "average_power_w": active_run.average_power_w,
                "idle_power_w": idle_power_w,
                "duration_s": active_run.duration_s,
                "operations": operations,
                "idle_run": str(idle_tag_run.path) if idle_tag_run is not None else None,
            },
        }

    hpre = fit_block("hpre", "hpre_ops")
    sec = fit_block("sec", "sec_ops")
    zip_block = fit_block("zip", "zip_ops")
    hccs = fit_block("hccs", "hccs_ops")

    overrides = {
        "custom_hccs_area": area_overrides.get("custom_hccs_area", 0.0),
        "custom_hccs_static_power": hccs["static_power_w"],
        "custom_hccs_switch_energy": hccs["switch_energy_j"],
        "custom_hpre_area": area_overrides.get("custom_hpre_area", 0.0),
        "custom_hpre_static_power": hpre["static_power_w"],
        "custom_hpre_switch_energy": hpre["switch_energy_j"],
        "custom_sec_area": area_overrides.get("custom_sec_area", 0.0),
        "custom_sec_static_power": sec["static_power_w"],
        "custom_sec_switch_energy": sec["switch_energy_j"],
        "custom_zip_area": area_overrides.get("custom_zip_area", 0.0),
        "custom_zip_static_power": zip_block["static_power_w"],
        "custom_zip_switch_energy": zip_block["switch_energy_j"],
    }

    payload = {
        "profile_name": "arm64-kunpeng920",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(dataset_root),
        "idle_power_w": idle_power_w,
        "overrides": overrides,
        "evidence": {
            "hccs": hccs["evidence"],
            "hpre": hpre["evidence"],
            "sec": sec["evidence"],
            "zip": zip_block["evidence"],
            "runs": [
                {
                    "path": str(run.path),
                    "label": run.label,
                    "command": run.command,
                    "duration_s": run.duration_s,
                    "average_power_w": run.average_power_w,
                    "tags": run.metadata["tags"],
                    "hpre_ops": run.hpre_ops,
                    "sec_ops": run.sec_ops,
                    "zip_ops": run.zip_ops,
                    "hccs_ops": run.hccs_ops,
                }
                for run in runs
            ],
        },
    }

    if output_file is not None:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    return payload


def load_kunpeng920_calibration(calibration_file: Path | str) -> Dict[str, Any]:
    path = Path(calibration_file)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def apply_kunpeng920_calibration(
    profile: Dict[str, Any], calibration_payload: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(profile)
    overrides = calibration_payload.get("overrides", {})
    for key, value in overrides.items():
        merged[key] = value
    merged["calibration"] = {
        "source": calibration_payload.get("dataset_root", ""),
        "generated_at": calibration_payload.get("generated_at", ""),
        "idle_power_w": calibration_payload.get("idle_power_w", 0.0),
        "overrides_applied": sorted(overrides.keys()),
    }
    return merged


def resolve_kunpeng920_calibration_file(
    *,
    target_dir: Path | None = None,
    explicit_file: Path | None = None,
    explicit_dataset: Path | None = None,
    default_repo_file: Path | None = None,
) -> Path | None:
    if explicit_dataset is not None:
        output_file = explicit_file or (
            (target_dir / DEFAULT_CALIBRATION_FILENAME)
            if target_dir is not None
            else explicit_dataset / DEFAULT_CALIBRATION_FILENAME
        )
        build_kunpeng920_calibration(explicit_dataset, output_file)
        return output_file

    env_dataset = os.getenv("MCPAT_KUNPENG920_CALIBRATION_DATASET")
    if env_dataset:
        dataset_path = Path(env_dataset)
        output_file = explicit_file or (
            (target_dir / DEFAULT_CALIBRATION_FILENAME)
            if target_dir is not None
            else dataset_path / DEFAULT_CALIBRATION_FILENAME
        )
        build_kunpeng920_calibration(dataset_path, output_file)
        return output_file

    if explicit_file is not None and explicit_file.exists():
        return explicit_file

    env_file = os.getenv("MCPAT_KUNPENG920_CALIBRATION")
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            return env_path

    if target_dir is not None:
        target_file = target_dir / DEFAULT_CALIBRATION_FILENAME
        if target_file.exists():
            return target_file

    if default_repo_file is not None and default_repo_file.exists():
        return default_repo_file

    return None
