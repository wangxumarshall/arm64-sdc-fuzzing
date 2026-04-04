#!/usr/bin/env python3
"""Build and inspect the local ARM64/A64 instruction catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
MICROPROBE_SRC = REPO_ROOT / "microprobe" / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MICROPROBE_SRC) not in sys.path:
    sys.path.insert(0, str(MICROPROBE_SRC))

from microprobe.utils.arm64_isa_catalog import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    DEFAULT_CLASSES,
    DEFAULT_DOCS_DIR,
    PROFILE_ALL_GENERATABLE,
    build_catalog,
    build_catalog_summary,
    iter_catalog_encodings,
    load_catalog,
    save_catalog,
    validate_sequence_asm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and inspect a normalized ARM64/A64 catalog."
    )
    parser.add_argument(
        "--xml-dir",
        type=Path,
        required=False,
        help="Path to the extracted Arm A64 XML directory.",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=DEFAULT_DOCS_DIR,
        help="Path to docs/armv8-isa markdown files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="Where to write the generated JSON catalog.",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=list(DEFAULT_CLASSES),
        help="Instruction classes to include.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a compact summary after building/loading the catalog.",
    )
    parser.add_argument(
        "--validate-sample",
        action="store_true",
        help="Validate one generated sample sequence with clang.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the loaded/generated catalog as JSON.",
    )
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="Load the existing catalog instead of rebuilding it from XML.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.load_only:
        catalog = load_catalog(args.output)
    else:
        if args.xml_dir is None:
            raise SystemExit("--xml-dir is required unless --load-only is used")
        catalog = build_catalog(
            args.xml_dir,
            docs_dir=args.docs_dir,
            classes=args.classes,
        )
        save_catalog(catalog, args.output)

    if args.json:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return 0

    if args.print_summary or not args.json:
        print(json.dumps(build_catalog_summary(catalog), indent=2, ensure_ascii=False))

    if args.validate_sample:
        sample = list(
            iter_catalog_encodings(catalog, profile_name=PROFILE_ALL_GENERATABLE)
        )[:8]
        result = validate_sequence_asm(sample)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
