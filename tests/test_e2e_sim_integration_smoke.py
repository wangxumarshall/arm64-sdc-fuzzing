import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.environ.get("SDC_RUN_REAL_SIM_SMOKE") != "1",
    reason="manual integration smoke; set SDC_RUN_REAL_SIM_SMOKE=1 to enable",
)
def test_e2e_sim_integration_smoke(tmp_path):
    output_root = tmp_path / "e2e-sim"
    command = [
        sys.executable,
        str((REPO_ROOT / "tools" / "sdc_agent.py").resolve()),
        "e2e-sim",
        "--output-root",
        str(output_root),
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["mode"] == "e2e-sim"
    report_path = Path(payload["report_json"])
    assert report_path.exists()
