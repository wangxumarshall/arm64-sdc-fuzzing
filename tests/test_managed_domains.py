import subprocess
from pathlib import Path

from sdc_agent.managed_domains import classify_path, collect_domain_statuses, diff_for_domain


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_classify_path_maps_core_domains():
    assert classify_path("microprobe/README.md") == "microprobe"
    assert classify_path("qemu/hw/arm/virt.c") == "qemu"
    assert classify_path("gem5/src/cpu/base.cc") == "gem5"
    assert classify_path("mcpat/README.md") == "mcpat"
    assert classify_path("opendcdiag/tests/cpu/arm64/sdc_test.cpp") == "opendcdiag"
    assert classify_path("sdc_agent/agent.py") == "root-control-plane"
    assert classify_path("docs/state.md") == "root-control-plane"


def test_collect_domain_statuses_and_diff_for_domain(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Codex")
    _git(repo, "config", "user.email", "codex@example.com")

    _write(repo / "README.md", "# demo\n")
    _write(repo / "sdc_agent" / "agent.py", "print('root')\n")
    _write(repo / "microprobe" / "README.md", "microprobe\n")
    _write(repo / "qemu" / "README.rst", "qemu\n")
    _write(repo / "gem5" / "README.md", "gem5\n")
    _write(repo / "mcpat" / "README.md", "mcpat\n")
    _write(repo / "opendcdiag" / "README.md", "opendcdiag\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _write(repo / "microprobe" / "README.md", "microprobe changed\n")
    _write(repo / "sdc_agent" / "agent.py", "print('root changed')\n")
    _write(repo / "qemu" / "new-file.c", "int main(void){return 0;}\n")
    _git(repo, "add", "microprobe/README.md")

    statuses = collect_domain_statuses(repo, recent_limit=2)
    by_id = {item.domain_id: item for item in statuses}

    assert by_id["microprobe"].changed_file_count == 1
    assert by_id["microprobe"].staged_file_count == 1
    assert by_id["root-control-plane"].changed_file_count == 1
    assert by_id["root-control-plane"].unstaged_file_count == 1
    assert by_id["qemu"].untracked_file_count == 1

    diff_payload = diff_for_domain("microprobe", repo)
    assert diff_payload["domain"]["domain_id"] == "microprobe"
    assert diff_payload["domain"]["changed_files"] == ["microprobe/README.md"]
