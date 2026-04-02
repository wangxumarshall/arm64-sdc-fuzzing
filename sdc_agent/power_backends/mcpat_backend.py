"""Default McPAT power backend for ARM64 SDC differential runs."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
MCPAT_PYPAT_ROOT = REPO_ROOT / "mcpat"


def _bootstrap_mcpat_imports() -> None:
    mcpat_root = str(MCPAT_PYPAT_ROOT)
    if mcpat_root not in sys.path:
        sys.path.insert(0, mcpat_root)


@dataclass(frozen=True)
class McPATBackend:
    """Thin adapter around the local `pypat` conversion pipeline."""

    template_profile: str = "arm64-kunpeng920"
    print_level: int = 1
    opt_for_clk: int = 0
    mcpat_binary: Optional[Path] = None

    def run(self, target_dir: Path | str) -> Dict[str, Any]:
        """Run McPAT conversion and normalize the artifact/result contract."""

        _bootstrap_mcpat_imports()
        from pypat.conversion.convert import run as run_mcpat_conversion

        run_directory = Path(target_dir).resolve()
        result = run_mcpat_conversion(
            run_directory,
            template_profile=self.template_profile,
            print_level=self.print_level,
            opt_for_clk=self.opt_for_clk,
            mcpat_binary=self.mcpat_binary,
        )

        normalized: Dict[str, Any] = {
            "backend": "mcpat",
            "target_dir": run_directory,
            "template_profile": result.get("template_profile", self.template_profile),
            "power_total": float(result.get("power_total", 0.0)),
            "power_dynamic": float(result.get("power_dynamic", 0.0)),
            "power_leakage": float(result.get("power_leakage", 0.0)),
            "power_peak_dynamic": float(result.get("power_peak_dynamic", 0.0)),
            "mcpat_input": result.get("mcpat_input"),
            "mcpat_output": result.get("mcpat_output"),
            "mcpat_area_output": result.get("mcpat_area_output"),
            "mcpat_power_trace": result.get("mcpat_power_trace"),
            "stats_file": result.get("stats_file"),
            "config_file": result.get("config_file"),
        }
        return normalized
