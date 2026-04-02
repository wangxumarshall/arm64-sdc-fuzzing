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


def _escape_c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _asm_block(lines: Iterable[str]) -> str:
    return "\n".join(f'"{_escape_c_string(line)}\\n"' for line in lines if line.strip())


def render_materialized_source(asm_content: str, testcase_key: str) -> str:
    asm_lines = [line.rstrip() for line in asm_content.splitlines() if line.strip()]
    if not asm_lines:
        asm_lines = ["nop"]

    benchmark_body = [
        ".text",
        ".align 4",
        ".global sdc_benchmark_body",
        ".type sdc_benchmark_body, %function",
        "sdc_benchmark_body:",
        "adr x16, sdc_gprs",
        "mov x0, #0",
        "mov x1, #0",
        "mov x2, #0",
        "mov x3, #0",
        "mov x4, #0",
        "mov x5, #0",
        "mov x6, #0",
        "mov x7, #0",
        "movi v0.16b, #0",
        "movi v1.16b, #0",
        "movi v2.16b, #0",
        "movi v3.16b, #0",
        "movi v4.16b, #0",
        "movi v5.16b, #0",
        "movi v6.16b, #0",
        "movi v7.16b, #0",
    ]
    benchmark_body.extend(asm_lines)
    benchmark_body.extend(
        [
            "adr x16, sdc_gprs",
            "str x0, [x16, #0]",
            "str x1, [x16, #8]",
            "str x2, [x16, #16]",
            "str x3, [x16, #24]",
            "str x4, [x16, #32]",
            "str x5, [x16, #40]",
            "str x6, [x16, #48]",
            "str x7, [x16, #56]",
            "str x8, [x16, #64]",
            "str x9, [x16, #72]",
            "str x10, [x16, #80]",
            "str x11, [x16, #88]",
            "str x12, [x16, #96]",
            "str x13, [x16, #104]",
            "str x14, [x16, #112]",
            "str x15, [x16, #120]",
            "str x16, [x16, #128]",
            "str x17, [x16, #136]",
            "str x18, [x16, #144]",
            "str x19, [x16, #152]",
            "str x20, [x16, #160]",
            "str x21, [x16, #168]",
            "str x22, [x16, #176]",
            "str x23, [x16, #184]",
            "str x24, [x16, #192]",
            "str x25, [x16, #200]",
            "str x26, [x16, #208]",
            "str x27, [x16, #216]",
            "str x28, [x16, #224]",
            "str x29, [x16, #232]",
            "str x30, [x16, #240]",
            "adr x16, sdc_nzcv",
            "mrs x17, nzcv",
            "str x17, [x16]",
            "adr x16, sdc_simd",
            "str q0, [x16, #0]",
            "str q1, [x16, #16]",
            "str q2, [x16, #32]",
            "str q3, [x16, #48]",
            "str q4, [x16, #64]",
            "str q5, [x16, #80]",
            "str q6, [x16, #96]",
            "str q7, [x16, #112]",
            "ret",
            ".size sdc_benchmark_body, .-sdc_benchmark_body",
        ]
    )

    return "\n".join(
        [
            "#include <inttypes.h>",
            "#include <stdint.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "",
            f"/* Materialized from vault testcase: {testcase_key} */",
            "static uint64_t sdc_gprs[31] = {0};",
            "static uint64_t sdc_nzcv = 0;",
            "static uint8_t sdc_simd[8 * 16] = {0};",
            "static uint8_t sdc_memory[256] = {0};",
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
            "extern void sdc_benchmark_body(void);",
            "__asm__(",
            _asm_block(benchmark_body),
            ");",
            "",
            "int main(void)",
            "{",
            "    uint64_t sdc_digest = 0xcbf29ce484222325ULL;",
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
