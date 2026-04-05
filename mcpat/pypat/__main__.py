import argparse
from pathlib import Path

from pypat import run_pypat


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run gem5-to-McPAT conversion and invoke the local mcpat binary."
    )
    parser.add_argument(
        "target_dir",
        type=Path,
        help="Path to a gem5 output directory containing config.json and stats.txt or stats.h5.",
    )
    parser.add_argument(
        "-t",
        "--template",
        type=Path,
        default=None,
        help="Optional McPAT XML template. Defaults to gem5_mcpat_parser/template_x86.xml.",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        type=Path,
        default=None,
        help="Optional path for the generated McPAT XML. Defaults to <target_dir>/conv.xml.",
    )
    parser.add_argument(
        "--template-profile",
        type=str,
        default="auto",
        help="McPAT template profile to use when --template is omitted. "
        "Supported: auto, x86, arm64-kunpeng920.",
    )
    parser.add_argument(
        "--print-level",
        type=int,
        default=1,
        help="McPAT print level passed to the local mcpat binary.",
    )
    parser.add_argument(
        "--opt-for-clk",
        type=int,
        default=0,
        help="Whether to enable McPAT clock optimization (0 or 1).",
    )
    parser.add_argument(
        "--mcpat-binary",
        type=Path,
        default=None,
        help="Optional path to the mcpat executable. Defaults to ./mcpat in the repository root.",
    )
    parser.add_argument(
        "--calibration-file",
        type=Path,
        default=None,
        help="Optional Kunpeng920 calibration JSON. When provided, runtime profile overrides are applied automatically.",
    )
    parser.add_argument(
        "--calibration-dataset",
        type=Path,
        default=None,
        help="Optional directory produced by collect_kunpeng920_counters.sh. "
        "When provided, pypat synthesizes a calibration JSON before conversion.",
    )
    args = parser.parse_args()

    run_pypat(
        target_dir=args.target_dir,
        template=args.template,
        outfile=args.outfile,
        template_profile=args.template_profile,
        print_level=args.print_level,
        opt_for_clk=args.opt_for_clk,
        mcpat_binary=args.mcpat_binary,
        calibration_file=args.calibration_file,
        calibration_dataset=args.calibration_dataset,
    )


if __name__ == "__main__":
    main()
