"""Helpers for recording gem5-side SDC fault-injection requests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence


@dataclass(frozen=True)
class FaultTargetSpec:
    raw_target: str = ""
    cpu_index: int = 0
    target_kind: str = "none"
    address_space: str = "none"
    register_name: str = ""
    memory_address: Optional[int] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.memory_address is not None:
            payload["memory_address_hex"] = f"0x{self.memory_address:x}"
        return payload


@dataclass(frozen=True)
class FaultRequest:
    fault_model: str = "none"
    fault_target: str = ""
    fault_bit: Optional[int] = None
    fault_tick: Optional[int] = None
    implemented_in_script: bool = False
    target_kind: str = "none"
    address_space: str = "none"
    cpu_index: int = 0
    register_name: str = ""
    memory_address: Optional[int] = None
    binary: str = ""
    binary_args: tuple[str, ...] = ()
    cpu_type: str = "o3"
    num_cores: int = 1
    clk_freq: str = "2.6GHz"

    def is_active(self) -> bool:
        return self.fault_model != "none"

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["binary_args"] = list(self.binary_args)
        if self.memory_address is not None:
            payload["memory_address_hex"] = f"0x{self.memory_address:x}"
        return payload


def parse_fault_target(raw_target: str) -> FaultTargetSpec:
    target = str(raw_target or "").strip()
    if not target:
        return FaultTargetSpec(raw_target=target)

    cpu_index = 0
    remainder = target
    if target.lower().startswith("cpu"):
        if ":" not in target:
            raise ValueError(
                f"Malformed CPU-qualified fault target: {raw_target}. "
                "Expected format cpuN:<target>."
            )
        prefix, remainder = target.split(":", 1)
        cpu_prefix = prefix.strip().lower()
        if not cpu_prefix.startswith("cpu"):
            raise ValueError(f"Malformed CPU-qualified fault target: {raw_target}")
        cpu_suffix = cpu_prefix[3:]
        if not cpu_suffix.isdigit():
            raise ValueError(
                f"Malformed CPU-qualified fault target: {raw_target}. "
                "CPU prefix must be cpuN where N is a decimal core index."
            )
        cpu_index = int(cpu_suffix)
        remainder = remainder.strip()

    lowered = remainder.lower()
    if lowered.startswith("mem:"):
        address_text = remainder.split(":", 1)[1].strip()
        if not address_text:
            raise ValueError(f"Invalid memory fault target: {raw_target}")
        return FaultTargetSpec(
            raw_target=target,
            cpu_index=cpu_index,
            target_kind="memory",
            address_space="guest_virtual",
            memory_address=int(address_text, 0),
        )

    if lowered.startswith(("physmem:", "paddr:")):
        address_text = remainder.split(":", 1)[1].strip()
        if not address_text:
            raise ValueError(f"Invalid physical memory fault target: {raw_target}")
        return FaultTargetSpec(
            raw_target=target,
            cpu_index=cpu_index,
            target_kind="memory",
            address_space="physical",
            memory_address=int(address_text, 0),
        )

    if not remainder:
        raise ValueError(f"Invalid fault target: {raw_target}")

    return FaultTargetSpec(
        raw_target=target,
        cpu_index=cpu_index,
        target_kind="register",
        address_space="register_file",
        register_name=remainder,
    )


def supports_scripted_fault_injection(
    *,
    fault_model: str,
    fault_target: str,
    fault_bit: Optional[int],
    fault_tick: Optional[int],
    num_cores: int,
) -> bool:
    if fault_bit is None or fault_tick is None:
        return False

    target = parse_fault_target(fault_target)
    if target.cpu_index >= num_cores:
        return False

    register_name = target.register_name.strip().lower()
    is_int_register = register_name.startswith("x") or register_name == "sp"
    is_vec_register = register_name.startswith("v") or register_name.startswith("q")

    normalized_model = str(fault_model).strip().lower()
    if normalized_model == "register_bit_flip":
        return (
            target.target_kind == "register"
            and target.address_space == "register_file"
            and is_int_register
            and fault_bit < 64
        )
    if normalized_model == "vector_register_bit_flip":
        return (
            target.target_kind == "register"
            and target.address_space == "register_file"
            and is_vec_register
            and fault_bit < 128
        )
    if normalized_model == "memory_bit_flip":
        return (
            target.target_kind == "memory"
            and target.address_space == "guest_virtual"
            and target.memory_address is not None
            and fault_bit >= 0
        )
    return False


def validate_fault_request(
    *,
    fault_model: str,
    fault_target: str,
) -> FaultTargetSpec:
    target = parse_fault_target(fault_target)
    normalized_model = str(fault_model).strip().lower()

    if normalized_model == "none":
        return target

    if normalized_model in {"register_bit_flip", "vector_register_bit_flip"}:
        if target.target_kind != "register" or target.address_space != "register_file":
            raise ValueError(
                f"{fault_model} requires a register fault target such as x0 or v0; "
                f"got {fault_target!r}."
            )
        return target

    if normalized_model == "memory_bit_flip":
        if target.target_kind != "memory":
            raise ValueError(
                f"{fault_model} requires a memory fault target such as mem:0x1000; "
                f"got {fault_target!r}."
            )
        if target.address_space != "guest_virtual":
            raise ValueError(
                f"{fault_model} currently requires guest virtual addresses using mem:0x...; "
                f"got {fault_target!r}."
            )
        return target

    return target


def build_fault_request(
    *,
    fault_model: str,
    fault_target: str,
    fault_bit: Optional[int],
    fault_tick: Optional[int],
    implemented_in_script: bool = False,
    binary: Path,
    binary_args: Sequence[str],
    cpu_type: str,
    num_cores: int,
    clk_freq: str,
) -> FaultRequest:
    target = validate_fault_request(
        fault_model=fault_model,
        fault_target=fault_target,
    )
    return FaultRequest(
        fault_model=fault_model,
        fault_target=fault_target,
        fault_bit=fault_bit,
        fault_tick=fault_tick,
        implemented_in_script=implemented_in_script,
        target_kind=target.target_kind,
        address_space=target.address_space,
        cpu_index=target.cpu_index,
        register_name=target.register_name,
        memory_address=target.memory_address,
        binary=str(binary.resolve()),
        binary_args=tuple(binary_args),
        cpu_type=cpu_type,
        num_cores=num_cores,
        clk_freq=clk_freq,
    )


def write_fault_request(request: FaultRequest, manifest_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(request.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path
