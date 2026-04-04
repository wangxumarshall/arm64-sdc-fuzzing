#!/usr/bin/env python3
"""Managed monorepo domain registry and status helpers."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ManagedDomain:
    domain_id: str
    display_name: str
    path_prefixes: tuple[str, ...]
    project_role: str
    phase_tags: tuple[str, ...]
    is_core_subproject: bool


@dataclass(frozen=True)
class ManagedDomainStatus:
    domain_id: str
    display_name: str
    path_prefixes: tuple[str, ...]
    project_role: str
    phase_tags: tuple[str, ...]
    is_core_subproject: bool
    changed_files: List[str]
    changed_file_count: int
    staged_file_count: int
    unstaged_file_count: int
    untracked_file_count: int
    recent_commits: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


MANAGED_DOMAINS: tuple[ManagedDomain, ...] = (
    ManagedDomain(
        domain_id="root-control-plane",
        display_name="Root Control Plane",
        path_prefixes=(
            "sdc_agent/",
            "tools/",
            "tests/",
            "docs/",
            "scripts/",
            "README.md",
            ".gitignore",
            ".gitmodules",
        ),
        project_role="Sub-P4 Control plane",
        phase_tags=("Phase 0", "Phase 1", "Phase 2", "Phase 4", "Phase 6", "Phase 7"),
        is_core_subproject=False,
    ),
    ManagedDomain(
        domain_id="microprobe",
        display_name="microprobe",
        path_prefixes=("microprobe/",),
        project_role="Sub-P1 microprobe-arm",
        phase_tags=("Phase 2", "Phase 3", "Phase 7"),
        is_core_subproject=True,
    ),
    ManagedDomain(
        domain_id="qemu",
        display_name="qemu",
        path_prefixes=("qemu/",),
        project_role="Sub-P2-1 qemu",
        phase_tags=("Phase 2", "Phase 4"),
        is_core_subproject=True,
    ),
    ManagedDomain(
        domain_id="gem5",
        display_name="gem5",
        path_prefixes=("gem5/",),
        project_role="Sub-P2-2 gem5",
        phase_tags=("Phase 4", "Phase 5"),
        is_core_subproject=True,
    ),
    ManagedDomain(
        domain_id="mcpat",
        display_name="mcpat",
        path_prefixes=("mcpat/",),
        project_role="Sub-P3 mcpat-arm",
        phase_tags=("Phase 2", "Phase 3"),
        is_core_subproject=True,
    ),
    ManagedDomain(
        domain_id="opendcdiag",
        display_name="opendcdiag",
        path_prefixes=("opendcdiag/",),
        project_role="Sub-P0 opendcdiag-arm",
        phase_tags=("Phase 6",),
        is_core_subproject=True,
    ),
)


def _run_git(repo_root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )


def _parse_name_lines(output: str) -> List[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def classify_path(path: str) -> str:
    normalized = path.strip()
    for domain in MANAGED_DOMAINS:
        for prefix in domain.path_prefixes:
            if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
                return domain.domain_id
    return "unmanaged"


def _domain_paths(domain: ManagedDomain) -> List[str]:
    return list(domain.path_prefixes)


def _recent_commits(repo_root: Path, domain: ManagedDomain, limit: int) -> List[Dict[str, str]]:
    completed = _run_git(
        repo_root,
        [
            "log",
            f"-n{limit}",
            "--pretty=format:%H%x09%s",
            "--",
            *_domain_paths(domain),
        ],
    )
    if completed.returncode != 0:
        return []
    records: List[Dict[str, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        records.append({"sha": sha, "subject": subject})
    return records


def collect_domain_statuses(
    repo_root: Path = REPO_ROOT,
    *,
    recent_limit: int = 5,
) -> List[ManagedDomainStatus]:
    repo_root = repo_root.resolve()
    staged = set(
        _parse_name_lines(_run_git(repo_root, ["diff", "--name-only", "--cached"]).stdout)
    )
    unstaged = set(
        _parse_name_lines(_run_git(repo_root, ["diff", "--name-only"]).stdout)
    )
    untracked = set(
        _parse_name_lines(
            _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"]).stdout
        )
    )
    changed = staged | unstaged | untracked

    statuses: List[ManagedDomainStatus] = []
    for domain in MANAGED_DOMAINS:
        domain_changed = sorted(
            path for path in changed if classify_path(path) == domain.domain_id
        )
        statuses.append(
            ManagedDomainStatus(
                domain_id=domain.domain_id,
                display_name=domain.display_name,
                path_prefixes=domain.path_prefixes,
                project_role=domain.project_role,
                phase_tags=domain.phase_tags,
                is_core_subproject=domain.is_core_subproject,
                changed_files=domain_changed,
                changed_file_count=len(domain_changed),
                staged_file_count=sum(1 for path in staged if classify_path(path) == domain.domain_id),
                unstaged_file_count=sum(1 for path in unstaged if classify_path(path) == domain.domain_id),
                untracked_file_count=sum(1 for path in untracked if classify_path(path) == domain.domain_id),
                recent_commits=_recent_commits(repo_root, domain, recent_limit),
            )
        )
    return statuses


def summarize_managed_domains(
    repo_root: Path = REPO_ROOT,
    *,
    recent_limit: int = 3,
) -> Dict[str, Any]:
    statuses = collect_domain_statuses(repo_root, recent_limit=recent_limit)
    changed_domains = [status for status in statuses if status.changed_file_count > 0]
    return {
        "repo_root": str(repo_root.resolve()),
        "domain_count": len(statuses),
        "changed_domain_count": len(changed_domains),
        "core_subproject_count": sum(1 for status in statuses if status.is_core_subproject),
        "domains": [status.to_dict() for status in statuses],
    }


def diff_for_domain(
    domain_id: str,
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    domain = next((item for item in MANAGED_DOMAINS if item.domain_id == domain_id), None)
    if domain is None:
        raise KeyError(f"Unknown domain_id: {domain_id}")

    statuses = collect_domain_statuses(repo_root, recent_limit=5)
    status = next(item for item in statuses if item.domain_id == domain_id)
    diff_stat = _run_git(
        repo_root,
        ["diff", "--stat", "--", *_domain_paths(domain)],
    )
    staged_diff_stat = _run_git(
        repo_root,
        ["diff", "--stat", "--cached", "--", *_domain_paths(domain)],
    )
    return {
        "domain": status.to_dict(),
        "unstaged_diff_stat": diff_stat.stdout.strip(),
        "staged_diff_stat": staged_diff_stat.stdout.strip(),
    }
