#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Kunpeng920 calibration override table from real-hardware collection runs."
    )
    parser.add_argument(
        "dataset_root",
        type=Path,
        help="Directory containing one or more collect_kunpeng920_counters.sh run directories.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output calibration JSON. Defaults to <dataset_root>/kunpeng920_calibration.json.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from pypat.conversion.calibration import (  # noqa: E402
        DEFAULT_CALIBRATION_FILENAME,
        build_kunpeng920_calibration,
    )

    output = args.output or (args.dataset_root / DEFAULT_CALIBRATION_FILENAME)
    payload = build_kunpeng920_calibration(args.dataset_root, output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
