#!/usr/bin/env python3
"""Real end-to-end Phase 2 validation using source-built QEMU system + gem5 + McPAT."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .differential import (
    CommandResult,
    build_fault_args,
    build_fault_request_summary,
)
from .generation import (
    DEFAULT_POLICY,
    DEFAULT_TARGET,
    PROFILE_SIM_SAFE,
    generate_batch,
    generate_testcase,
)
from .materialize import SDC_MEMORY_SIZE, _asm_block, _benchmark_body_lines
from .power_backends.mcpat_backend import McPATBackend
from .tooling import (
    DEFAULT_GEM5_BAREMETAL_CONFIG,
    DEFAULT_GEM5_BINARY,
    DEFAULT_MCPAT_BINARY,
    resolve_local_tools,
)
from .vault import SDCVault
from .vault import VaultEntry


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "artifacts" / "sdc_vault.sqlite3"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "phase2-validation"
DEFAULT_BOOT_ASM = REPO_ROOT / "qemu" / "tests" / "tcg" / "aarch64" / "system" / "boot.S"
DIGEST_PATTERN = re.compile(r"SDC_(?:DIGEST|HASH)=([0-9a-fA-F]+)")
DEFAULT_SAFE_VALIDATION_INSTRUCTIONS = (
    "MOVZ_X_V0",
    "MOVZ_X_V0",
    "MOVZ_X_V0",
    "MOVZ_X_V0",
)
SAFE_BASELINE_ASM = "\n".join(
    [
        "mov x0, #1",
        "mov x1, #2",
        "add x2, x0, x1",
        "eor x3, x2, x1",
        "subs x4, x3, x0",
        "nop",
    ]
)


def _resolve_compiler() -> str:
    resolved = resolve_local_tools(compiler=None).compiler
    if resolved:
        return resolved
    raise FileNotFoundError("No usable AArch64 cross compiler found.")


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw_value = row.get("metadata_json", "{}")
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(str(raw_value))


def _jsonable_command(result: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    return {
        "args": result.args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def extract_digest(text: str) -> Optional[str]:
    match = DIGEST_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).lower()


def _normalize_asm_line(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped:
        return []
    if stripped.startswith("//"):
        return []
    if stripped.lower().startswith(".arch") or stripped.lower().startswith(".text"):
        return []

    mnemonic = stripped.split()[0].upper()
    parts = [part.strip() for part in stripped.split(",")]

    if mnemonic in {"MOVZ", "MOVK", "MOVN"} and len(parts) >= 3:
        first = parts[0].split()
        opcode = first[0].lower()
        reg = first[-1]
        imm = parts[1]
        shift = parts[2]
        return [f"{opcode} {reg}, #{imm}, lsl #{int(shift) * 16}"]

    if mnemonic in {"FMLA", "FMLS"}:
        dest_src = [part.strip() for part in stripped.split(",")]
        if len(dest_src) >= 3:
            head = dest_src[0].split()
            dest = head[-1]
            operands = [dest] + dest_src[1:] + [dest]
            converted = "FMADD " + ", ".join(
                re.sub(r"\bv(\d+)\b", lambda match: f"d{match.group(1)}", operand)
                for operand in operands
            )
            return [converted]

    if mnemonic in {"FMSUB"}:
        converted = re.sub(r"\bv(\d+)\b", lambda match: f"d{match.group(1)}", stripped)
        return [converted]

    return [stripped.lower()]


def render_semihost_validation_source(asm_content: str, testcase_key: str) -> str:
    asm_lines = [line.rstrip() for line in asm_content.splitlines() if line.strip()]
    if not asm_lines:
        asm_lines = ["nop"]
    normalized_lines: list[str] = []
    for line in asm_lines:
        normalized_lines.extend(_normalize_asm_line(line))
    if not normalized_lines:
        normalized_lines = ["nop"]
    return "\n".join(
        [
            f"/* Phase2 validation source for {testcase_key} */",
            "typedef unsigned long long uint64_t;",
            "typedef unsigned int uint32_t;",
            "typedef unsigned long size_t;",
            "typedef unsigned char uint8_t;",
            "",
            "extern void __sys_outc(char c);",
            "",
            "static uint64_t sdc_gprs[31] = {0};",
            "static uint64_t sdc_nzcv = 0;",
            "static uint8_t sdc_simd[8 * 16] = {0};",
            f"static uint8_t sdc_memory[{SDC_MEMORY_SIZE}] = {{0}};",
            "",
            "static inline uint64_t sdc_rotl64(uint64_t value, unsigned shift)",
            "{",
            "    return (value << shift) | (value >> (64 - shift));",
            "}",
            "",
            "static inline uint64_t sdc_mix_u64(uint64_t state, uint64_t value)",
            "{",
            "    state ^= value + 0x9e3779b97f4a7c15ULL + (state << 6) + (state >> 2);",
            "    return sdc_rotl64(state, 17);",
            "}",
            "",
            "static inline uint64_t sdc_mix_bytes(uint64_t state, const uint8_t *buffer, size_t size)",
            "{",
            "    for (size_t index = 0; index < size; ++index) {",
            "        state ^= (uint64_t)buffer[index] << ((index & 7U) * 8U);",
            "        state *= 0x100000001b3ULL;",
            "        state = sdc_rotl64(state, 9);",
            "    }",
            "    return state;",
            "}",
            "",
            "static void sdc_write_str(const char *text)",
            "{",
            "    while (*text) {",
            "        __sys_outc(*text++);",
            "    }",
            "}",
            "",
            "static void sdc_prepare_memory(void)",
            "{",
            "    for (size_t index = 0; index < 31; ++index) {",
            "        sdc_gprs[index] = 0ULL;",
            "    }",
            "    sdc_nzcv = 0ULL;",
            "    for (size_t index = 0; index < sizeof(sdc_simd); ++index) {",
            "        sdc_simd[index] = 0U;",
            "    }",
            "    for (size_t index = 0; index < sizeof(sdc_memory); ++index) {",
            "        sdc_memory[index] = (uint8_t)(((index * 131U) + 17U) & 0xffU);",
            "    }",
            "}",
            "",
            "static void sdc_write_hex64(uint64_t value)",
            "{",
            "    for (int shift = 60; shift >= 0; shift -= 4) {",
            "        uint8_t nibble = (value >> shift) & 0xFU;",
            "        char c = (nibble < 10U) ? (char)('0' + nibble) : (char)('a' + nibble - 10U);",
            "        __sys_outc(c);",
            "    }",
            "}",
            "",
            "extern void sdc_benchmark_body(void);",
            "__asm__(",
            _asm_block(_benchmark_body_lines("\n".join(normalized_lines))),
            ");",
            "",
            "int main(void)",
            "{",
            "    uint64_t digest = 0xcbf29ce484222325ULL;",
            "    sdc_prepare_memory();",
            "    sdc_benchmark_body();",
            "    for (size_t i = 0; i < 31; ++i) {",
            "        digest = sdc_mix_u64(digest, sdc_gprs[i]);",
            "    }",
            "    digest = sdc_mix_u64(digest, sdc_nzcv);",
            "    digest = sdc_mix_bytes(digest, sdc_simd, sizeof(sdc_simd));",
            "    digest = sdc_mix_bytes(digest, sdc_memory, sizeof(sdc_memory));",
            '    sdc_write_str("SDC_DIGEST=");',
            "    sdc_write_hex64(digest);",
            "    __sys_outc('\\n');",
            "    return 0;",
            "}",
            "",
        ]
    )


def write_shared_kernel_ld(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "ENTRY(__start)",
                "MEMORY {",
                "    TXT (rx) : ORIGIN = 1 << 30, LENGTH = 2M",
                "    DAT (rw) : ORIGIN = (1 << 30) + 2M, LENGTH = 2M",
                "    TAG (rw) : ORIGIN = (1 << 30) + 4M, LENGTH = 2M",
                "}",
                "SECTIONS {",
                "    .text : { *(.text) *(.rodata) } >TXT",
                "    .data : { *(.data) *(.bss) } >DAT",
                "    .tag : { mte_page = .; } >TAG",
                "    /DISCARD/ : { *(.ARM.attributes) }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def build_semihost_validation_elf(
    *,
    asm_content: str,
    testcase_key: str,
    output_root: Path,
    compiler: str,
) -> Dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    source_path = output_root / f"{testcase_key}.c"
    boot_obj = output_root / "boot.o"
    linker_script = output_root / "kernel.ld"
    elf_path = output_root / f"{testcase_key}.elf"

    source_path.write_text(
        render_semihost_validation_source(asm_content, testcase_key),
        encoding="utf-8",
    )
    write_shared_kernel_ld(linker_script)

    subprocess.run(
        [
            compiler,
            "-c",
            "-nostdlib",
            "-O0",
            "-ggdb",
            str(DEFAULT_BOOT_ASM),
            "-o",
            str(boot_obj),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            compiler,
            "-nostdlib",
            "-static",
            "-O0",
            "-ggdb",
            str(source_path),
            str(boot_obj),
            f"-Wl,-T,{linker_script}",
            "-lgcc",
            "-o",
            str(elf_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "source_path": source_path.resolve(),
        "boot_obj": boot_obj.resolve(),
        "linker_script": linker_script.resolve(),
        "elf_path": elf_path.resolve(),
    }


def run_qemu_system_golden(
    *,
    qemu_binary: Path,
    elf_path: Path,
    timeout: int,
) -> Dict[str, Any]:
    cmd = [
        str(qemu_binary.resolve()),
        "-M",
        "virt",
        "-cpu",
        "max",
        "-m",
        "4096",
        "-display",
        "none",
        "-serial",
        "none",
        "-chardev",
        "stdio,mux=on,id=stdio0",
        "-semihosting-config",
        "enable=on,chardev=stdio0",
        "-mon",
        "chardev=stdio0,mode=readline",
        "-kernel",
        str(elf_path.resolve()),
    ]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    digest = extract_digest(result.stdout + "\n" + result.stderr)
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "golden_digest": digest,
    }


def run_gem5_semihost_validation(
    *,
    gem5_binary: Path,
    gem5_config: Path,
    elf_path: Path,
    output_root: Path,
    fault_model: str = "none",
    fault_target: str = "",
    fault_bit: Optional[int] = None,
    fault_tick: Optional[int] = None,
    timeout: int,
) -> Dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    semi_stdout = output_root / "semi.stdout"
    semi_stderr = output_root / "semi.stderr"
    cmd = [
        str(gem5_binary.resolve()),
        "-d",
        str(output_root.resolve()),
        str(gem5_config.resolve()),
    ]
    if gem5_config.name == "sdc_kunpeng920_se.py":
        cmd.extend(
            [
                str(elf_path.resolve()),
                "--stdout-file",
                str(semi_stdout.resolve()),
                "--stderr-file",
                str(semi_stderr.resolve()),
                "--cpu-type",
                "atomic",
            ]
        )
    else:
        cmd.extend(
            [
                "--kernel",
                str(elf_path.resolve()),
                "--semi-enable",
                "--semi-stdout",
                str(semi_stdout.resolve()),
                "--semi-stderr",
                str(semi_stderr.resolve()),
                "--cpu",
                "atomic",
            ]
        )

    cmd.extend(
        build_fault_args(
            fault_model=fault_model,
            fault_target=fault_target,
            fault_bit=fault_bit,
            fault_tick=fault_tick,
        )
    )
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout_text = result.stdout
    stderr_text = result.stderr
    if semi_stdout.exists():
        stdout_text += "\n" + semi_stdout.read_text(encoding="utf-8", errors="replace")
    if semi_stderr.exists():
        stderr_text += "\n" + semi_stderr.read_text(encoding="utf-8", errors="replace")
    digest = extract_digest(stdout_text + "\n" + stderr_text)
    command_result = CommandResult(
        command=[str(part) for part in cmd],
        returncode=result.returncode,
        stdout=stdout_text,
        stderr=stderr_text,
    )
    fault_request = build_fault_request_summary(
        gem5_outdir=output_root,
        gem5_result=command_result,
        fault_model=str(fault_model),
        fault_target=str(fault_target),
        fault_bit=fault_bit,
        fault_tick=fault_tick,
    )
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "gem5_digest": digest,
        "semi_stdout": str(semi_stdout.resolve()),
        "semi_stderr": str(semi_stderr.resolve()),
        "fault_request": fault_request,
        "implemented_in_script": bool(fault_request.get("implemented_in_script", False)),
        "injection_observed": bool(fault_request.get("injection_observed", False)),
        "fault_execution_plane": str(fault_request.get("execution_plane", "")),
    }


@dataclass(frozen=True)
class Phase2ValidationResult:
    testcase_key: str
    profile_name: str
    requested_profile_name: str
    compiler: str
    qemu_binary: str
    gem5_binary: str
    mcpat_binary: str
    source_path: str
    elf_path: str
    qemu_golden_digest: Optional[str]
    gem5_digest: Optional[str]
    qemu_returncode: int
    gem5_returncode: int
    mcpat_power_total: Optional[float]
    status: str
    report_path: str


def _select_validation_candidate(
    *,
    db_path: Path,
    generate_count: int,
    output_root: Path,
    profile_name: str,
    instruction_names: Optional[list[str]] = None,
    candidate_kind: str = "baseline",
) -> Mapping[str, Any]:
    if candidate_kind == "baseline":
        testcase_key = "phase2-safe-baseline"
        entry = VaultEntry(
            testcase_key=testcase_key,
            asm_content=SAFE_BASELINE_ASM,
            target_name=DEFAULT_TARGET,
            policy_name=DEFAULT_POLICY,
            ace_score=0.1,
            ibr_score=0.1,
            memory_pressure_score=0.0,
            risk_score=0.1,
            status="STATIC_DONE",
            metadata={
                "profile_name": profile_name,
                "requested_profile_name": profile_name,
                "effective_profile_name": profile_name,
                "phase2_validation": {
                    "sample_kind": "safe_baseline_case",
                },
            },
        )
        with SDCVault(db_path) as vault:
            vault.upsert_testcase(entry)
            row = vault.get_testcase(testcase_key)
            if row is None:
                raise RuntimeError("Failed to persist safe baseline testcase.")
            return dict(row)

    if generate_count > 0:
        testcase_keys = []
        with SDCVault(db_path) as vault:
            for index in range(generate_count):
                generated = generate_testcase(
                    {
                        "target": DEFAULT_TARGET,
                        "policy": DEFAULT_POLICY,
                        "profile_name": profile_name,
                        "wrapper": "Arm64AsmWrapper",
                        "sequence_length": 4,
                        "benchmark_size": 16,
                        "dependency_distance": 1,
                        "memory_stream_stride": 8192,
                        "strict_validation": False,
                        "seed": 13 + index,
                        "output_dir": str(output_root / "generated"),
                        "instruction_names": instruction_names or list(DEFAULT_SAFE_VALIDATION_INSTRUCTIONS),
                        "metadata_extra": {
                            "phase2_validation": {
                                "sample_kind": "safe_baseline_case",
                            }
                        },
                    }
                )
                vault.upsert_testcase(generated["entry"])
                testcase_keys.append(generated["entry"].testcase_key)
                vault.mark_status(generated["entry"].testcase_key, "STATIC_DONE")
        with SDCVault(db_path) as vault:
            if testcase_keys:
                row = vault.get_testcase(str(testcase_keys[0]))
                if row is not None:
                    return dict(row)
    with SDCVault(db_path) as vault:
        candidates = vault.fetch_top_k_risky(1, statuses=("STATIC_DONE", "PENDING", "GOLDEN_READY"))
        if not candidates:
            raise RuntimeError("No candidate testcase available for Phase 2 validation.")
        return dict(candidates[0])


def run_phase2_validation(
    *,
    db_path: Path = DEFAULT_DB,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    generate_count: int = 1,
    profile_name: str = PROFILE_SIM_SAFE,
    instruction_names: Optional[list[str]] = None,
    candidate_kind: str = "baseline",
    compiler: Optional[str] = None,
    qemu_binary: str | Path = "qemu-system-aarch64",
    gem5_binary: Path = DEFAULT_GEM5_BINARY,
    gem5_config: Path = DEFAULT_GEM5_BAREMETAL_CONFIG,
    mcpat_binary: Path = DEFAULT_MCPAT_BINARY,
    skip_gem5: bool = False,
    skip_mcpat: bool = False,
    timeout: int = 30,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_tools = resolve_local_tools(
        compiler=compiler,
        qemu_system_binary=qemu_binary,
        gem5_binary=gem5_binary,
        gem5_config=gem5_config,
        mcpat_binary=mcpat_binary,
    )
    compiler = resolved_tools.compiler or _resolve_compiler()
    qemu_binary = Path(resolved_tools.qemu_system_binary or qemu_binary).resolve()
    gem5_binary = Path(resolved_tools.gem5_binary or gem5_binary).resolve()
    gem5_config = Path(resolved_tools.gem5_config or gem5_config).resolve()
    mcpat_binary = Path(resolved_tools.mcpat_binary or mcpat_binary).resolve()

    candidate = _select_validation_candidate(
        db_path=db_path,
        generate_count=generate_count,
        output_root=output_root,
        profile_name=profile_name,
        instruction_names=instruction_names,
        candidate_kind=candidate_kind,
    )
    testcase_key = str(candidate["testcase_key"])
    metadata = _decode_metadata(candidate)
    build_dir = output_root / testcase_key
    build_dir.mkdir(parents=True, exist_ok=True)

    build_artifacts = build_semihost_validation_elf(
        asm_content=str(candidate["asm_content"]),
        testcase_key=testcase_key,
        output_root=build_dir,
        compiler=compiler,
    )
    qemu_result = run_qemu_system_golden(
        qemu_binary=qemu_binary,
        elf_path=build_artifacts["elf_path"],
        timeout=timeout,
    )
    gem5_outdir = build_dir / "gem5"
    if skip_gem5:
        gem5_result = {
            "command": [],
            "returncode": 0,
            "stdout": "Skipped gem5; qemu-only mode.",
            "stderr": "",
            "gem5_digest": qemu_result["golden_digest"],
            "semi_stdout": str((gem5_outdir / "semi.stdout").resolve()),
            "semi_stderr": str((gem5_outdir / "semi.stderr").resolve()),
            "fault_request": {"fault_model": "none", "execution_plane": "skipped_gem5"},
            "implemented_in_script": False,
            "injection_observed": False,
            "fault_execution_plane": "skipped_gem5",
        }
        mcpat_result = None
        matched = qemu_result["returncode"] == 0 and qemu_result["golden_digest"] is not None
        status = "GOLDEN_READY" if matched else "FAILED"
    else:
        gem5_result = run_gem5_semihost_validation(
            gem5_binary=gem5_binary,
            gem5_config=gem5_config,
            elf_path=build_artifacts["elf_path"],
            output_root=gem5_outdir,
            fault_model="none",
            fault_target="",
            fault_bit=None,
            fault_tick=None,
            timeout=timeout,
        )
        mcpat_result = None
        if not skip_mcpat:
            mcpat_result = McPATBackend(
                template_profile="arm64-kunpeng920",
                mcpat_binary=mcpat_binary,
            ).run(gem5_outdir)
            mcpat_result = _json_safe(mcpat_result)

        matched = (
            qemu_result["returncode"] == 0
            and gem5_result["returncode"] == 0
            and qemu_result["golden_digest"] is not None
            and qemu_result["golden_digest"] == gem5_result["gem5_digest"]
            and (
                skip_mcpat
                or (
                    isinstance(mcpat_result, dict)
                    and mcpat_result.get("power_total") is not None
                )
            )
        )
        status = "INNER_READY" if matched else "FAILED"

    updated_metadata = {
        **metadata,
        "source_path": str(build_artifacts["source_path"]),
        "golden_digest": qemu_result["golden_digest"],
        "mcpat": mcpat_result,
        "phase2_validation": {
            "compiler": compiler,
            "qemu_binary": str(qemu_binary),
            "gem5_binary": str(gem5_binary),
            "mcpat_binary": str(mcpat_binary),
            "source_path": str(build_artifacts["source_path"]),
            "elf_path": str(build_artifacts["elf_path"]),
            "boot_obj": str(build_artifacts["boot_obj"]),
            "linker_script": str(build_artifacts["linker_script"]),
            "qemu": qemu_result,
            "gem5": gem5_result,
            "matched": matched,
            "skip_gem5": skip_gem5,
            "skip_mcpat": bool(skip_mcpat or skip_gem5),
        },
        "inner_loop": {
            "inner_status": status,
            "artifact_dir": str(build_dir.resolve()),
            "gem5_outdir": str(gem5_outdir.resolve()),
            "source_path": str(build_artifacts["source_path"]),
            "elf_path": str(build_artifacts["elf_path"]),
            "golden_digest": qemu_result["golden_digest"],
            "gem5_digest": gem5_result["gem5_digest"],
            "power_total": mcpat_result.get("power_total") if isinstance(mcpat_result, dict) else None,
            "source_cache_hit": False,
            "elf_cache_hit": False,
            "golden_cache_hit": False,
        },
        "execution": {
            "compile": {"status": "ok", "returncode": 0},
            "qemu": {
                "status": "ok" if qemu_result["returncode"] == 0 else "failed",
                "returncode": qemu_result["returncode"],
            },
            "gem5": {
                "status": "ok" if gem5_result["returncode"] == 0 else "failed",
                "returncode": gem5_result["returncode"],
            },
        },
        "fault_request": {},
    }
    with SDCVault(db_path) as vault:
        vault.update_execution_result(
            testcase_key,
            qemu_golden_hash=qemu_result["golden_digest"],
            mcpat_power=(
                float(mcpat_result["power_total"])
                if isinstance(mcpat_result, dict) and mcpat_result.get("power_total") is not None
                else None
            ),
            status=status,
            metadata=updated_metadata,
        )

    report = Phase2ValidationResult(
        testcase_key=testcase_key,
        profile_name=str(metadata.get("profile_name", PROFILE_SIM_SAFE)),
        requested_profile_name=str(metadata.get("requested_profile_name", metadata.get("profile_name", PROFILE_SIM_SAFE))),
        compiler=compiler,
        qemu_binary=str(qemu_binary),
        gem5_binary=str(gem5_binary),
        mcpat_binary=str(mcpat_binary),
        source_path=str(build_artifacts["source_path"]),
        elf_path=str(build_artifacts["elf_path"]),
        qemu_golden_digest=qemu_result["golden_digest"],
        gem5_digest=gem5_result["gem5_digest"],
        qemu_returncode=int(qemu_result["returncode"]),
        gem5_returncode=int(gem5_result["returncode"]),
        mcpat_power_total=(
            float(mcpat_result["power_total"])
            if isinstance(mcpat_result, dict) and mcpat_result.get("power_total") is not None
            else None
        ),
        status=status,
        report_path=str((build_dir / "phase2-validation.json").resolve()),
    )
    report_payload = {
        **asdict(report),
        "qemu": qemu_result,
        "gem5": gem5_result,
        "mcpat": (
            {
                key: _json_safe(value)
                for key, value in mcpat_result.items()
            }
            if isinstance(mcpat_result, dict)
            else None
        ),
    }
    report_path = Path(report.report_path)
    report_path.write_text(
        json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real Phase 2 end-to-end validation with source-built QEMU system, gem5, and McPAT."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--generate-count", type=int, default=1)
    parser.add_argument("--profile", default=PROFILE_SIM_SAFE)
    parser.add_argument(
        "--candidate-kind",
        choices=["baseline", "generated"],
        default="baseline",
        help="Use a known-safe baseline testcase or a generated testcase.",
    )
    parser.add_argument(
        "--instruction-name",
        action="append",
        default=[],
        help="Optional instruction names for deterministic validation generation. Repeat as needed.",
    )
    parser.add_argument("--compiler", default=None)
    parser.add_argument("--qemu-binary", default="qemu-system-aarch64")
    parser.add_argument("--gem5-binary", type=Path, default=DEFAULT_GEM5_BINARY)
    parser.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_BAREMETAL_CONFIG)
    parser.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    parser.add_argument("--skip-gem5", action="store_true")
    parser.add_argument("--skip-mcpat", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_phase2_validation(
        db_path=args.db,
        output_root=args.output_root,
        generate_count=args.generate_count,
        profile_name=args.profile,
        instruction_names=args.instruction_name or None,
        candidate_kind=args.candidate_kind,
        compiler=args.compiler,
        qemu_binary=args.qemu_binary,
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        mcpat_binary=args.mcpat_binary,
        skip_gem5=args.skip_gem5,
        skip_mcpat=args.skip_mcpat,
        timeout=args.timeout,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] in {"INNER_READY", "GOLDEN_READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
