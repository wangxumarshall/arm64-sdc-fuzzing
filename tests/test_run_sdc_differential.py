from pathlib import Path

from run_sdc_differential import (
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
        return CommandResult(["gem5"], 0, "SDC_HASH=2222", "")

    class FakeBackend:
        def __init__(self, template_profile: str, mcpat_binary: Path | None = None):
            self.template_profile = template_profile
            self.mcpat_binary = mcpat_binary

        def run(self, target_dir: Path):
            return {"power_total": 3.5, "target_dir": str(target_dir)}

    monkeypatch.setattr(
        "run_sdc_differential.compile_static_elf", fake_compile_static_elf
    )
    monkeypatch.setattr("run_sdc_differential.run_qemu", fake_run_qemu)
    monkeypatch.setattr("run_sdc_differential.run_gem5", fake_run_gem5)
    monkeypatch.setattr("run_sdc_differential.McPATBackend", FakeBackend)

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
