import shutil
import stat
import sys
from pathlib import Path

import pytest


MCPAT_ROOT = Path(__file__).resolve().parents[1]
if str(MCPAT_ROOT) not in sys.path:
    sys.path.insert(0, str(MCPAT_ROOT))

from pypat.conversion.convert import run, run_mcpat  # noqa: E402


FIXTURE_ROOT = Path(__file__).resolve().parent / "data" / "arm64_kunpeng920_minimal"


def test_arm64_kunpeng920_fixture_runs_end_to_end(tmp_path):
    mcpat_binary = MCPAT_ROOT / "mcpat"
    if not mcpat_binary.exists() or not mcpat_binary.stat().st_mode & stat.S_IXUSR:
        pytest.skip("Local McPAT binary is not built or not executable")

    target_dir = tmp_path / "arm64_kunpeng920_minimal"
    shutil.copytree(FIXTURE_ROOT, target_dir)

    result = run(
        target_dir=target_dir,
        template_profile="arm64-kunpeng920",
        mcpat_binary=mcpat_binary,
    )

    assert result["template_profile"] == "arm64-kunpeng920"
    assert result["power_total"] > 0.0
    assert result["power_peak_dynamic"] > 0.0
    assert Path(result["mcpat_input"]).exists()
    assert Path(result["mcpat_output"]).exists()
    assert Path(result["mcpat_power_trace"]).exists()


def test_run_mcpat_detects_fatal_log_even_on_zero_exit(tmp_path):
    fake_mcpat = tmp_path / "fake-mcpat.sh"
    fake_mcpat.write_text(
        "#!/bin/sh\n"
        "echo 'ERROR: no valid cache organizations found'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_mcpat.chmod(fake_mcpat.stat().st_mode | stat.S_IXUSR)

    mcpat_input = tmp_path / "conv.xml"
    mcpat_input.write_text("<component id='root' name='root'/>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="fatal error"):
        run_mcpat(
            mcpat_binary=fake_mcpat,
            target=tmp_path,
            mcpat_input=mcpat_input,
            print_level=1,
            opt_for_clk=0,
        )
