#!/usr/bin/env python3
"""Materialize vault assembly snippets into runnable ARM64 C sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "materialized"
SDC_MEMORY_SIZE = 8192
SDC_MEMORY_BASE_OFFSET = 1024
SDC_REGISTER_STRIDE = 96


def _escape_c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _asm_block(lines: Iterable[str]) -> str:
    return "\n".join(f'"{_escape_c_string(line)}\\n"' for line in lines if line.strip())


def _prepare_asm_lines(asm_content: str) -> List[str]:
    lines = [line.rstrip() for line in asm_content.splitlines() if line.strip()]
    return lines or ["nop"]


def _register_initialization_lines() -> List[str]:
    lines = [
        "adrp x18, sdc_memory",
        "add x18, x18, :lo12:sdc_memory",
    ]
    for reg_index in range(31):
        offset = SDC_MEMORY_BASE_OFFSET + (reg_index * SDC_REGISTER_STRIDE)
        if reg_index == 18:
            continue
        lines.extend(
            [
                f"mov x{reg_index}, x18",
                f"add x{reg_index}, x{reg_index}, #{offset}",
            ]
        )
    lines.append(
        f"add x18, x18, #{SDC_MEMORY_BASE_OFFSET + (18 * SDC_REGISTER_STRIDE)}"
    )
    for reg_index in range(8):
        lines.append(f"movi v{reg_index}.16b, #0")
    return lines


def _register_capture_lines() -> List[str]:
    lines = [
        "sub sp, sp, #16",
        "stp x16, x17, [sp]",
        "adrp x16, sdc_gprs",
        "add x16, x16, :lo12:sdc_gprs",
    ]
    for reg_index in range(16):
        lines.append(f"str x{reg_index}, [x16, #{reg_index * 8}]")
    lines.extend(
        [
            "ldr x17, [sp, #0]",
            "str x17, [x16, #128]",
            "ldr x17, [sp, #8]",
            "str x17, [x16, #136]",
        ]
    )
    for reg_index in range(18, 31):
        lines.append(f"str x{reg_index}, [x16, #{reg_index * 8}]")
    lines.extend(
        [
            "add sp, sp, #16",
            "adrp x16, sdc_nzcv",
            "add x16, x16, :lo12:sdc_nzcv",
            "mrs x17, nzcv",
            "str x17, [x16]",
            "adrp x16, sdc_simd",
            "add x16, x16, :lo12:sdc_simd",
        ]
    )
    for reg_index in range(8):
        lines.append(f"str q{reg_index}, [x16, #{reg_index * 16}]")
    lines.extend(
        [
            "ret",
            ".size sdc_benchmark_body, .-sdc_benchmark_body",
        ]
    )
    return lines


def _benchmark_body_lines(asm_content: str) -> List[str]:
    lines = [
        ".text",
        ".align 4",
        ".global sdc_benchmark_body",
        ".type sdc_benchmark_body, %function",
        "sdc_benchmark_body:",
    ]
    lines.extend(_register_initialization_lines())
    lines.extend(_prepare_asm_lines(asm_content))
    lines.extend(_register_capture_lines())
    return lines


def render_materialized_source(asm_content: str, testcase_key: str) -> str:
    return "\n".join(
        [
            "#include <inttypes.h>",
            "#include <stdint.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <string.h>",
            "",
            f"/* Materialized from vault testcase: {testcase_key} */",
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
            "static inline uint64_t sdc_mix_bytes(",
            "    uint64_t state, const uint8_t *buffer, size_t size)",
            "{",
            "    for (size_t index = 0; index < size; ++index)",
            "    {",
            "        state ^= (uint64_t)buffer[index] << ((index & 7U) * 8U);",
            "        state *= 0x100000001b3ULL;",
            "        state = sdc_rotl64(state, 9);",
            "    }",
            "    return state;",
            "}",
            "",
            "static void sdc_prepare_memory(void)",
            "{",
            "    memset(sdc_gprs, 0, sizeof(sdc_gprs));",
            "    sdc_nzcv = 0;",
            "    memset(sdc_simd, 0, sizeof(sdc_simd));",
            "    for (size_t index = 0; index < sizeof(sdc_memory); ++index)",
            "    {",
            "        sdc_memory[index] = (uint8_t)(((index * 131U) + 17U) & 0xffU);",
            "    }",
            "}",
            "",
            "extern void sdc_benchmark_body(void);",
            "__asm__(",
            _asm_block(_benchmark_body_lines(asm_content)),
            ");",
            "",
            "int main(void)",
            "{",
            "    uint64_t sdc_digest = 0xcbf29ce484222325ULL;",
            "    sdc_prepare_memory();",
            "    sdc_benchmark_body();",
            "    for (size_t sdc_index = 0; sdc_index < 31; ++sdc_index)",
            "    {",
            "        sdc_digest = sdc_mix_u64(sdc_digest, sdc_gprs[sdc_index]);",
            "    }",
            "    sdc_digest = sdc_mix_u64(sdc_digest, sdc_nzcv);",
            "    sdc_digest = sdc_mix_bytes(sdc_digest, sdc_simd, sizeof(sdc_simd));",
            "    sdc_digest = sdc_mix_bytes(sdc_digest, sdc_memory, sizeof(sdc_memory));",
            '    printf("SDC_DIGEST=%016" PRIx64 "\\n", sdc_digest);',
            "    fflush(stdout);",
            "    return 0;",
            "}",
            "",
        ]
    )


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw_value = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(str(raw_value))


def materialize_testcase(
    vault: SDCVault,
    testcase_key: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    row = vault.get_testcase(testcase_key)
    if row is None:
        raise KeyError(f"Unknown testcase_key: {testcase_key}")

    output_root.mkdir(parents=True, exist_ok=True)
    source_path = (output_root / f"{testcase_key}.c").resolve()
    source_path.write_text(
        render_materialized_source(str(row["asm_content"]), testcase_key),
        encoding="utf-8",
    )

    metadata = _decode_metadata(row)
    metadata["source_path"] = str(source_path)
    metadata["materialized"] = {
        "source_path": str(source_path),
        "output_root": str(output_root.resolve()),
    }
    vault.update_execution_result(testcase_key, metadata=metadata)
    return source_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize vault assembly entries into ARM64 C sources."
    )
    parser.add_argument("--db", type=Path, required=True, help="Vault database path.")
    parser.add_argument(
        "--testcase-key",
        action="append",
        default=[],
        help="Specific testcase key to materialize. Repeat as needed.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If no testcase key is provided, materialize up to this many pending entries.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for generated C files.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    with SDCVault(args.db) as vault:
        testcase_keys = list(args.testcase_key)
        if not testcase_keys:
            pending = vault.fetch_top_k_risky(args.limit or 10)
            testcase_keys = [str(row["testcase_key"]) for row in pending]

        materialized = [
            str(materialize_testcase(vault, testcase_key, output_root=args.output_root))
            for testcase_key in testcase_keys
        ]

    payload = {
        "count": len(materialized),
        "sources": materialized,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
