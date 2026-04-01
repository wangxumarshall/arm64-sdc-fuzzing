#!/usr/bin/env python3
"""Power-analysis pipeline: vault → materialization → gem5 SE → McPAT → vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_VAULT = REPO_ROOT / "artifacts" / "sdc_vault.sqlite3"
DEFAULT_GEM5_BINARY = REPO_ROOT / "gem5" / "build" / "ARM" / "gem5.opt"
DEFAULT_GEM5_CONFIG = (
    REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "sdc_baremetal_se.py"
)
DEFAULT_MCPAT_BINARY = REPO_ROOT / "mcpat" / "mcpat" / "mcpat"
DEFAULT_MATERIALIZED_ROOT = REPO_ROOT / "artifacts" / "materialized"
DIGEST_RE = re.compile(r"SDC_DIGEST=([0-9a-fA-F]+)")

# Path to the aarch64 bare-metal cross-compiler
_AARCH64_GCC_CANDIDATES = [
    "/opt/homebrew/bin/aarch64-elf-gcc",
    "/usr/local/bin/aarch64-elf-gcc",
    "aarch64-elf-gcc",
]


def _find_aarch64_gcc() -> str:
    for path in _AARCH64_GCC_CANDIDATES:
        if Path(path).is_file() or shutil.which(path):
            return path
    return "aarch64-elf-gcc"


def _escape_c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _asm_block(lines) -> str:
    return "\n".join(f'"{_escape_c_string(line)}\\n"' for line in lines if line.strip())


# Inline version of render_materialized_source (avoids import of sdc_materialize
# to keep the file self-contained and avoid path issues).
def render_materialized_source(asm_content: str, testcase_key: str) -> str:
    asm_lines = [line.rstrip() for line in asm_content.splitlines() if line.strip()]
    if not asm_lines:
        asm_lines = ["nop"]

    benchmark_body = [
        ".text", ".align 4",
        ".global sdc_benchmark_body", ".type sdc_benchmark_body, %function",
        "sdc_benchmark_body:",
        "adr x16, sdc_gprs",
    ]
    # Clear all GPRs
    for r in range(31):
        benchmark_body.append(f"mov x{r}, #0")
    # Clear SIMD
    for v in range(8):
        benchmark_body.append(f"movi v{v}.8b, #0")

    # Fix asm for bare-metal assembler compatibility:
    # 1. FMADD/FMLA on vector regs (vN) → scalar FP regs (dN) with .d lane
    # 2. LDP/STP with unscaled imm → scaled imm (must be multiple of 8)
    import re
    def _fix_asm(line):
        s = line.strip()
        if not s:
            return line
        mn = s.split()[0].upper()
        # FMLA/FMLS 3-operand → FMADD 4-operand with self-accumulation
        if mn in ("FMLA", "FMLS"):
            parts = [p.strip() for p in s.split(",")]
            if len(parts) >= 3:
                # parts[0] is "FMLA d14" - extract register "d14"
                first_part_parts = parts[0].split()
                dest_reg = first_part_parts[-1] if first_part_parts else ""
                # Replace FMLA/FMLS mnemonic with just the register in first part
                parts[0] = dest_reg
                parts.append(dest_reg)  # Use dest reg as 4th operand for FMADD
            # Replace vN with dN and FMLA/FMLS with FMADD
            converted = "FMADD " + ", ".join(
                re.sub(r'\b(v\d+)\b', lambda m: "d" + m.group(1)[1:], p)
                for p in parts
            )
            return converted
        elif mn in ("FMADD", "FMSUB", "FNMADD", "FNMSUB", "FMUL",
                    "FADD", "FSUB"):
            s = re.sub(r'\b(v\d+)\b', lambda m: "d" + m.group(1)[1:], s)
        # LDP/STP: replace with two LDR/STR using scaled (multiple-of-8) immediates
        elif mn in ("LDP", "STP"):
            # Parse by comma: "LDP x28, x20, [x21, 0x28]"
            # parts = ["LDP x28", "x20", "[x21", "0x28]"]
            parts = [p.strip() for p in s.split(",")]
            if len(parts) >= 3:
                # reg1: split first part on whitespace, take 2nd token (after mnemonic)
                reg1_parts = parts[0].split()
                reg1 = reg1_parts[-1].rstrip(",") if reg1_parts else ""
                # reg2: second part (text between first and last comma)
                reg2 = parts[1].rstrip(",")
                # base_reg and offset from last part (inside brackets)
                last_mem = parts[-1].strip()  # "0x28]" or "-0xb]"
                if last_mem.endswith("]"):
                    last_mem = last_mem[:-1]  # "0x28" or "-0xb"
                # base_reg: part[-2] inside brackets (e.g. "[x21, 0x28]" -> parts[-2]="[x21")
                if len(parts) >= 2:
                    base_mem = parts[-2].rstrip(",")
                    if base_mem.startswith("["):
                        base_mem = base_mem[1:]  # strip leading '['
                    offset_str = last_mem.strip()
                    if offset_str.endswith("]"):
                        offset_str = offset_str[:-1]  # strip trailing ']'
                    try:
                        neg = offset_str.startswith("-")
                        if neg:
                            offset_str = offset_str[1:]
                        imm_val = int(offset_str, 16) if (
                            offset_str.startswith("0x") or offset_str.startswith("0X")
                        ) else int(offset_str, 0)
                        if neg:
                            imm_val = -imm_val
                        # Always use two LDR/STR with scaled (multiple-of-8) immediates
                        # GNU as does not accept LDP/STP with non-8-multiple scaled immediates
                        scaled = (imm_val // 16) * 8
                        if mn == "LDP":
                            s = (f"ldr {reg1}, [{base_mem}, #{scaled}]\n"
                                 f"        ldr {reg2}, [{base_mem}, #{scaled + 8}]")
                        else:
                            s = (f"str {reg1}, [{base_mem}, #{scaled}]\n"
                                 f"        str {reg2}, [{base_mem}, #{scaled + 8}]")
                    except ValueError:
                        pass
        elif mn in ("CASAL", "CASA", "CASL"):
            return ["dmb ish", "dmb ish"]
        return s

    for asm_line in asm_lines:
        result = _fix_asm(asm_line)
        if isinstance(result, list):
            benchmark_body.extend(result)
        elif isinstance(result, str) and "\n" in result:
            benchmark_body.extend(result.splitlines())
        else:
            benchmark_body.append(result)
    for i in range(31):
        benchmark_body.append(f"str x{i}, [x16, #{i * 8}]")
    benchmark_body.extend([
        "adr x16, sdc_nzcv", "mrs x17, nzcv", "str x17, [x16]",
        "adr x16, sdc_simd",
    ])
    for v in range(8):
        benchmark_body.append(f"str q{v}, [x16, #{v * 16}]")
    # Infinite loop instead of ret to avoid faulting on uninitialized LR
    benchmark_body.append("b .")

    return "\n".join([
        "/* Materialized (bare-metal, no stdlib): " + testcase_key + " */",
        "typedef unsigned long      uint64_t;",
        "typedef unsigned int       uint32_t;",
        "typedef unsigned short     uint16_t;",
        "typedef unsigned char      uint8_t;",
        "typedef unsigned long     size_t;",
        "typedef long              int64_t;",
        "",
        "static uint64_t sdc_gprs[31] __attribute__((section(\".data\"))) = {0};",
        "static uint64_t sdc_nzcv __attribute__((section(\".data\"))) = 0;",
        "static uint8_t sdc_simd[8 * 16] __attribute__((section(\".data\"))) = {0};",
        "static uint8_t sdc_memory[256] __attribute__((section(\".data\"))) = {0};",
        "",
        "/* Forward declare m5ops so we can call them */",
        "void _m5_exit(uint64_t code) __attribute__((noreturn));",
        "__asm__(\".global _m5_exit\\n_m5_exit:\\n    hlt #0\\n\");",
        "",
        "void printf_hex(uint64_t v) {",
        "    char buf[17];",
        "    for (int i = 0; i < 16; i++) {",
        "        int nibble = (v >> ((15 - i) * 4)) & 0xF;",
        "        buf[i] = nibble < 10 ? ('0' + nibble) : ('a' + nibble - 10);",
        "    }",
        "    buf[16] = 0;",
        "    for (char *p = buf; *p; p++) {",
        "        volatile char *mmio = (volatile char *)(0x10000000 + (*p & 0xFF));",
        "        (void)*mmio;",
        "    }",
        "}",
        "",
        "/* Stack pointer - must be aligned to 16 bytes for AAPCS64 */",
        "static char sdc_stack[8192] __attribute__((aligned(16)));",
        "extern char __StackTop;",
        "extern char __StackLimit;",
        "",
        "static inline uint64_t sdc_rotl64(uint64_t v, unsigned s){",
        "    return (v << s) | (v >> (64 - s));",
        "}",
        "static inline uint64_t sdc_mix_u64(uint64_t s, uint64_t v){",
        "    s ^= v + 0x9e3779b97f4a7c15ULL + (s << 6) + (s >> 2);",
        "    return sdc_rotl64(s, 17);",
        "}",
        "static inline uint64_t sdc_mix_bytes(uint64_t s,",
        "    const uint8_t *buf, size_t n){",
        "    for (size_t i = 0; i < n; ++i){",
        "        s ^= (uint64_t)buf[i] << ((i & 7U) * 8U);",
        "        s *= 0x100000001b3ULL;",
        "        s = sdc_rotl64(s, 9);",
        "    }",
        "    return s;",
        "}",
        "extern void sdc_benchmark_body(void);",
        "__asm__(",
        _asm_block(benchmark_body),
        ");",
        "",
        "/* Stack - placed in .bss so it gets zero-initialized */",
        "static char sdc_stack[8192] __attribute__((aligned(16)));",
        "void _start(void) {",
        "    __asm__ volatile (\"mov sp, %0\" : : \"r\"(sdc_stack + sizeof(sdc_stack)) : \"memory\");",
        "    uint64_t d = 0xcbf29ce484222325ULL;",
        "    sdc_benchmark_body();",
        "    for (int i = 0; i < 31; ++i) d = sdc_mix_u64(d, sdc_gprs[i]);",
        "    d = sdc_mix_u64(d, sdc_nzcv);",
        "    d = sdc_mix_bytes(d, sdc_simd, sizeof(sdc_simd));",
        "    printf_hex(d);",
        "    while(1);",
        "}",
    ])


def _write_c_and_compile(asm_content: str, testcase_key: str, gcc: str) -> Path:
    """Write C source and compile to static ELF. Returns path to ELF."""
    source = render_materialized_source(asm_content, testcase_key)
    with tempfile.TemporaryDirectory(prefix="sdc_mat_") as tmp:
        tmp_path = Path(tmp)
        src_path = tmp_path / f"{testcase_key}.c"
        elf_path = tmp_path / f"{testcase_key}.elf"
        src_path.write_text(source, encoding="utf-8")
        # Use simpler approach - no linker script, let compiler handle it
        compile_cmd = [
            gcc,
            "-static",
            "-nostdlib",
            "-ffreestanding",
            "-fno-pie",
            "-fno-builtin",
            "-march=armv8.2-a",
            "-nostdinc",
            "-Wl,--gc-sections",
            "-e", "_start",
            "-o", str(elf_path),
            str(src_path),
        ]
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(
                f"Compilation failed for {testcase_key}:\n{result.stderr}"
            )
        # Copy ELF to materialized root
        out_dir = DEFAULT_MATERIALIZED_ROOT / testcase_key
        out_dir.mkdir(parents=True, exist_ok=True)
        dest_elf = out_dir / f"{testcase_key}.elf"
        shutil.copy2(elf_path, dest_elf)
        return dest_elf


def _run_gem5(elf_path: Path, gem5_binary: Path, gem5_config: Path, out_dir: Path) -> Dict[str, Any]:
    """Run gem5 SE on the ELF. Returns gem5 stats dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(gem5_binary),
        "--outdir", str(out_dir),
        "--redirect-stderr",
        str(gem5_config),
        str(elf_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    stats: Dict[str, Any] = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    stats_file = out_dir / "stats.txt"
    config_file = out_dir / "config.json"
    if stats_file.exists():
        stats["stats_file"] = str(stats_file)
        # Parse a few key stats
        for line in stats_file.read_text().splitlines():
            if not line.startswith("sim_ticks"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    stats["sim_ticks"] = int(parts[1])
                except ValueError:
                    pass

    if config_file.exists():
        stats["config_file"] = str(config_file)

    return stats


def _run_mcpat(target_dir: Path, mcpat_binary: Optional[Path]) -> Dict[str, Any]:
    """Run McPAT on gem5 output directory."""
    sys.path.insert(0, str(REPO_ROOT / "mcpat"))
    from pypat.conversion.convert import run as run_mcpat_conversion
    result = run_mcpat_conversion(
        target_dir,
        template_profile="arm64-kunpeng920",
        print_level=1,
        mcpat_binary=mcpat_binary,
    )
    return {
        "power_total": float(result.get("power_total", 0.0)),
        "power_dynamic": float(result.get("power_dynamic", 0.0)),
        "power_leakage": float(result.get("power_leakage", 0.0)),
        "power_peak_dynamic": float(result.get("power_peak_dynamic", 0.0)),
        "mcpat_input": str(result.get("mcpat_input", "")),
        "mcpat_output": str(result.get("mcpat_output", "")),
        "stats_file": str(result.get("stats_file", "")),
        "config_file": str(result.get("config_file", "")),
    }


def _hash_key(asm_lines: List[str]) -> str:
    content = "\n".join(asm_lines)
    return hashlib.sha1(content.encode()).hexdigest()[:16]


@dataclass
class PowerAnalysisResult:
    testcase_key: str
    elf_path: str
    gem5_out_dir: str
    gem5_stats: Dict[str, Any]
    mcpat_result: Optional[Dict[str, Any]]
    mcpat_error: Optional[str]
    status: str  # COMPLETED or FAILED


def run_power_analysis(
    vault_path: Path,
    limit: int = 10,
    gem5_binary: Path = DEFAULT_GEM5_BINARY,
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    mcpat_binary: Optional[Path] = None,
    gcc: str = None,
    materialized_root: Path = DEFAULT_MATERIALIZED_ROOT,
) -> List[PowerAnalysisResult]:
    """Run the full power-analysis pipeline on top-k vault entries."""
    if gcc is None:
        gcc = _find_aarch64_gcc()

    sys.path.insert(0, str(REPO_ROOT))
    from sdc_vault import SDCVault, VaultEntry

    with SDCVault(vault_path) as vault:
        # Fetch PENDING entries sorted by risk score
        rows = vault.fetch_top_k_risky(limit, statuses=["PENDING"])
        if not rows:
            print("No PENDING testcases in vault. Nothing to do.")
            return []

        print(f"Processing {len(rows)} testcase(s)...")
        results: List[PowerAnalysisResult] = []

        for row in rows:
            testcase_key = str(row["testcase_key"])
            asm_content = str(row["asm_content"])
            print(f"\n[{testcase_key}] ACE={row['ace_score']:.3f} RISK={row['risk_score']:.3f}")

            try:
                # 1. Compile
                print(f"  Compiling with {gcc}...")
                elf_path = _write_c_and_compile(asm_content, testcase_key, gcc)
                print(f"  ELF: {elf_path}")

                # 2. Run gem5 SE
                out_dir = materialized_root / testcase_key / "gem5_out"
                print(f"  Running gem5 SE...")
                gem5_stats = _run_gem5(elf_path, gem5_binary, gem5_config, out_dir)
                print(f"  gem5 exit={gem5_stats.get('returncode', -1)}, ticks={gem5_stats.get('sim_ticks', '?')}")

                # 3. Run McPAT
                mcpat_result = None
                mcpat_error = None
                print(f"  Running McPAT...")
                try:
                    mcpat_result = _run_mcpat(out_dir, mcpat_binary)
                    print(f"  McPAT power_total={mcpat_result['power_total']:.4f}W "
                          f"dynamic={mcpat_result['power_dynamic']:.4f}W")
                except Exception as exc:
                    mcpat_error = str(exc)
                    print(f"  McPAT error (non-fatal): {mcpat_error}")

                # 4. Update vault
                status = "COMPLETED" if mcpat_result else "GEM5_OK"
                vault.update_execution_result(
                    testcase_key,
                    mcpat_power=mcpat_result["power_total"] if mcpat_result else None,
                    status=status,
                    metadata={"gem5_stats": gem5_stats, "mcpat_result": mcpat_result},
                )

                results.append(PowerAnalysisResult(
                    testcase_key=testcase_key,
                    elf_path=str(elf_path),
                    gem5_out_dir=str(out_dir),
                    gem5_stats=gem5_stats,
                    mcpat_result=mcpat_result,
                    mcpat_error=mcpat_error,
                    status=status,
                ))
                print(f"  → {status}")

            except Exception as exc:
                print(f"  ✗ FAILED: {exc}")
                vault.update_execution_result(
                    testcase_key,
                    status="FAILED",
                    metadata={"error": str(exc)},
                )
                results.append(PowerAnalysisResult(
                    testcase_key=testcase_key,
                    elf_path="",
                    gem5_out_dir="",
                    gem5_stats={},
                    mcpat_result=None,
                    mcpat_error=str(exc),
                    status="FAILED",
                ))

        return results


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Power-analysis pipeline: vault → compile → gem5 SE → McPAT → vault"
    )
    p.add_argument("--db", type=Path, default=DEFAULT_VAULT, help="Vault SQLite path")
    p.add_argument("--limit", type=int, default=10, help="Number of PENDING testcases to process")
    p.add_argument("--gem5-binary", type=Path, default=DEFAULT_GEM5_BINARY)
    p.add_argument("--gem5-config", type=Path, default=DEFAULT_GEM5_CONFIG)
    p.add_argument("--mcpat-binary", type=Path, default=DEFAULT_MCPAT_BINARY)
    p.add_argument("--gcc", default=None, help="aarch64-elf-gcc path (default: search PATH)")
    p.add_argument("--materialized-root", type=Path, default=DEFAULT_MATERIALIZED_ROOT)
    return p


def main() -> int:
    args = _build_parser().parse_args()
    results = run_power_analysis(
        vault_path=args.db,
        limit=args.limit,
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        mcpat_binary=args.mcpat_binary,
        gcc=args.gcc,
        materialized_root=args.materialized_root,
    )
    completed = sum(1 for r in results if r.status in ("COMPLETED", "GEM5_OK"))
    failed = sum(1 for r in results if r.status == "FAILED")
    print(f"\nDone: {completed} completed, {failed} failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())