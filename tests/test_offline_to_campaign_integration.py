import importlib.util
import json
from pathlib import Path

from sdc_agent.differential import CommandResult, DifferentialResult
from sdc_agent.campaign import execute_campaign
from sdc_agent.vault import SDCVault


MICROPROBE_TOOL = (
    Path(__file__).resolve().parents[1]
    / "microprobe"
    / "targets"
    / "generic"
    / "tools"
    / "mp_sdc_offline_gen.py"
)
SPEC = importlib.util.spec_from_file_location("mp_sdc_offline_gen", MICROPROBE_TOOL)
assert SPEC is not None and SPEC.loader is not None
mp_sdc_offline_gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mp_sdc_offline_gen)


def test_offline_generator_output_flows_into_campaign(monkeypatch, tmp_path):
    generated = mp_sdc_offline_gen._generate_one(
        {
            "target": "armv8_common-armv8_common-aarch64_linux_gcc",
            "policy": "sdc_fuzzing",
            "wrapper": "BareMetalDiffWrapper",
            "sequence_length": 4,
            "benchmark_size": 32,
            "dependency_distance": 1,
            "memory_stream_stride": 8192,
            "strict_validation": False,
            "seed": 37,
            "output_dir": str(tmp_path / "generated"),
        }
    )

    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(generated["entry"])

    monkeypatch.setattr(
        "sdc_agent.campaign.run_preflight",
        lambda **kwargs: {"ready": True, "checks": [], "repo_root": str(tmp_path)},
    )

    def fake_run_differential(**kwargs):
        source = kwargs["source"]
        assert source.exists()
        assert source.suffix == ".c"
        assert "SDC_DIGEST=" in source.read_text(encoding="utf-8")
        return DifferentialResult(
            status="matched",
            golden_digest="1111",
            faulted_digest="1111",
            compile=CommandResult(["cc"], 0, "", ""),
            qemu=CommandResult(["qemu"], 0, "SDC_DIGEST=1111", ""),
            gem5=CommandResult(["gem5"], 0, "SDC_DIGEST=1111", ""),
            mcpat={"power_total": 1.25},
            mcpat_error=None,
        )

    monkeypatch.setattr("sdc_agent.campaign.run_differential", fake_run_differential)

    result = execute_campaign(
        db_path=db_path,
        limit=1,
        source_root=None,
        output_root=tmp_path / "campaign",
        dry_run=False,
        skip_preflight=False,
        compiler="cc",
        compiler_flags=[],
        qemu_binary="qemu-aarch64",
        qemu_args=[],
        gem5_binary="gem5.opt",
        gem5_config=tmp_path / "cfg.py",
        gem5_args=[],
        gem5_cmd_flag="auto",
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=5,
        fault_tick=1200,
        skip_gem5=False,
        skip_mcpat=False,
        mcpat_template_profile="arm64-kunpeng920",
        mcpat_binary=tmp_path / "mcpat",
        timeout=30,
    )

    assert result["ok"] is True
    assert result["counts"]["executed"] == 1
    assert result["runs"][0]["action"] == "executed"

    with SDCVault(db_path) as vault:
        row = vault.get_testcase(generated["entry"].testcase_key)
        assert row is not None
        assert row["status"] == "MATCHED"
        metadata = json.loads(row["metadata_json"])
        assert metadata["source_path"].endswith(".c")
        assert metadata["rendered_path"].endswith(".c")
        assert metadata["campaign"]["result_json"].endswith("result.json")
