"""SDC-Agent package exports."""

from __future__ import annotations

from typing import Any


__all__ = ["run_cycle", "run_evolution", "run_e2e_local", "summarize_vault"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .agent import run_cycle, run_e2e_local, run_evolution, summarize_vault

        exports = {
            "run_cycle": run_cycle,
            "run_e2e_local": run_e2e_local,
            "run_evolution": run_evolution,
            "summarize_vault": summarize_vault,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
