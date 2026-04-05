"""
[usage]:
python3 Gem5McPATParser_custom.py -c ./config.json -s ./stats.txt
python3 Gem5McPATParser_custom.py -c ./config.json -s ./stats.txt \
  --template-profile arm64-kunpeng920
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert gem5 stats/config into McPAT XML input."
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        required=True,
        metavar="PATH",
        help="Input config.json from gem5 output.",
    )
    parser.add_argument(
        "--stats",
        "-s",
        type=Path,
        required=True,
        metavar="PATH",
        help="Input stats.txt or stats.h5 from gem5 output.",
    )
    parser.add_argument(
        "--template",
        "-t",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional McPAT XML template. Defaults to the selected template profile.",
    )
    parser.add_argument(
        "--template-profile",
        type=str,
        default="auto",
        help="McPAT template profile used when --template is omitted. "
        "Supported: auto, x86, arm64-kunpeng920.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("mcpat-in.xml"),
        metavar="PATH",
        help="Output path for the generated McPAT XML.",
    )
    parser.add_argument(
        "--calibration-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional Kunpeng920 calibration JSON used to override the default profile.",
    )
    parser.add_argument(
        "--calibration-dataset",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional directory of real-hardware collection runs. "
        "When set, a calibration JSON is synthesized before conversion.",
    )
    return parser


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from pypat.conversion.calibration import resolve_kunpeng920_calibration_file
    from pypat.conversion.gem5_to_mcpat import run_conversion

    args = create_parser().parse_args()
    calibration_file = resolve_kunpeng920_calibration_file(
        target_dir=args.output.parent,
        explicit_file=args.calibration_file,
        explicit_dataset=args.calibration_dataset,
        default_repo_file=repo_root / "gem5_mcpat_parser" / "kunpeng920_calibration.json",
    )
    run_conversion(
        stats_file=args.stats,
        config_file=args.config,
        outfile=args.output,
        template=args.template,
        template_profile=args.template_profile,
        calibration_file=calibration_file,
    )


if __name__ == "__main__":
    main()
