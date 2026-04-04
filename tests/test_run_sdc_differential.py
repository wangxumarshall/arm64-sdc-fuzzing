import json
from pathlib import Path

from sdc_agent.differential import (
    build_fault_args,
    CommandResult,
    classify,
    extract_digest,
    run_differential,
)


def test_extract_digest_reads_stdout_then_stderr():
    stdout_result = CommandResult(
        command=["echo"],
        returncode=0,
        stdout="SDC_DIGEST=deadbeef",
        stderr="",
    )
    stderr_result = CommandResult(
        command=["echo"],
        returncode=0,
        stdout="",
        stderr="SDC_HASH=cafebabe",
    )

    assert extract_digest(stdout_result) == "deadbeef"
    assert extract_digest(stderr_result) == "cafebabe"


def test_classify_returns_sdc_found_for_digest_mismatch():
    compile_result = CommandResult(["cc"], 0, "", "")
    qemu_result = CommandResult(["qemu"], 0, "", "")
    gem5_result = CommandResult(["gem5"], 0, "", "")

    assert (
        classify(
            compile_result=compile_result,
            qemu_result=qemu_result,
            gem5_result=gem5_result,
            golden_digest="1111",
            faulted_digest="2222",
        )
        == "sdc_found"
    )


def test_classify_reports_golden_only_without_gem5():
    compile_result = CommandResult(["cc"], 0, "", "")
    qemu_result = CommandResult(["qemu"], 0, "", "")

    assert (
        classify(
            compile_result=compile_result,
            qemu_result=qemu_result,
            gem5_result=None,
            golden_digest="1111",
            faulted_digest=None,
        )
        == "golden_only"
    )


def test_classify_rejects_fault_runs_without_observed_injection():
    compile_result = CommandResult(["cc"], 0, "", "")
    qemu_result = CommandResult(["qemu"], 0, "", "")
    gem5_result = CommandResult(["gem5"], 0, "", "")

    assert (
        classify(
            compile_result=compile_result,
            qemu_result=qemu_result,
            gem5_result=gem5_result,
            golden_digest="1111",
            faulted_digest="1111",
            fault_request={
                "fault_model": "register_bit_flip",
                "execution_plane": "manifest_only",
                "injection_observed": False,
            },
        )
        == "no_injection"
    )


def test_build_fault_args_renders_optional_fields():
    assert build_fault_args(fault_model="none", fault_target="") == [
        "--fault-model",
        "none",
        "--fault-target",
        "",
    ]
    assert build_fault_args(
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=7,
        fault_tick=1234,
    ) == [
        "--fault-model",
        "register_bit_flip",
        "--fault-target",
        "x0",
        "--fault-bit",
        "7",
        "--fault-tick",
        "1234",
    ]


def test_run_differential_exposes_programmatic_pipeline(monkeypatch, tmp_path):
    source = tmp_path / "case.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    observed = {}

    def fake_compile_static_elf(**kwargs):
        return CommandResult(["cc"], 0, "", "")

    def fake_run_qemu(**kwargs):
        return CommandResult(["qemu"], 0, "SDC_DIGEST=1111", "")

    def fake_run_gem5(**kwargs):
        observed["gem5_args"] = kwargs["gem5_args"]
        manifest_path = kwargs["gem5_outdir"] / "sdc_fault_request.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "fault_model": "register_bit_flip",
                    "fault_target": "x0",
                    "fault_bit": 7,
                    "fault_tick": 1234,
                    "implemented_in_script": True,
                    "binary": str((tmp_path / "case.elf").resolve()),
                    "binary_args": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return CommandResult(
            ["gem5"],
            0,
            "SDC_HASH=2222",
            (
                "[sdc] injected register bit flip: "
                "cpu=0 reg=x0 bit=7 "
                "old=0x0000000000000001 new=0x0000000000000081 "
                "tick=1234"
            ),
        )

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path | None = None):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {"power_total": 3.5, "target_dir": str(target_dir)}

    monkeypatch.setattr(
        "sdc_agent.differential.compile_static_elf", fake_compile_static_elf
    )
    monkeypatch.setattr("sdc_agent.differential.run_qemu", fake_run_qemu)
    monkeypatch.setattr("sdc_agent.differential.run_gem5", fake_run_gem5)
    monkeypatch.setattr("sdc_agent.differential.McPATBackend", FakeBackend)

    result = run_differential(
        source=source,
        elf=tmp_path / "case.elf",
        gem5_outdir=tmp_path / "m5out",
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=7,
        fault_tick=1234,
    )

    assert result.status == "sdc_found"
    assert result.golden_digest == "1111"
    assert result.faulted_digest == "2222"
    assert result.mcpat == {"power_total": 3.5, "target_dir": str((tmp_path / "m5out").resolve())}
    assert result.fault_request is not None
    assert result.fault_request["manifest_found"] is True
    assert result.fault_request["implemented_in_script"] is True
    assert result.fault_request["injection_observed"] is True
    assert result.fault_request["execution_plane"] == "gem5_scripted"
    assert result.fault_request["observation"]["register_name"] == "x0"
    assert observed["gem5_args"][:8] == [
        "--fault-model",
        "register_bit_flip",
        "--fault-target",
        "x0",
        "--fault-bit",
        "7",
        "--fault-tick",
        "1234",
    ]


def test_run_differential_marks_manifest_only_faults_as_no_injection(monkeypatch, tmp_path):
    source = tmp_path / "case-no-inject.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    def fake_compile_static_elf(**kwargs):
        return CommandResult(["cc"], 0, "", "")

    def fake_run_qemu(**kwargs):
        return CommandResult(["qemu"], 0, "SDC_DIGEST=1111", "")

    def fake_run_gem5(**kwargs):
        manifest_path = kwargs["gem5_outdir"] / "sdc_fault_request.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "fault_model": "register_bit_flip",
                    "fault_target": "x0",
                    "fault_bit": 3,
                    "fault_tick": 100,
                    "implemented_in_script": False,
                    "binary": str((tmp_path / "case-no-inject.elf").resolve()),
                    "binary_args": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return CommandResult(["gem5"], 0, "SDC_HASH=1111", "")

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path | None = None):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {"power_total": 1.0, "target_dir": str(target_dir)}

    monkeypatch.setattr(
        "sdc_agent.differential.compile_static_elf", fake_compile_static_elf
    )
    monkeypatch.setattr("sdc_agent.differential.run_qemu", fake_run_qemu)
    monkeypatch.setattr("sdc_agent.differential.run_gem5", fake_run_gem5)
    monkeypatch.setattr("sdc_agent.differential.McPATBackend", FakeBackend)

    result = run_differential(
        source=source,
        elf=tmp_path / "case-no-inject.elf",
        gem5_outdir=tmp_path / "m5out-no-inject",
        fault_model="register_bit_flip",
        fault_target="x0",
        fault_bit=3,
        fault_tick=100,
    )

    assert result.status == "no_injection"
    assert result.fault_request is not None
    assert result.fault_request["execution_plane"] == "manifest_only"
    assert result.fault_request["injection_observed"] is False


def test_run_differential_parses_vector_register_fault_observation(monkeypatch, tmp_path):
    source = tmp_path / "case-vec.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    def fake_compile_static_elf(**kwargs):
        return CommandResult(["cc"], 0, "", "")

    def fake_run_qemu(**kwargs):
        return CommandResult(["qemu"], 0, "SDC_DIGEST=aaaa", "")

    def fake_run_gem5(**kwargs):
        manifest_path = kwargs["gem5_outdir"] / "sdc_fault_request.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "fault_model": "vector_register_bit_flip",
                    "fault_target": "v0",
                    "fault_bit": 65,
                    "fault_tick": 2048,
                    "implemented_in_script": True,
                    "binary": str((tmp_path / "case-vec.elf").resolve()),
                    "binary_args": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return CommandResult(
            ["gem5"],
            0,
            "SDC_HASH=bbbb",
            (
                "[sdc] injected vector register bit flip: "
                "cpu=0 reg=v0 bit=65 "
                "old=0x00000000000000000000000000000000 "
                "new=0x00000000000000020000000000000000 "
                "tick=2048"
            ),
        )

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path | None = None):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {"power_total": 2.0, "target_dir": str(target_dir)}

    monkeypatch.setattr(
        "sdc_agent.differential.compile_static_elf", fake_compile_static_elf
    )
    monkeypatch.setattr("sdc_agent.differential.run_qemu", fake_run_qemu)
    monkeypatch.setattr("sdc_agent.differential.run_gem5", fake_run_gem5)
    monkeypatch.setattr("sdc_agent.differential.McPATBackend", FakeBackend)

    result = run_differential(
        source=source,
        elf=tmp_path / "case-vec.elf",
        gem5_outdir=tmp_path / "m5out-vec",
        fault_model="vector_register_bit_flip",
        fault_target="v0",
        fault_bit=65,
        fault_tick=2048,
    )

    assert result.status == "sdc_found"
    assert result.fault_request is not None
    assert result.fault_request["execution_plane"] == "gem5_scripted"
    assert result.fault_request["observation"]["target_kind"] == "vector_register"
    assert result.fault_request["observation"]["register_name"] == "v0"
