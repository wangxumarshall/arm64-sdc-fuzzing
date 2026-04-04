from __future__ import annotations

import copy
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence


_MISSING = object()
_SIZE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([kmgt]?i?b)?\s*$", re.IGNORECASE)
_FREQ_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([gmkh]?hz)?\s*$", re.IGNORECASE)
_SIZE_UNITS = {
    None: 1,
    "b": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
    "tb": 1000**4,
    "tib": 1024**4,
}
_FREQ_UNITS_TO_MHZ = {
    None: 1.0,
    "hz": 1.0 / 1_000_000.0,
    "khz": 1.0 / 1_000.0,
    "mhz": 1.0,
    "ghz": 1_000.0,
}


@dataclass(frozen=True)
class Kunpeng920McPATModel:
    system: Dict[str, Any]
    core: Dict[str, Any]
    caches: Dict[str, Dict[str, Any]]
    memory: Dict[str, Any]
    noc: Dict[str, Any]
    io: Dict[str, Dict[str, Any]]
    identity: Dict[str, Any]
    topology: Dict[str, Any]
    sources: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_float(value[0])
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    parsed = _coerce_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _coerce_size_bytes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_size_bytes(value[0])
    if not isinstance(value, str):
        return None

    match = _SIZE_RE.match(value)
    if match is None:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) is not None else None
    return int(round(number * _SIZE_UNITS[unit]))


def _coerce_frequency_mhz(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return None
        # Treat large bare numerics as Hz to tolerate gem5-ish raw frequencies.
        if numeric > 100_000.0:
            numeric *= _FREQ_UNITS_TO_MHZ["hz"]
        return int(round(numeric))
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_frequency_mhz(value[0])
    if not isinstance(value, str):
        return None

    match = _FREQ_RE.match(value)
    if match is None:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) is not None else None
    return int(round(number * _FREQ_UNITS_TO_MHZ[unit]))


def _clock_period_ps(clock_mhz: int) -> float:
    if clock_mhz <= 0:
        return 0.0
    return 1_000_000.0 / float(clock_mhz)


def _lookup_path(container: Any, path: str) -> Any:
    current = container
    for segment in path.split("."):
        if isinstance(current, list):
            if segment.isdigit():
                index = int(segment)
                if index >= len(current):
                    return _MISSING
                current = current[index]
            elif len(current) == 1 and isinstance(current[0], dict):
                current = current[0]
            else:
                return _MISSING

        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
            continue

        if isinstance(current, list):
            continue

        return _MISSING

    return current


def _any_path_exists(container: Any, paths: Iterable[str]) -> bool:
    return any(_lookup_path(container, path) is not _MISSING for path in paths)


def _first_config_value(
    container: Mapping[str, Any],
    parser,
    paths: Iterable[str],
    default: Any,
) -> Any:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        parsed = parser(value) if parser is not None else value
        if parsed is not None:
            return parsed
    return default


def _first_config_value_with_source(
    container: Mapping[str, Any],
    parser,
    paths: Iterable[str],
    default: Any,
    *,
    default_source: str,
) -> tuple[Any, str]:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        parsed = parser(value) if parser is not None else value
        if parsed is not None:
            return parsed, f"config.{path}"
    return default, default_source


def _container_length(container: Any, paths: Iterable[str]) -> int | None:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            numeric_keys = [key for key in value.keys() if str(key).isdigit()]
            if numeric_keys:
                return len(numeric_keys)
            if value:
                return len(value)
    return None


def _container_length_with_source(
    container: Any, paths: Iterable[str]
) -> tuple[int | None, str | None]:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        if isinstance(value, list):
            return len(value), f"config.{path}"
        if isinstance(value, dict):
            numeric_keys = [key for key in value.keys() if str(key).isdigit()]
            if numeric_keys:
                return len(numeric_keys), f"config.{path}"
            if value:
                return len(value), f"config.{path}"
    return None, None


def _first_non_zero(*values: float) -> float:
    for value in values:
        if value > 0:
            return value
    return values[-1] if values else 0.0


def _to_stat_float(value: Any) -> float:
    parsed = _coerce_float(value)
    if parsed is None or math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _find_first_stat(raw_stats: Mapping[str, Any], aliases: Iterable[str]) -> float:
    for alias in aliases:
        if alias in raw_stats:
            return _to_stat_float(raw_stats[alias])
    for alias in aliases:
        for key, value in raw_stats.items():
            if key.endswith(alias):
                return _to_stat_float(value)
    return 0.0


def _find_first_stat_with_source(
    raw_stats: Mapping[str, Any], aliases: Iterable[str]
) -> tuple[float, str | None]:
    for alias in aliases:
        if alias in raw_stats:
            return _to_stat_float(raw_stats[alias]), alias
    for alias in aliases:
        for key, value in raw_stats.items():
            if key.endswith(alias):
                return _to_stat_float(value), key
    return 0.0, None


def _sum_matching_suffixes(
    raw_stats: Mapping[str, Any], aliases: Iterable[str]
) -> float:
    matched_keys: set[str] = set()
    total = 0.0
    for alias in aliases:
        for key, value in raw_stats.items():
            if key in matched_keys:
                continue
            if key == alias or key.endswith(alias):
                matched_keys.add(key)
                total += _to_stat_float(value)
    return total


def _sum_matching_suffixes_with_sources(
    raw_stats: Mapping[str, Any], aliases: Iterable[str]
) -> tuple[float, list[str]]:
    matched_keys: list[str] = []
    seen: set[str] = set()
    total = 0.0
    for alias in aliases:
        for key, value in raw_stats.items():
            if key in seen:
                continue
            if key == alias or key.endswith(alias):
                seen.add(key)
                matched_keys.append(key)
                total += _to_stat_float(value)
    return total, matched_keys


def _sum_matching_fragments(
    raw_stats: Mapping[str, Any], required_fragments: Iterable[str]
) -> float:
    fragments = [fragment.lower() for fragment in required_fragments]
    total = 0.0
    for key, value in raw_stats.items():
        lowered = key.lower()
        if all(fragment in lowered for fragment in fragments):
            total += _to_stat_float(value)
    return total


def _sum_matching_fragments_with_sources(
    raw_stats: Mapping[str, Any], required_fragments: Iterable[str]
) -> tuple[float, list[str]]:
    fragments = [fragment.lower() for fragment in required_fragments]
    total = 0.0
    matched_keys: list[str] = []
    for key, value in raw_stats.items():
        lowered = key.lower()
        if all(fragment in lowered for fragment in fragments):
            matched_keys.append(key)
            total += _to_stat_float(value)
    return total, matched_keys


def _sum_matching_any_fragments_with_sources(
    raw_stats: Mapping[str, Any], fragments: Iterable[str]
) -> tuple[float, list[str]]:
    lowered_fragments = [fragment.lower() for fragment in fragments]
    total = 0.0
    matched_keys: list[str] = []
    for key, value in raw_stats.items():
        lowered = key.lower()
        if any(
            re.search(r"(^|[^a-z0-9])" + re.escape(fragment) + r"([^a-z0-9]|$)", lowered)
            for fragment in lowered_fragments
        ):
            matched_keys.append(key)
            total += _to_stat_float(value)
    return total, matched_keys


def _format_stat(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9):
        return str(int(round(value)))
    return f"{value:.6f}"


def _normalize_sources(sources: Sequence[str | None]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source is None or source == "":
            continue
        if source not in seen:
            seen.add(source)
            ordered.append(source)
    return ordered


def build_kunpeng920_model(
    config: Mapping[str, Any], profile: Mapping[str, Any]
) -> Kunpeng920McPATModel:
    default_clock_mhz = int(profile.get("target_core_clockrate_mhz", 2600))
    target_core_clockrate_mhz, clock_source = _first_config_value_with_source(
        config,
        _coerce_frequency_mhz,
        (
            "system.clk_freq",
            "board.clk_freq",
            "system.clock",
            "board.clock",
        ),
        default_clock_mhz,
        default_source="profile.target_core_clockrate_mhz",
    )

    explicit_core_count, explicit_core_source = _first_config_value_with_source(
        config,
        _coerce_int,
        (
            "system.processor.num_cores",
            "board.processor.num_cores",
            "system.num_cores",
            "board.num_cores",
        ),
        None,
        default_source="profile.number_of_cores",
    )
    detected_core_count, detected_core_source = _container_length_with_source(
        config,
        (
            "system.processor.cores",
            "board.processor.cores",
            "system.processor.o3",
            "board.processor.o3",
            "system.cpu",
            "board.cpu",
        ),
    )
    if explicit_core_count is not None and explicit_core_count > 0:
        number_of_cores = explicit_core_count
        core_count_source = explicit_core_source
    elif detected_core_count is not None and detected_core_count > 0:
        number_of_cores = detected_core_count
        core_count_source = detected_core_source or "config.<container>"
    else:
        number_of_cores = int(profile.get("number_of_cores", 64))
        core_count_source = "profile.number_of_cores"
    number_of_cores = max(1, int(number_of_cores))

    number_hardware_threads, thread_source = _first_config_value_with_source(
        config,
        _coerce_int,
        (
            "system.processor.o3.0.core.numThreads",
            "board.processor.o3.0.core.numThreads",
            "system.processor.cores.0.core.numThreads",
            "board.processor.cores.0.core.numThreads",
            "system.cpu.0.numThreads",
            "board.cpu.0.numThreads",
        ),
        int(profile.get("number_hardware_threads", 1)),
        default_source="profile.number_hardware_threads",
    )
    number_hardware_threads = max(1, int(number_hardware_threads))

    cores_per_cluster = int(profile.get("cores_per_cluster", 4))
    default_clusters_per_die = int(profile.get("clusters_per_die", 8))
    default_compute_dies = int(profile.get("compute_dies", 2))
    io_dies = int(profile.get("io_dies", 1))
    explicit_cache_hierarchy = _any_path_exists(
        config,
        (
            "system.cache_hierarchy",
            "board.cache_hierarchy",
        ),
    )
    explicit_l3 = _any_path_exists(
        config,
        (
            "system.cache_hierarchy.l3_size",
            "board.cache_hierarchy.l3_size",
            "system.cache_hierarchy.llc_size",
            "board.cache_hierarchy.llc_size",
        ),
    )
    has_l3 = explicit_l3 or not explicit_cache_hierarchy

    number_of_clusters = max(1, math.ceil(number_of_cores / cores_per_cluster))
    number_of_l3s = number_of_clusters if has_l3 else 0
    compute_dies = (
        max(1, math.ceil(number_of_clusters / default_clusters_per_die))
        if has_l3
        else 0
    )
    number_of_nocs = (
        min(default_compute_dies, compute_dies) if compute_dies > 0 else 0
    )

    l1i_size, l1i_source = _first_config_value_with_source(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l1i_size", "board.cache_hierarchy.l1i_size"),
        int(profile.get("l1i_size", 65536)),
        default_source="profile.l1i_size",
    )
    l1d_size, l1d_source = _first_config_value_with_source(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l1d_size", "board.cache_hierarchy.l1d_size"),
        int(profile.get("l1d_size", 65536)),
        default_source="profile.l1d_size",
    )
    l2_size, l2_source = _first_config_value_with_source(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l2_size", "board.cache_hierarchy.l2_size"),
        int(profile.get("l2_size", 524288)),
        default_source="profile.l2_size",
    )
    l3_total_size, l3_source = _first_config_value_with_source(
        config,
        _coerce_size_bytes,
        (
            "system.cache_hierarchy.l3_size",
            "board.cache_hierarchy.l3_size",
            "system.cache_hierarchy.llc_size",
            "board.cache_hierarchy.llc_size",
        ),
        int(profile.get("l3_total_size", profile.get("l3_size", 67108864))),
        default_source="profile.l3_total_size",
    )
    l3_slice_size = (
        max(1, int(math.ceil(l3_total_size / number_of_l3s)))
        if number_of_l3s > 0
        else 0
    )

    explicit_memory_channels, memory_channel_source = _first_config_value_with_source(
        config,
        _coerce_int,
        (
            "system.memory.num_channels",
            "board.memory.num_channels",
            "system.mem_channels",
            "board.mem_channels",
        ),
        None,
        default_source="profile.number_mcs/profile.memory_channels_per_mc",
    )
    if explicit_memory_channels is None:
        number_mcs = int(profile.get("number_mcs", 2))
        memory_channels_per_mc = int(profile.get("memory_channels_per_mc", 4))
        memory_channel_source = "profile.number_mcs/profile.memory_channels_per_mc"
    elif explicit_memory_channels <= 4:
        number_mcs = 1
        memory_channels_per_mc = explicit_memory_channels
    else:
        number_mcs = min(int(profile.get("number_mcs", 2)), explicit_memory_channels)
        memory_channels_per_mc = max(
            1, math.ceil(explicit_memory_channels / number_mcs)
        )

    l3_slices_per_die = (
        max(1, int(math.ceil(number_of_l3s / max(1, compute_dies))))
        if number_of_l3s > 0
        else 0
    )
    memory_channels_total = int(number_mcs * memory_channels_per_mc)
    noc_horizontal_nodes = int(
        profile.get(
            "noc_horizontal_nodes",
            max(1, math.ceil(default_clusters_per_die / 2.0)),
        )
    )
    noc_vertical_nodes = int(
        profile.get(
            "noc_vertical_nodes",
            max(1, math.ceil(default_clusters_per_die / max(1, noc_horizontal_nodes))),
        )
    )
    noc_chip_coverage = float(
        profile.get(
            "noc_chip_coverage",
            (1.0 / float(max(1, number_of_nocs))) if number_of_nocs > 0 else 1.0,
        )
    )

    system = {
        "number_of_cores": number_of_cores,
        "number_of_l1directories": 0,
        "number_of_l2directories": 0,
        "number_of_l2s": number_of_cores,
        "private_l2": int(profile.get("private_l2", 1)),
        "number_of_l3s": number_of_l3s,
        "number_of_nocs": number_of_nocs,
        "number_cache_levels": 3 if number_of_l3s > 0 else 2,
        "number_hardware_threads": number_hardware_threads,
        "machine_bits": int(profile.get("machine_bits", 64)),
        "virtual_address_width": int(profile.get("virtual_address_width", 64)),
        "physical_address_width": int(profile.get("physical_address_width", 52)),
        "virtual_memory_page_size": int(profile.get("virtual_memory_page_size", 4096)),
        "mcpat_tech_node_nm": int(profile.get("mcpat_tech_node_nm", 22)),
        "target_core_clockrate_mhz": target_core_clockrate_mhz,
        "clock_period_ps": _clock_period_ps(target_core_clockrate_mhz),
        "temperature_k": int(profile.get("temperature_k", 380)),
        "interconnect_projection_type": int(
            profile.get("interconnect_projection_type", 0)
        ),
        "device_type": int(profile.get("device_type", 0)),
        "longer_channel_device": int(profile.get("longer_channel_device", 0)),
        "power_gating": int(profile.get("power_gating", 0)),
        "clusters": number_of_clusters,
        "cores_per_cluster": cores_per_cluster,
        "compute_dies": compute_dies,
        "io_dies": io_dies,
    }

    core = {
        "target_core_clockrate_mhz": target_core_clockrate_mhz,
        "clock_period_ps": system["clock_period_ps"],
        "vdd": int(profile.get("vdd", 0)),
        "instruction_length": int(profile.get("instruction_length", 32)),
        "opcode_width": int(profile.get("opcode_width", 16)),
        "micro_opcode_width": int(profile.get("micro_opcode_width", 8)),
        "machine_type": int(profile.get("machine_type", 0)),
        "fetch_width": int(profile.get("fetch_width", 4)),
        "decode_width": int(profile.get("decode_width", 4)),
        "issue_width": int(profile.get("issue_width", 4)),
        "commit_width": int(profile.get("commit_width", 4)),
        "fp_issue_width": int(profile.get("fp_issue_width", 2)),
        "prediction_width": int(profile.get("prediction_width", 1)),
        "pipelines_per_core": str(profile.get("pipelines_per_core", "3,2")),
        "pipeline_depth": str(profile.get("pipeline_depth", "13,17")),
        "alu_per_core": int(profile.get("alu_per_core", 3)),
        "mul_per_core": int(profile.get("mul_per_core", 1)),
        "fpu_per_core": int(profile.get("fpu_per_core", 2)),
        "instruction_buffer_size": int(profile.get("instruction_buffer_size", 16)),
        "decoded_stream_buffer_size": int(
            profile.get("decoded_stream_buffer_size", 16)
        ),
        "instruction_window_size": int(profile.get("instruction_window_size", 33)),
        "fp_instruction_window_size": int(
            profile.get("fp_instruction_window_size", 33)
        ),
        "rob_size": int(profile.get("rob_size", 128)),
        "archi_regs_irf_size": int(profile.get("archi_regs_irf_size", 31)),
        "archi_regs_frf_size": int(profile.get("archi_regs_frf_size", 32)),
        "phy_regs_irf_size": int(profile.get("phy_regs_irf_size", 160)),
        "phy_regs_frf_size": int(profile.get("phy_regs_frf_size", 160)),
        "store_buffer_size": int(profile.get("store_buffer_size", 32)),
        "load_buffer_size": int(profile.get("load_buffer_size", 32)),
        "memory_ports": int(profile.get("memory_ports", 2)),
        "ras_size": int(profile.get("ras_size", 31)),
        "itlb_entries": int(profile.get("itlb_entries", 32)),
        "dtlb_entries": int(profile.get("dtlb_entries", 32)),
        "btb_entries": int(profile.get("btb_entries", 64)),
    }

    caches = {
        "l1i": {
            "size_bytes": l1i_size,
            "block_size": int(profile.get("l1i_block_size", 64)),
            "assoc": int(profile.get("l1i_assoc", 4)),
            "latency_cycles": int(profile.get("l1i_latency", 3)),
            "mshrs": int(profile.get("l1i_mshrs", 8)),
        },
        "l1d": {
            "size_bytes": l1d_size,
            "block_size": int(profile.get("l1d_block_size", 64)),
            "assoc": int(profile.get("l1d_assoc", 4)),
            "latency_cycles": int(profile.get("l1d_latency", 4)),
            "mshrs": int(profile.get("l1d_mshrs", 8)),
        },
        "l2": {
            "size_bytes": l2_size,
            "block_size": int(profile.get("l2_block_size", 64)),
            "assoc": int(profile.get("l2_assoc", 8)),
            "latency_cycles": int(profile.get("l2_latency", 10)),
            "mshrs": int(profile.get("l2_mshrs", 16)),
        },
        "l3": {
            "size_bytes": l3_slice_size,
            "total_size_bytes": l3_total_size,
            "block_size": int(profile.get("l3_block_size", 64)),
            "assoc": int(profile.get("l3_assoc", 16)),
            "latency_cycles": int(profile.get("l3_latency", 36)),
            "mshrs": int(profile.get("l3_mshrs", 64)),
        },
    }

    memory = {
        "number_mcs": int(number_mcs),
        "memory_channels_per_mc": int(memory_channels_per_mc),
        "memory_channels_total": memory_channels_total,
        "number_ranks": int(profile.get("number_ranks", 2)),
        "memory_clock_mhz": int(profile.get("memory_clock_mhz", 1466)),
        "ddr_data_rate_mtps": int(profile.get("ddr_data_rate_mtps", 2933)),
        "databus_width": int(profile.get("databus_width", 64)),
        "addressbus_width": int(profile.get("addressbus_width", 52)),
    }

    noc = {
        "topology": str(profile.get("noc_topology", "2d-mesh")),
        "horizontal_nodes": noc_horizontal_nodes,
        "vertical_nodes": noc_vertical_nodes,
        "has_global_link": int(
            profile.get("noc_has_global_link", 1 if number_of_nocs > 1 else 0)
        ),
        "link_throughput": int(profile.get("noc_link_throughput", 1)),
        "link_latency": int(profile.get("noc_link_latency", 1)),
        "input_ports": int(profile.get("noc_input_ports", 2)),
        "output_ports": int(profile.get("noc_output_ports", 2)),
        "virtual_channel_per_port": int(
            profile.get("noc_virtual_channel_per_port", 4)
        ),
        "input_buffer_entries_per_vc": int(
            profile.get("noc_input_buffer_entries_per_vc", 4)
        ),
        "flit_bits": int(profile.get("noc_flit_bits", 256)),
        "chip_coverage": noc_chip_coverage,
        "route_over_perc": float(profile.get("noc_route_over_perc", 0.5)),
        "number_of_crossbars": int(profile.get("noc_number_of_crossbars", 1)),
        "crossbar_inputs": int(
            profile.get("noc_crossbar_inputs", profile.get("noc_input_ports", 2))
        ),
        "crossbar_outputs": int(
            profile.get("noc_crossbar_outputs", profile.get("noc_output_ports", 2))
        ),
    }

    io = {
        "niu": {
            "number_units": int(profile.get("niu_units", 0)),
            "clockrate_mhz": int(profile.get("niu_clockrate_mhz", 350)),
            "duty_cycle": float(profile.get("niu_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("niu_total_load_perc", 0.0)),
            "roce_ports": int(profile.get("roce_ports", 2)),
            "line_rate_gbps": int(profile.get("roce_line_rate_gbps", 100)),
        },
        "pcie": {
            "number_units": int(profile.get("pcie_units", 0)),
            "num_channels": int(profile.get("pcie_channels", 8)),
            "clockrate_mhz": int(profile.get("pcie_clockrate_mhz", 350)),
            "duty_cycle": float(profile.get("pcie_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("pcie_total_load_perc", 0.0)),
            "generation": int(profile.get("pcie_generation", 4)),
        },
        "flashc": {
            "number_flashcs": int(profile.get("flash_controllers", 0)),
            "peak_transfer_rate": int(profile.get("flash_peak_transfer_rate", 200)),
            "duty_cycle": float(profile.get("flash_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("flash_total_load_perc", 0.0)),
        },
    }

    topology = {
        "cores_per_cluster": cores_per_cluster,
        "clusters": number_of_clusters,
        "clusters_per_die": default_clusters_per_die,
        "compute_dies": compute_dies,
        "io_dies": io_dies,
        "l3_slices": number_of_l3s,
        "l3_slices_per_die": l3_slices_per_die,
        "l3_slice_mode": str(profile.get("l3_slice_mode", "cluster-shared")),
        "l3_default_mode": str(profile.get("l3_default_mode", "partition")),
        "memory_channels_total": memory_channels_total,
        "memory_channels_per_mc": int(memory_channels_per_mc),
        "number_mcs": int(number_mcs),
    }

    sources = {
        "field_sources": {
            "clock_mhz": clock_source,
            "number_of_cores": core_count_source,
            "number_hardware_threads": thread_source,
            "l1i_size": l1i_source,
            "l1d_size": l1d_source,
            "l2_size": l2_source,
            "l3_total_size": l3_source,
            "memory_channels": memory_channel_source,
        },
        "modeling_notes": [
            str(
                profile.get(
                    "profile_source",
                    "kunpeng920.md plus conservative defaults where the note omits exact McPAT fields",
                )
            ),
            "McPAT models Kunpeng920 as homogeneous ARMv8.2-A OoO cores with private L2s and homogeneous L3 slices.",
            "Die-level coherency, RoCE, and accelerator behavior remain approximations even when the topology fields are explicit.",
        ],
    }

    return Kunpeng920McPATModel(
        system=system,
        core=core,
        caches=caches,
        memory=memory,
        noc=noc,
        io=io,
        identity={
            "profile_name": str(profile.get("profile_name", "arm64-kunpeng920")),
            "isa_name": str(profile.get("isa_name", "ARMv8.2-A")),
            "core_name": str(profile.get("core_name", "TaiShan V110-like")),
        },
        topology=topology,
        sources=sources,
    )


def normalize_kunpeng920_config(
    config: Mapping[str, Any], base_profile: Mapping[str, Any]
) -> Dict[str, Any]:
    normalized = copy.deepcopy(dict(config))
    profile = copy.deepcopy(dict(base_profile))
    model = build_kunpeng920_model(normalized, profile)
    flat_profile = profile
    flat_profile.update(
        {
            "target_core_clockrate_mhz": model.core["target_core_clockrate_mhz"],
            "clock_period_ps": model.core["clock_period_ps"],
            "number_hardware_threads": model.system["number_hardware_threads"],
            "number_of_cores": model.system["number_of_cores"],
            "number_of_l2s": model.system["number_of_l2s"],
            "private_l2": model.system["private_l2"],
            "number_of_l3s": model.system["number_of_l3s"],
            "number_of_nocs": model.system["number_of_nocs"],
            "number_cache_levels": model.system["number_cache_levels"],
            "cores_per_cluster": model.topology["cores_per_cluster"],
            "clusters": model.topology["clusters"],
            "clusters_per_die": model.topology["clusters_per_die"],
            "compute_dies": model.topology["compute_dies"],
            "io_dies": model.topology["io_dies"],
            "l3_slices_per_die": model.topology["l3_slices_per_die"],
            "l3_slice_mode": model.topology["l3_slice_mode"],
            "l3_default_mode": model.topology["l3_default_mode"],
            "l1i_size": model.caches["l1i"]["size_bytes"],
            "l1d_size": model.caches["l1d"]["size_bytes"],
            "l2_size": model.caches["l2"]["size_bytes"],
            "l3_size": model.caches["l3"]["size_bytes"],
            "l3_total_size": model.caches["l3"]["total_size_bytes"],
            "memory_clock_mhz": model.memory["memory_clock_mhz"],
            "number_mcs": model.memory["number_mcs"],
            "memory_channels_per_mc": model.memory["memory_channels_per_mc"],
            "memory_channels_total": model.memory["memory_channels_total"],
            "noc_topology": model.noc["topology"],
            "noc_horizontal_nodes": model.noc["horizontal_nodes"],
            "noc_vertical_nodes": model.noc["vertical_nodes"],
            "noc_has_global_link": model.noc["has_global_link"],
            "noc_link_throughput": model.noc["link_throughput"],
            "noc_link_latency": model.noc["link_latency"],
            "noc_input_ports": model.noc["input_ports"],
            "noc_output_ports": model.noc["output_ports"],
            "noc_virtual_channel_per_port": model.noc["virtual_channel_per_port"],
            "noc_input_buffer_entries_per_vc": model.noc["input_buffer_entries_per_vc"],
            "noc_flit_bits": model.noc["flit_bits"],
            "noc_chip_coverage": model.noc["chip_coverage"],
            "noc_route_over_perc": model.noc["route_over_perc"],
            "noc_number_of_crossbars": model.noc["number_of_crossbars"],
            "noc_crossbar_inputs": model.noc["crossbar_inputs"],
            "noc_crossbar_outputs": model.noc["crossbar_outputs"],
            "niu_units": model.io["niu"]["number_units"],
            "niu_clockrate_mhz": model.io["niu"]["clockrate_mhz"],
            "pcie_units": model.io["pcie"]["number_units"],
            "pcie_channels": model.io["pcie"]["num_channels"],
            "pcie_clockrate_mhz": model.io["pcie"]["clockrate_mhz"],
            "flash_controllers": model.io["flashc"]["number_flashcs"],
        }
    )
    normalized["profile"] = flat_profile
    normalized["mcpat"] = model.to_dict()
    return normalized


def normalize_kunpeng920_stats(
    stats: Dict[int, Dict[str, str]], config: Mapping[str, Any]
) -> Dict[int, Dict[str, str]]:
    normalized = {index: dict(values) for index, values in stats.items()}
    root_stats = normalized.setdefault(0, {})
    profile = config.get("profile", {})
    issue_width = max(1, int(profile.get("issue_width", 4)))
    memory_ports = max(1, int(profile.get("memory_ports", 2)))

    derived_stats: Dict[str, float] = {}
    derived_metadata: Dict[str, Dict[str, Any]] = {}

    def remember(
        name: str,
        value: float,
        *,
        method: str,
        sources: Sequence[str | None],
        note: str | None = None,
    ) -> None:
        derived_stats[name] = value
        metadata = {
            "value": value,
            "method": method,
            "sources": _normalize_sources(sources),
        }
        if note:
            metadata["note"] = note
        derived_metadata[name] = metadata

    total_instructions, total_instructions_source = _find_first_stat_with_source(
        root_stats,
        ("simInsts", "commitStats0.numInsts", "baseStats.numInsts"),
    )
    if total_instructions <= 0:
        total_instructions, total_instructions_source = _find_first_stat_with_source(
            root_stats, ("fetch2.totalInstructions",)
        )
    total_instructions_method = (
        "direct" if total_instructions > 0 and total_instructions_source else "default"
    )

    total_ops, total_ops_source = _find_first_stat_with_source(
        root_stats, ("simOps", "commitStats0.numOps", "baseStats.numOps")
    )
    if total_ops <= 0:
        total_ops = total_instructions
        total_ops_source = total_instructions_source
        total_ops_method = "fallback"
    else:
        total_ops_method = "direct"

    total_cycles, total_cycles_source = _find_first_stat_with_source(
        root_stats, ("baseStats.numCycles", "numCycles")
    )
    if total_cycles <= 0:
        sim_ticks, sim_ticks_source = _find_first_stat_with_source(root_stats, ("simTicks",))
        if sim_ticks > 0:
            total_cycles = sim_ticks / max(float(profile.get("clock_period_ps", 1.0)), 1.0)
            total_cycles_source = (
                f"{sim_ticks_source} / profile.clock_period_ps"
                if sim_ticks_source
                else "profile.clock_period_ps"
            )
            total_cycles_method = "fallback"
        else:
            total_cycles_method = "default"
    else:
        total_cycles_method = "direct"
    busy_cycles = total_cycles
    idle_cycles = max(0.0, total_cycles - busy_cycles)

    int_instructions, int_instructions_source = _find_first_stat_with_source(
        root_stats, ("commitStats0.numIntInsts", "fetch2.intInstructions")
    )
    int_instructions_method = (
        "direct" if int_instructions > 0 and int_instructions_source else "default"
    )

    fp_scalar_instructions, fp_scalar_source = _find_first_stat_with_source(
        root_stats, ("commitStats0.numFpInsts", "fetch2.fpInstructions")
    )
    vec_instructions, vec_instructions_source = _find_first_stat_with_source(
        root_stats, ("commitStats0.numVecInsts", "fetch2.vecInstructions")
    )
    fp_instructions = fp_scalar_instructions + vec_instructions

    branch_instructions, branch_instruction_source = _find_first_stat_with_source(
        root_stats, ("fetchStats0.numBranches", "executeStats0.numBranches")
    )
    if branch_instructions <= 0:
        branch_instructions, branch_sources = _sum_matching_suffixes_with_sources(
            root_stats,
            (
                "commitStats0.committedControl::IsDirectControl",
                "commitStats0.committedControl::IsIndirectControl",
                "commitStats0.committedControl::IsCondControl",
                "commitStats0.committedControl::IsCall",
                "commitStats0.committedControl::IsReturn",
            ),
        )
        branch_instruction_source = ", ".join(branch_sources) if branch_sources else None
        branch_instructions_method = "aggregated" if branch_sources else "default"
    else:
        branch_instructions_method = "direct"

    branch_mispredictions, branch_mispred_source = _find_first_stat_with_source(
        root_stats, ("numBranchMispred", "condIncorrect")
    )
    if branch_mispredictions <= 0:
        branch_mispredictions, mispred_sources = _sum_matching_suffixes_with_sources(
            root_stats, ("mispredict", "mispredicted")
        )
        branch_mispred_source = ", ".join(mispred_sources) if mispred_sources else None
        branch_mispred_method = "aggregated" if mispred_sources else "default"
    else:
        branch_mispred_method = "direct"

    load_instructions, load_instructions_source = _find_first_stat_with_source(
        root_stats,
        ("commitStats0.numLoadInsts", "executeStats0.numLoadInsts", "fetch2.loadInstructions"),
    )
    load_instructions_method = (
        "direct" if load_instructions > 0 and load_instructions_source else "default"
    )

    store_instructions, store_instructions_source = _find_first_stat_with_source(
        root_stats,
        (
            "commitStats0.numStoreInsts",
            "executeStats0.numStoreInsts",
            "fetch2.storeInstructions",
        ),
    )
    if store_instructions <= 0:
        mem_refs, mem_refs_source = _find_first_stat_with_source(
            root_stats, ("commitStats0.numMemRefs", "executeStats0.numMemRefs")
        )
        if mem_refs > 0:
            store_instructions = max(0.0, mem_refs - load_instructions)
            store_instructions_source = (
                f"{mem_refs_source} - load_instructions" if mem_refs_source else "load_instructions"
            )
            store_instructions_method = "fallback"
        else:
            store_instructions_method = "default"
    else:
        store_instructions_method = "direct"

    committed_instructions, committed_instructions_source = _find_first_stat_with_source(
        root_stats, ("commitStats0.numInsts",)
    )
    if committed_instructions <= 0:
        committed_instructions = total_instructions
        committed_instructions_source = total_instructions_source
        committed_instructions_method = "fallback"
    else:
        committed_instructions_method = "direct"
    committed_int_instructions = (
        int_instructions if int_instructions > 0 else committed_instructions
    )
    committed_fp_instructions = fp_instructions

    int_reg_reads, int_reg_reads_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numIntRegReads",)
    )
    if int_reg_reads <= 0 and int_instructions > 0:
        int_reg_reads = max(1.0, int_instructions * 2.0)
        int_reg_reads_source = "int_instructions * 2.0"
        int_reg_reads_method = "fallback"
    else:
        int_reg_reads_method = "direct" if int_reg_reads_source else "default"

    int_reg_writes, int_reg_writes_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numIntRegWrites",)
    )
    if int_reg_writes <= 0 and int_instructions > 0:
        int_reg_writes = int_instructions
        int_reg_writes_source = "int_instructions"
        int_reg_writes_method = "fallback"
    else:
        int_reg_writes_method = "direct" if int_reg_writes_source else "default"

    fp_reg_reads, fp_reg_reads_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numFpRegReads",)
    )
    vec_reg_reads, vec_reg_reads_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numVecRegReads",)
    )
    float_reg_reads = fp_reg_reads + vec_reg_reads

    fp_reg_writes, fp_reg_writes_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numFpRegWrites",)
    )
    vec_reg_writes, vec_reg_writes_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numVecRegWrites",)
    )
    float_reg_writes = fp_reg_writes + vec_reg_writes

    ialu_accesses, ialu_accesses_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numIntAluAccesses",)
    )
    if ialu_accesses <= 0 and int_instructions > 0:
        ialu_accesses = int_instructions
        ialu_accesses_source = "int_instructions"
        ialu_accesses_method = "fallback"
    else:
        ialu_accesses_method = "direct" if ialu_accesses_source else "default"

    fp_alu_accesses, fp_alu_accesses_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numFpAluAccesses",)
    )
    vec_alu_accesses, vec_alu_accesses_source = _find_first_stat_with_source(
        root_stats, ("executeStats0.numVecAluAccesses",)
    )
    fpu_accesses = fp_alu_accesses + vec_alu_accesses
    if fpu_accesses <= 0 and fp_instructions > 0:
        fpu_accesses = fp_instructions
        fpu_accesses_method = "fallback"
        fpu_accesses_sources = ["fp_instructions"]
    else:
        fpu_accesses_method = (
            "aggregated"
            if fp_alu_accesses_source or vec_alu_accesses_source
            else "default"
        )
        fpu_accesses_sources = [fp_alu_accesses_source, vec_alu_accesses_source]

    mul_accesses, mul_sources = _sum_matching_fragments_with_sources(
        root_stats, ("committedinsttype::", "mult")
    )
    if mul_accesses <= 0:
        div_accesses, div_sources = _sum_matching_fragments_with_sources(
            root_stats, ("committedinsttype::", "div")
        )
        mul_accesses = div_accesses
        mul_sources = div_sources
    if mul_accesses <= 0:
        mul_accesses = fpu_accesses * 0.25 if fpu_accesses > 0 else int_instructions * 0.05
        mul_sources = ["fpu_accesses * 0.25" if fpu_accesses > 0 else "int_instructions * 0.05"]
        mul_accesses_method = "fallback"
    else:
        mul_accesses_method = "aggregated"

    pipeline_duty_cycle = (
        min(1.0, committed_instructions / (total_cycles * issue_width))
        if total_cycles > 0
        else 0.0
    )
    lsu_duty_cycle = (
        min(1.0, (load_instructions + store_instructions) / (total_cycles * memory_ports))
        if total_cycles > 0
        else 0.0
    )

    icache_read_accesses, icache_read_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("icache.ReadReq_accesses::total", "icache.overallAccesses::total"),
    )
    if icache_read_accesses <= 0:
        icache_read_accesses = total_instructions
        icache_read_accesses_source = total_instructions_source
        icache_read_accesses_method = "fallback"
    else:
        icache_read_accesses_method = "direct"

    icache_read_misses, icache_read_misses_source = _find_first_stat_with_source(
        root_stats,
        ("icache.ReadReq_misses::total", "icache.overallMisses::total"),
    )
    icache_read_misses_method = (
        "direct" if icache_read_misses_source else "default"
    )

    dcache_read_accesses, dcache_read_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("dcache.ReadReq_accesses::total", "dcache.overallReadAccesses::total"),
    )
    if dcache_read_accesses <= 0:
        dcache_read_accesses = load_instructions
        dcache_read_accesses_source = load_instructions_source
        dcache_read_accesses_method = "fallback"
    else:
        dcache_read_accesses_method = "direct"

    dcache_write_accesses, dcache_write_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("dcache.WriteReq_accesses::total", "dcache.overallWriteAccesses::total"),
    )
    if dcache_write_accesses <= 0:
        dcache_write_accesses = store_instructions
        dcache_write_accesses_source = store_instructions_source
        dcache_write_accesses_method = "fallback"
    else:
        dcache_write_accesses_method = "direct"

    dcache_read_misses, dcache_read_misses_source = _find_first_stat_with_source(
        root_stats,
        ("dcache.ReadReq_misses::total", "dcache.overallReadMisses::total"),
    )
    dcache_read_misses_method = "direct" if dcache_read_misses_source else "default"

    dcache_write_misses, dcache_write_misses_source = _find_first_stat_with_source(
        root_stats,
        ("dcache.WriteReq_misses::total", "dcache.overallWriteMisses::total"),
    )
    dcache_write_misses_method = "direct" if dcache_write_misses_source else "default"

    l2_read_accesses, l2_read_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("l2.ReadReq_accesses::total", "l2cache.ReadReq_accesses::total", "l2.overallAccesses::total"),
    )
    if l2_read_accesses <= 0:
        l2_read_accesses = dcache_read_misses
        l2_read_accesses_source = dcache_read_misses_source
        l2_read_accesses_method = "fallback"
    else:
        l2_read_accesses_method = "direct"

    l2_write_accesses, l2_write_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("l2.WriteReq_accesses::total", "l2cache.WriteReq_accesses::total"),
    )
    if l2_write_accesses <= 0:
        l2_write_accesses = dcache_write_misses
        l2_write_accesses_source = dcache_write_misses_source
        l2_write_accesses_method = "fallback"
    else:
        l2_write_accesses_method = "direct"

    l2_read_misses, l2_read_misses_source = _find_first_stat_with_source(
        root_stats,
        ("l2.ReadReq_misses::total", "l2cache.ReadReq_misses::total", "l2.overallMisses::total"),
    )
    l2_read_misses_method = "direct" if l2_read_misses_source else "default"

    l2_write_misses, l2_write_misses_source = _find_first_stat_with_source(
        root_stats,
        ("l2.WriteReq_misses::total", "l2cache.WriteReq_misses::total"),
    )
    l2_write_misses_method = "direct" if l2_write_misses_source else "default"

    l3_read_accesses, l3_read_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("l3.ReadReq_accesses::total", "l3cache.ReadReq_accesses::total", "l3.overallAccesses::total"),
    )
    if l3_read_accesses <= 0:
        l3_read_accesses = l2_read_misses
        l3_read_accesses_source = l2_read_misses_source
        l3_read_accesses_method = "fallback"
    else:
        l3_read_accesses_method = "direct"

    l3_write_accesses, l3_write_accesses_source = _find_first_stat_with_source(
        root_stats,
        ("l3.WriteReq_accesses::total", "l3cache.WriteReq_accesses::total"),
    )
    if l3_write_accesses <= 0:
        l3_write_accesses = l2_write_misses
        l3_write_accesses_source = l2_write_misses_source
        l3_write_accesses_method = "fallback"
    else:
        l3_write_accesses_method = "direct"

    l3_read_misses, l3_read_misses_source = _find_first_stat_with_source(
        root_stats,
        ("l3.ReadReq_misses::total", "l3cache.ReadReq_misses::total", "l3.overallMisses::total"),
    )
    l3_read_misses_method = "direct" if l3_read_misses_source else "default"

    l3_write_misses, l3_write_misses_source = _find_first_stat_with_source(
        root_stats,
        ("l3.WriteReq_misses::total", "l3cache.WriteReq_misses::total"),
    )
    l3_write_misses_method = "direct" if l3_write_misses_source else "default"

    memory_reads, memory_read_sources = _sum_matching_suffixes_with_sources(
        root_stats, ("mem_ctrl.readReqs", "dram.readBursts", "readReqs")
    )
    if memory_reads <= 0:
        memory_reads = l3_read_misses
        memory_read_sources = [l3_read_misses_source]
        memory_reads_method = "fallback"
    else:
        memory_reads_method = "aggregated"

    memory_writes, memory_write_sources = _sum_matching_suffixes_with_sources(
        root_stats, ("mem_ctrl.writeReqs", "dram.writeBursts", "writeReqs")
    )
    if memory_writes <= 0:
        memory_writes = l3_write_misses
        memory_write_sources = [l3_write_misses_source]
        memory_writes_method = "fallback"
    else:
        memory_writes_method = "aggregated"
    memory_accesses = memory_reads + memory_writes

    itlb_accesses, itlb_accesses_source = _find_first_stat_with_source(
        root_stats, ("itlb.overallAccesses::total", "itlb.ReadReq_accesses::total")
    )
    if itlb_accesses <= 0:
        itlb_accesses = total_instructions
        itlb_accesses_source = total_instructions_source
        itlb_accesses_method = "fallback"
    else:
        itlb_accesses_method = "direct"

    itlb_misses, itlb_misses_source = _find_first_stat_with_source(
        root_stats, ("itlb.overallMisses::total", "itlb.ReadReq_misses::total")
    )
    itlb_misses_method = "direct" if itlb_misses_source else "default"

    dtlb_accesses, dtlb_accesses_source = _find_first_stat_with_source(
        root_stats, ("dtlb.overallAccesses::total", "dtlb.ReadReq_accesses::total")
    )
    if dtlb_accesses <= 0:
        dtlb_accesses = load_instructions + store_instructions
        dtlb_accesses_source = "load_instructions + store_instructions"
        dtlb_accesses_method = "fallback"
    else:
        dtlb_accesses_method = "direct"

    dtlb_misses, dtlb_misses_source = _find_first_stat_with_source(
        root_stats, ("dtlb.overallMisses::total", "dtlb.ReadReq_misses::total")
    )
    dtlb_misses_method = "direct" if dtlb_misses_source else "default"

    btb_read_accesses, btb_read_accesses_source = _find_first_stat_with_source(
        root_stats, ("BTBLookups",)
    )
    if btb_read_accesses <= 0:
        btb_read_accesses = branch_instructions
        btb_read_accesses_source = branch_instruction_source
        btb_read_accesses_method = "fallback"
    else:
        btb_read_accesses_method = "direct"
    btb_write_accesses = branch_mispredictions

    noc_total_accesses, noc_total_accesses_sources = _sum_matching_suffixes_with_sources(
        root_stats, ("xbar.pktCount::total",)
    )
    if noc_total_accesses <= 0:
        noc_total_accesses = (
            l2_read_accesses + l2_write_accesses + l3_read_accesses + l3_write_accesses
        )
        noc_total_accesses_sources = [
            "l2_read_accesses",
            "l2_write_accesses",
            "l3_read_accesses",
            "l3_write_accesses",
        ]
        noc_total_accesses_method = "fallback"
    else:
        noc_total_accesses_method = "aggregated"
    noc_duty_cycle = (
        min(1.0, noc_total_accesses / total_cycles) if total_cycles > 0 else 0.0
    )

    remember(
        "mcpat.system.total_cycles",
        total_cycles,
        method=total_cycles_method,
        sources=[total_cycles_source],
    )
    remember(
        "mcpat.system.idle_cycles",
        idle_cycles,
        method="derived",
        sources=["mcpat.system.total_cycles", "mcpat.system.busy_cycles"],
    )
    remember(
        "mcpat.system.busy_cycles",
        busy_cycles,
        method="derived",
        sources=["mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.core.total_instructions",
        total_instructions,
        method=total_instructions_method,
        sources=[total_instructions_source],
    )
    remember(
        "mcpat.core.int_instructions",
        int_instructions,
        method=int_instructions_method,
        sources=[int_instructions_source],
    )
    remember(
        "mcpat.core.fp_instructions",
        fp_instructions,
        method="aggregated",
        sources=[fp_scalar_source, vec_instructions_source],
        note="Scalar FP and vector NEON instructions are combined for McPAT FPU activity.",
    )
    remember(
        "mcpat.core.branch_instructions",
        branch_instructions,
        method=branch_instructions_method,
        sources=[branch_instruction_source],
    )
    remember(
        "mcpat.core.branch_mispredictions",
        branch_mispredictions,
        method=branch_mispred_method,
        sources=[branch_mispred_source],
    )
    remember(
        "mcpat.core.load_instructions",
        load_instructions,
        method=load_instructions_method,
        sources=[load_instructions_source],
    )
    remember(
        "mcpat.core.store_instructions",
        store_instructions,
        method=store_instructions_method,
        sources=[store_instructions_source],
    )
    remember(
        "mcpat.core.committed_instructions",
        committed_instructions,
        method=committed_instructions_method,
        sources=[committed_instructions_source],
    )
    remember(
        "mcpat.core.committed_int_instructions",
        committed_int_instructions,
        method="fallback" if committed_int_instructions == committed_instructions else "direct",
        sources=[int_instructions_source, committed_instructions_source],
    )
    remember(
        "mcpat.core.committed_fp_instructions",
        committed_fp_instructions,
        method="aggregated",
        sources=[fp_scalar_source, vec_instructions_source],
    )
    remember(
        "mcpat.core.pipeline_duty_cycle",
        pipeline_duty_cycle,
        method="derived",
        sources=["mcpat.core.committed_instructions", "mcpat.system.total_cycles", "profile.issue_width"],
    )
    remember(
        "mcpat.core.rob_reads",
        total_ops,
        method=total_ops_method,
        sources=[total_ops_source],
    )
    remember(
        "mcpat.core.rob_writes",
        total_ops,
        method=total_ops_method,
        sources=[total_ops_source],
    )
    remember(
        "mcpat.core.rename_reads",
        int_reg_reads,
        method=int_reg_reads_method,
        sources=[int_reg_reads_source],
    )
    remember(
        "mcpat.core.rename_writes",
        int_reg_writes,
        method=int_reg_writes_method,
        sources=[int_reg_writes_source],
    )
    remember(
        "mcpat.core.fp_rename_reads",
        float_reg_reads,
        method="aggregated" if float_reg_reads > 0 else "default",
        sources=[fp_reg_reads_source, vec_reg_reads_source],
    )
    remember(
        "mcpat.core.fp_rename_writes",
        float_reg_writes,
        method="aggregated" if float_reg_writes > 0 else "default",
        sources=[fp_reg_writes_source, vec_reg_writes_source],
    )
    remember(
        "mcpat.core.inst_window_reads",
        committed_instructions,
        method="fallback",
        sources=[committed_instructions_source],
    )
    remember(
        "mcpat.core.inst_window_writes",
        committed_instructions,
        method="fallback",
        sources=[committed_instructions_source],
    )
    remember(
        "mcpat.core.inst_window_wakeup_accesses",
        committed_instructions * 2.0,
        method="derived",
        sources=["mcpat.core.committed_instructions"],
    )
    remember(
        "mcpat.core.fp_inst_window_reads",
        fp_instructions,
        method="fallback",
        sources=[fp_scalar_source, vec_instructions_source],
    )
    remember(
        "mcpat.core.fp_inst_window_writes",
        fp_instructions,
        method="fallback",
        sources=[fp_scalar_source, vec_instructions_source],
    )
    remember(
        "mcpat.core.fp_inst_window_wakeup_accesses",
        fp_instructions * 2.0,
        method="derived",
        sources=["mcpat.core.fp_instructions"],
    )
    remember(
        "mcpat.core.int_regfile_reads",
        int_reg_reads,
        method=int_reg_reads_method,
        sources=[int_reg_reads_source],
    )
    remember(
        "mcpat.core.float_regfile_reads",
        float_reg_reads,
        method="aggregated" if float_reg_reads > 0 else "default",
        sources=[fp_reg_reads_source, vec_reg_reads_source],
    )
    remember(
        "mcpat.core.int_regfile_writes",
        int_reg_writes,
        method=int_reg_writes_method,
        sources=[int_reg_writes_source],
    )
    remember(
        "mcpat.core.float_regfile_writes",
        float_reg_writes,
        method="aggregated" if float_reg_writes > 0 else "default",
        sources=[fp_reg_writes_source, vec_reg_writes_source],
    )

    function_calls, function_calls_source = _find_first_stat_with_source(
        root_stats, ("commitStats0.functionCalls",)
    )
    remember(
        "mcpat.core.function_calls",
        function_calls,
        method="direct" if function_calls_source else "default",
        sources=[function_calls_source],
    )
    remember(
        "mcpat.core.context_switches",
        0.0,
        method="default",
        sources=[],
    )
    remember(
        "mcpat.core.ialu_accesses",
        ialu_accesses,
        method=ialu_accesses_method,
        sources=[ialu_accesses_source],
    )
    remember(
        "mcpat.core.fpu_accesses",
        fpu_accesses,
        method=fpu_accesses_method,
        sources=fpu_accesses_sources,
    )
    remember(
        "mcpat.core.mul_accesses",
        mul_accesses,
        method=mul_accesses_method,
        sources=mul_sources,
    )
    remember(
        "mcpat.core.cdb_alu_accesses",
        ialu_accesses,
        method=ialu_accesses_method,
        sources=[ialu_accesses_source],
    )
    remember(
        "mcpat.core.cdb_mul_accesses",
        mul_accesses,
        method=mul_accesses_method,
        sources=mul_sources,
    )
    remember(
        "mcpat.core.cdb_fpu_accesses",
        fpu_accesses,
        method=fpu_accesses_method,
        sources=fpu_accesses_sources,
    )
    remember(
        "mcpat.core.ifu_duty_cycle",
        pipeline_duty_cycle,
        method="derived",
        sources=["mcpat.core.pipeline_duty_cycle"],
    )
    remember(
        "mcpat.core.lsu_duty_cycle",
        lsu_duty_cycle,
        method="derived",
        sources=["mcpat.core.load_instructions", "mcpat.core.store_instructions", "mcpat.system.total_cycles", "profile.memory_ports"],
    )
    remember(
        "mcpat.core.mmu_i_duty_cycle",
        pipeline_duty_cycle,
        method="derived",
        sources=["mcpat.core.pipeline_duty_cycle"],
    )
    remember(
        "mcpat.core.mmu_d_duty_cycle",
        lsu_duty_cycle,
        method="derived",
        sources=["mcpat.core.lsu_duty_cycle"],
    )

    alu_duty_cycle = min(1.0, ialu_accesses / total_cycles) if total_cycles > 0 else 0.0
    mul_duty_cycle = min(1.0, mul_accesses / total_cycles) if total_cycles > 0 else 0.0
    fpu_duty_cycle = min(1.0, fpu_accesses / total_cycles) if total_cycles > 0 else 0.0
    remember(
        "mcpat.core.alu_duty_cycle",
        alu_duty_cycle,
        method="derived",
        sources=["mcpat.core.ialu_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.core.mul_duty_cycle",
        mul_duty_cycle,
        method="derived",
        sources=["mcpat.core.mul_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.core.fpu_duty_cycle",
        fpu_duty_cycle,
        method="derived",
        sources=["mcpat.core.fpu_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.core.alu_cdb_duty_cycle",
        alu_duty_cycle,
        method="derived",
        sources=["mcpat.core.alu_duty_cycle"],
    )
    remember(
        "mcpat.core.mul_cdb_duty_cycle",
        mul_duty_cycle,
        method="derived",
        sources=["mcpat.core.mul_duty_cycle"],
    )
    remember(
        "mcpat.core.fpu_cdb_duty_cycle",
        fpu_duty_cycle,
        method="derived",
        sources=["mcpat.core.fpu_duty_cycle"],
    )
    remember(
        "mcpat.tlb.itlb.accesses",
        itlb_accesses,
        method=itlb_accesses_method,
        sources=[itlb_accesses_source],
    )
    remember(
        "mcpat.tlb.itlb.misses",
        itlb_misses,
        method=itlb_misses_method,
        sources=[itlb_misses_source],
    )
    remember(
        "mcpat.tlb.dtlb.accesses",
        dtlb_accesses,
        method=dtlb_accesses_method,
        sources=[dtlb_accesses_source],
    )
    remember(
        "mcpat.tlb.dtlb.misses",
        dtlb_misses,
        method=dtlb_misses_method,
        sources=[dtlb_misses_source],
    )
    remember(
        "mcpat.cache.l1i.read_accesses",
        icache_read_accesses,
        method=icache_read_accesses_method,
        sources=[icache_read_accesses_source],
    )
    remember(
        "mcpat.cache.l1i.read_misses",
        icache_read_misses,
        method=icache_read_misses_method,
        sources=[icache_read_misses_source],
    )
    remember(
        "mcpat.cache.l1d.read_accesses",
        dcache_read_accesses,
        method=dcache_read_accesses_method,
        sources=[dcache_read_accesses_source],
    )
    remember(
        "mcpat.cache.l1d.write_accesses",
        dcache_write_accesses,
        method=dcache_write_accesses_method,
        sources=[dcache_write_accesses_source],
    )
    remember(
        "mcpat.cache.l1d.read_misses",
        dcache_read_misses,
        method=dcache_read_misses_method,
        sources=[dcache_read_misses_source],
    )
    remember(
        "mcpat.cache.l1d.write_misses",
        dcache_write_misses,
        method=dcache_write_misses_method,
        sources=[dcache_write_misses_source],
    )
    remember(
        "mcpat.branch.btb.read_accesses",
        btb_read_accesses,
        method=btb_read_accesses_method,
        sources=[btb_read_accesses_source],
    )
    remember(
        "mcpat.branch.btb.write_accesses",
        btb_write_accesses,
        method="fallback",
        sources=[branch_mispred_source],
    )
    remember(
        "mcpat.directory.l1.read_accesses",
        dcache_read_accesses,
        method=dcache_read_accesses_method,
        sources=[dcache_read_accesses_source],
    )
    remember(
        "mcpat.directory.l1.write_accesses",
        dcache_write_accesses,
        method=dcache_write_accesses_method,
        sources=[dcache_write_accesses_source],
    )
    remember(
        "mcpat.directory.l1.read_misses",
        dcache_read_misses,
        method=dcache_read_misses_method,
        sources=[dcache_read_misses_source],
    )
    remember(
        "mcpat.directory.l1.write_misses",
        dcache_write_misses,
        method=dcache_write_misses_method,
        sources=[dcache_write_misses_source],
    )
    remember(
        "mcpat.directory.l1.conflicts",
        0.0,
        method="default",
        sources=[],
    )
    remember(
        "mcpat.directory.l2.read_accesses",
        l2_read_accesses,
        method=l2_read_accesses_method,
        sources=[l2_read_accesses_source],
    )
    remember(
        "mcpat.directory.l2.write_accesses",
        l2_write_accesses,
        method=l2_write_accesses_method,
        sources=[l2_write_accesses_source],
    )
    remember(
        "mcpat.directory.l2.read_misses",
        l2_read_misses,
        method=l2_read_misses_method,
        sources=[l2_read_misses_source],
    )
    remember(
        "mcpat.directory.l2.write_misses",
        l2_write_misses,
        method=l2_write_misses_method,
        sources=[l2_write_misses_source],
    )
    remember(
        "mcpat.directory.l2.conflicts",
        0.0,
        method="default",
        sources=[],
    )
    remember(
        "mcpat.cache.l2.read_accesses",
        l2_read_accesses,
        method=l2_read_accesses_method,
        sources=[l2_read_accesses_source],
    )
    remember(
        "mcpat.cache.l2.write_accesses",
        l2_write_accesses,
        method=l2_write_accesses_method,
        sources=[l2_write_accesses_source],
    )
    remember(
        "mcpat.cache.l2.read_misses",
        l2_read_misses,
        method=l2_read_misses_method,
        sources=[l2_read_misses_source],
    )
    remember(
        "mcpat.cache.l2.write_misses",
        l2_write_misses,
        method=l2_write_misses_method,
        sources=[l2_write_misses_source],
    )
    remember(
        "mcpat.cache.l2.conflicts",
        0.0,
        method="default",
        sources=[],
    )
    remember(
        "mcpat.cache.l2.duty_cycle",
        min(1.0, (l2_read_accesses + l2_write_accesses) / total_cycles) if total_cycles > 0 else 0.0,
        method="derived",
        sources=["mcpat.cache.l2.read_accesses", "mcpat.cache.l2.write_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.cache.l3.read_accesses",
        l3_read_accesses,
        method=l3_read_accesses_method,
        sources=[l3_read_accesses_source],
    )
    remember(
        "mcpat.cache.l3.write_accesses",
        l3_write_accesses,
        method=l3_write_accesses_method,
        sources=[l3_write_accesses_source],
    )
    remember(
        "mcpat.cache.l3.read_misses",
        l3_read_misses,
        method=l3_read_misses_method,
        sources=[l3_read_misses_source],
    )
    remember(
        "mcpat.cache.l3.write_misses",
        l3_write_misses,
        method=l3_write_misses_method,
        sources=[l3_write_misses_source],
    )
    remember(
        "mcpat.cache.l3.conflicts",
        0.0,
        method="default",
        sources=[],
    )
    remember(
        "mcpat.cache.l3.duty_cycle",
        min(1.0, (l3_read_accesses + l3_write_accesses) / total_cycles) if total_cycles > 0 else 0.0,
        method="derived",
        sources=["mcpat.cache.l3.read_accesses", "mcpat.cache.l3.write_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.noc.total_accesses",
        noc_total_accesses,
        method=noc_total_accesses_method,
        sources=noc_total_accesses_sources,
    )
    remember(
        "mcpat.noc.duty_cycle",
        noc_duty_cycle,
        method="derived",
        sources=["mcpat.noc.total_accesses", "mcpat.system.total_cycles"],
    )
    remember(
        "mcpat.memory.accesses",
        memory_accesses,
        method="derived",
        sources=["mcpat.memory.reads", "mcpat.memory.writes"],
    )
    remember(
        "mcpat.memory.reads",
        memory_reads,
        method=memory_reads_method,
        sources=memory_read_sources,
    )
    remember(
        "mcpat.memory.writes",
        memory_writes,
        method=memory_writes_method,
        sources=memory_write_sources,
    )

    interval_seconds = (
        (total_cycles * float(profile.get("clock_period_ps", 0.0))) / 1_000_000_000_000.0
        if total_cycles > 0
        else 0.0
    )

    hpre_switch_count, hpre_switch_sources = _sum_matching_any_fragments_with_sources(
        root_stats, ("hpre", "rsa", "ecc")
    )
    sec_switch_count, sec_switch_sources = _sum_matching_any_fragments_with_sources(
        root_stats, ("sec", "crypto", "aes", "sha")
    )
    zip_switch_count, zip_switch_sources = _sum_matching_any_fragments_with_sources(
        root_stats, ("zip", "zlib", "gzip", "compress")
    )

    custom_blocks = {
        "hccs": {
            "switch_count": noc_total_accesses,
            "sources": noc_total_accesses_sources,
            "method": "derived",
            "activation_factor": noc_duty_cycle,
            "activation_sources": ["mcpat.noc.duty_cycle"],
            "note": "HCCS activity is approximated from NoC traffic.",
        },
        "hpre": {
            "switch_count": hpre_switch_count,
            "sources": hpre_switch_sources,
            "method": "aggregated" if hpre_switch_sources else "default",
            "activation_factor": min(1.0, hpre_switch_count / total_cycles) if total_cycles > 0 and hpre_switch_count > 0 else 0.0,
            "activation_sources": hpre_switch_sources,
            "note": "HPRE activity defaults to 0 unless gem5 stats expose accelerator events.",
        },
        "sec": {
            "switch_count": sec_switch_count,
            "sources": sec_switch_sources,
            "method": "aggregated" if sec_switch_sources else "default",
            "activation_factor": min(1.0, sec_switch_count / total_cycles) if total_cycles > 0 and sec_switch_count > 0 else 0.0,
            "activation_sources": sec_switch_sources,
            "note": "SEC activity defaults to 0 unless gem5 stats expose accelerator events.",
        },
        "zip": {
            "switch_count": zip_switch_count,
            "sources": zip_switch_sources,
            "method": "aggregated" if zip_switch_sources else "default",
            "activation_factor": min(1.0, zip_switch_count / total_cycles) if total_cycles > 0 and zip_switch_count > 0 else 0.0,
            "activation_sources": zip_switch_sources,
            "note": "ZIP activity defaults to 0 unless gem5 stats expose compression events.",
        },
    }

    for custom_name, custom_info in custom_blocks.items():
        remember(
            f"mcpat.custom.{custom_name}.switch_count",
            custom_info["switch_count"],
            method=custom_info["method"],
            sources=custom_info["sources"],
            note=custom_info["note"],
        )
        remember(
            f"mcpat.custom.{custom_name}.activation_factor",
            custom_info["activation_factor"],
            method="derived" if custom_name == "hccs" else custom_info["method"],
            sources=custom_info["activation_sources"],
            note=custom_info["note"],
        )
        remember(
            f"mcpat.custom.{custom_name}.interval",
            interval_seconds,
            method="derived",
            sources=["mcpat.system.total_cycles", "profile.clock_period_ps"],
        )

    root_stats.update({key: _format_stat(value) for key, value in derived_stats.items()})
    mcpat_model = config.get("mcpat")
    if isinstance(mcpat_model, dict):
        mcpat_model["stats"] = {"derived": derived_metadata}
    return normalized
