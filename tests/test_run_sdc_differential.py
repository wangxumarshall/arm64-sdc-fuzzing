from run_sdc_differential import CommandResult, classify, extract_digest


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
