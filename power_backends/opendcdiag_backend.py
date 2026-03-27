"""Deferred OpenDCDiag backend interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class OpenDCDiagBackend:
    """Placeholder interface for future hardware-side validation."""

    enabled: bool = False

    def run(self, target_dir: Path | str) -> Dict[str, Any]:
        raise NotImplementedError(
            "OpenDCDiagBackend is intentionally disabled in the default "
            "simulator loop. Use McPATBackend for the current ARM64 flow. "
            f"Received target directory: {Path(target_dir).resolve()}"
        )
