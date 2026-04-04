#!/usr/bin/env python3
"""Hardware-promotion control plane for the ARM64 SDC pipeline."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .materialize import SDC_MEMORY_SIZE, _asm_block, _benchmark_body_lines
from .scheduler import FeedbackScheduler, RankedCandidate
from .vault import SDCVault


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "hardware-lane"
DEFAULT_BACKEND_NAME = "opendcdiag"


@dataclass(frozen=True)
class HardwarePromotionRecord:
    testcase_key: str
    external_test_name: str
    backend_name: str
    promotion_score: float
    promotion_ready: bool
    promotion_id: Optional[int]
    status: str
    bundle_dir: str
    manifest_path: str
    test_source_path: str
    asm_path: str
    meson_fragment_path: str


def _sanitize_identifier(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = normalized.strip("_")
    if not normalized:
        normalized = "seed"
    if normalized[0].isdigit():
        normalized = f"sdc_{normalized}"
    return normalized.lower()


def _decode_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw_value = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    return json.loads(str(raw_value))


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _profile_name(metadata: Mapping[str, Any]) -> str:
    for key in ("effective_profile_name", "profile_name", "requested_profile_name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return "SIM_SAFE"


def default_external_test_name(testcase_key: str) -> str:
    return f"arm64_sdc_{_sanitize_identifier(testcase_key)}"


def _expected_golden_digest(candidate: RankedCandidate) -> Optional[str]:
    for value in (
        candidate.row.get("qemu_golden_hash"),
        candidate.metadata.get("golden_digest"),
        candidate.metadata.get("outer_loop", {}).get("qemu_golden_digest")
        if isinstance(candidate.metadata.get("outer_loop"), Mapping)
        else None,
    ):
        if value:
            return str(value).strip().lower()
    return None


def compute_promotion_score(
    candidate: RankedCandidate,
    *,
    existing_promotion_count: int,
) -> Dict[str, float]:
    metadata = candidate.metadata
    outer_loop = metadata.get("outer_loop", {})
    if not isinstance(outer_loop, Mapping):
        outer_loop = {}

    base_score = max(
        candidate.promotion_readiness_score,
        candidate.outer_value_score * 0.5,
        candidate.inner_value_score * 0.25,
        candidate.fitness * 0.1,
    )

    coverage_bonus = 1.0
    if _profile_name(metadata) == "HW_AGGRESSIVE":
        coverage_bonus += 0.15
    if candidate.injector_confidence_score > 0.0:
        coverage_bonus += 0.10
    if _float_or_default(metadata.get("preferred_stride_bytes"), 0.0) >= 8192:
        coverage_bonus += 0.05
    execution_planes = outer_loop.get("execution_planes", {})
    if isinstance(execution_planes, Mapping) and execution_planes.get("gem5_scripted", 0):
        coverage_bonus += 0.05

    deployment_cost_penalty = 1.0 / (1.0 + (0.25 * max(existing_promotion_count, 0)))
    promotion_score = base_score * coverage_bonus * deployment_cost_penalty
    return {
        "base_score": base_score,
        "hardware_coverage_bonus": coverage_bonus,
        "deployment_cost_penalty": deployment_cost_penalty,
        "promotion_score": promotion_score,
    }


def render_opendcdiag_promotion_source(
    *,
    testcase_key: str,
    external_test_name: str,
    asm_content: str,
    metadata: Mapping[str, Any],
    promotion_components: Mapping[str, Any],
    expected_golden_digest: Optional[str],
) -> str:
    escaped_key = json.dumps(testcase_key)
    escaped_profile = json.dumps(_profile_name(metadata))
    escaped_name = _sanitize_identifier(external_test_name)
    description = json.dumps(
        f"Promoted ARM64 SDC testcase {testcase_key} prepared by the SDC-Agent hardware lane"
    )
    promotion_score = _float_or_default(promotion_components.get("promotion_score"))
    expected_digest_literal = (
        f"0x{expected_golden_digest}ULL"
        if expected_golden_digest is not None
        else "0ULL"
    )
    has_expected_digest = "true" if expected_golden_digest is not None else "false"

    return "\n".join(
        [
            '#include "sandstone.h"',
            "",
            "#ifdef __aarch64__",
            "#include <cinttypes>",
            "#include <cstdint>",
            "#include <cstdlib>",
            "#include <cstring>",
            "#endif",
            "",
            f"static const char kPromotedTestcaseKey[] = {escaped_key};",
            f"static const char kPromotedProfileName[] = {escaped_profile};",
            f"static const double kPromotionScore = {promotion_score:.12f};",
            f"static const bool kHasExpectedDigest = {has_expected_digest};",
            f"static const uint64_t kExpectedDigest = {expected_digest_literal};",
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
            "static void sdc_prepare_memory(void)",
            "{",
            "    std::memset(sdc_gprs, 0, sizeof(sdc_gprs));",
            "    sdc_nzcv = 0;",
            "    std::memset(sdc_simd, 0, sizeof(sdc_simd));",
            "    for (size_t index = 0; index < sizeof(sdc_memory); ++index) {",
            "        sdc_memory[index] = (uint8_t)(((index * 131U) + 17U) & 0xffU);",
            "    }",
            "}",
            "",
            'extern "C" void sdc_benchmark_body(void);',
            "__asm__(",
            _asm_block(_benchmark_body_lines(asm_content)),
            ");",
            "",
            "static uint64_t sdc_compute_digest(void)",
            "{",
            "    uint64_t digest = 0xcbf29ce484222325ULL;",
            "    sdc_prepare_memory();",
            "    sdc_benchmark_body();",
            "    for (size_t index = 0; index < 31; ++index) {",
            "        digest = sdc_mix_u64(digest, sdc_gprs[index]);",
            "    }",
            "    digest = sdc_mix_u64(digest, sdc_nzcv);",
            "    digest = sdc_mix_bytes(digest, sdc_simd, sizeof(sdc_simd));",
            "    digest = sdc_mix_bytes(digest, sdc_memory, sizeof(sdc_memory));",
            "    return digest;",
            "}",
            "",
            f"static int {escaped_name}_run(struct test *test, int cpu)",
            "{",
            "    (void)test;",
            "    (void)cpu;",
            "#ifdef __aarch64__",
            "    if (!kHasExpectedDigest) {",
            "        return EXIT_FAILURE;",
            "    }",
            "    const uint64_t observed_digest = sdc_compute_digest();",
            "    if (observed_digest != kExpectedDigest) {",
            "        return EXIT_FAILURE;",
            "    }",
            "    return EXIT_SUCCESS;",
            "#else",
            "    return EXIT_FAILURE;",
            "#endif",
            "}",
            "",
            f"DECLARE_TEST({escaped_name}, {description})",
            f"    .test_run = {escaped_name}_run,",
            "    .quality_level = TEST_QUALITY_BETA,",
            "END_DECLARE_TEST",
            "",
        ]
    )


def render_meson_fragment(external_test_name: str) -> str:
    source_name = f"{external_test_name}.cpp"
    return "\n".join(
        [
            "# Add the promoted source to opendcdiag/tests/cpu/arm64/meson.build",
            "# when you are ready to compile and run it on hardware.",
            f"'{source_name}',",
            "",
        ]
    )


def emit_promotion_bundle(
    *,
    output_root: Path,
    candidate: RankedCandidate,
    external_test_name: str,
    backend_name: str,
    promotion_components: Mapping[str, Any],
) -> Dict[str, str]:
    bundle_dir = (output_root / candidate.testcase_key / external_test_name).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    asm_path = bundle_dir / f"{external_test_name}.s"
    test_source_path = bundle_dir / f"{external_test_name}.cpp"
    manifest_path = bundle_dir / "promotion.json"
    meson_fragment_path = bundle_dir / "meson.build.fragment"

    asm_content = str(candidate.row.get("asm_content", "") or "")
    expected_golden_digest = _expected_golden_digest(candidate)
    asm_path.write_text(asm_content.rstrip() + "\n", encoding="utf-8")
    test_source_path.write_text(
        render_opendcdiag_promotion_source(
            testcase_key=candidate.testcase_key,
            external_test_name=external_test_name,
            asm_content=asm_content,
            metadata=candidate.metadata,
            promotion_components=promotion_components,
            expected_golden_digest=expected_golden_digest,
        ),
        encoding="utf-8",
    )
    meson_fragment_path.write_text(
        render_meson_fragment(external_test_name),
        encoding="utf-8",
    )

    manifest_payload = {
        "testcase_key": candidate.testcase_key,
        "external_test_name": external_test_name,
        "backend_name": backend_name,
        "promotion_components": dict(promotion_components),
        "scheduler": {
            "fitness": candidate.fitness,
            "outer_value_score": candidate.outer_value_score,
            "injector_confidence_score": candidate.injector_confidence_score,
            "promotion_readiness_score": candidate.promotion_readiness_score,
            "promotion_ready": candidate.promotion_ready,
        },
        "expected_golden_digest": expected_golden_digest,
        "profile_name": _profile_name(candidate.metadata),
        "paths": {
            "bundle_dir": str(bundle_dir),
            "asm_path": str(asm_path.resolve()),
            "test_source_path": str(test_source_path.resolve()),
            "meson_fragment_path": str(meson_fragment_path.resolve()),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "bundle_dir": str(bundle_dir),
        "asm_path": str(asm_path.resolve()),
        "test_source_path": str(test_source_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "meson_fragment_path": str(meson_fragment_path.resolve()),
    }


def run_hardware_promotion(
    *,
    db_path: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    limit: int = 4,
    backend_name: str = DEFAULT_BACKEND_NAME,
    dry_run: bool = False,
) -> Dict[str, Any]:
    output_root = output_root.resolve()
    if not dry_run:
        output_root.mkdir(parents=True, exist_ok=True)

    scheduler = FeedbackScheduler()
    promotions: List[HardwarePromotionRecord] = []
    counts = {
        "selected": 0,
        "planned": 0,
        "emitted": 0,
    }

    with SDCVault(db_path) as vault:
        candidates = scheduler.select_promotion_candidates(vault, limit)
        counts["selected"] = len(candidates)

        for candidate in candidates:
            existing_promotions = vault.list_hardware_promotions(
                candidate.testcase_key,
                limit=200,
            )
            promotion_components = compute_promotion_score(
                candidate,
                existing_promotion_count=len(existing_promotions),
            )
            external_test_name = default_external_test_name(candidate.testcase_key)
            status = "PLANNED" if dry_run else "EMITTED"
            promotion_id: Optional[int] = None

            if dry_run:
                bundle_paths = {
                    "bundle_dir": str((output_root / candidate.testcase_key / external_test_name).resolve()),
                    "asm_path": str((output_root / candidate.testcase_key / external_test_name / f"{external_test_name}.s").resolve()),
                    "test_source_path": str((output_root / candidate.testcase_key / external_test_name / f"{external_test_name}.cpp").resolve()),
                    "manifest_path": str((output_root / candidate.testcase_key / external_test_name / "promotion.json").resolve()),
                    "meson_fragment_path": str((output_root / candidate.testcase_key / external_test_name / "meson.build.fragment").resolve()),
                }
                counts["planned"] += 1
            else:
                expected_golden_digest = _expected_golden_digest(candidate)
                bundle_paths = emit_promotion_bundle(
                    output_root=output_root,
                    candidate=candidate,
                    external_test_name=external_test_name,
                    backend_name=backend_name,
                    promotion_components=promotion_components,
                )
                promotion_metadata = {
                    **bundle_paths,
                    **promotion_components,
                    "expected_golden_digest": expected_golden_digest,
                    "scheduler": {
                        "fitness": candidate.fitness,
                        "outer_value_score": candidate.outer_value_score,
                        "injector_confidence_score": candidate.injector_confidence_score,
                        "promotion_readiness_score": candidate.promotion_readiness_score,
                        "promotion_ready": candidate.promotion_ready,
                    },
                    "profile_name": _profile_name(candidate.metadata),
                }
                promotion_id = vault.upsert_hardware_promotion(
                    candidate.testcase_key,
                    backend_name=backend_name,
                    external_test_name=external_test_name,
                    status=status,
                    metadata=promotion_metadata,
                )

                row = vault.get_testcase(candidate.testcase_key)
                assert row is not None
                metadata = _decode_metadata(row)
                metadata["hardware_lane"] = {
                    "promotion_id": promotion_id,
                    "backend_name": backend_name,
                    "external_test_name": external_test_name,
                    "status": status,
                    **bundle_paths,
                    **promotion_components,
                    "expected_golden_digest": expected_golden_digest,
                }
                vault.update_execution_result(candidate.testcase_key, metadata=metadata)
                counts["emitted"] += 1

            promotions.append(
                HardwarePromotionRecord(
                    testcase_key=candidate.testcase_key,
                    external_test_name=external_test_name,
                    backend_name=backend_name,
                    promotion_score=float(promotion_components["promotion_score"]),
                    promotion_ready=bool(candidate.promotion_ready),
                    promotion_id=promotion_id,
                    status=status,
                    bundle_dir=str(bundle_paths["bundle_dir"]),
                    manifest_path=str(bundle_paths["manifest_path"]),
                    test_source_path=str(bundle_paths["test_source_path"]),
                    asm_path=str(bundle_paths["asm_path"]),
                    meson_fragment_path=str(bundle_paths["meson_fragment_path"]),
                )
            )

    return {
        "ok": True,
        "dry_run": dry_run,
        "backend_name": backend_name,
        "counts": counts,
        "promotions": [asdict(promotion) for promotion in promotions],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote high-value ARM64 SDC samples into hardware-lane bundles."
    )
    parser.add_argument("--db", type=Path, required=True, help="Vault database path.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_hardware_promotion(
        db_path=args.db,
        output_root=args.output_root,
        limit=args.limit,
        backend_name=args.backend_name,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
