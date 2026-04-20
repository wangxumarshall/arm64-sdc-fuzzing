import json

from pathlib import Path
import platform
import subprocess

import pytest

from sdc_agent.materialize import materialize_testcase, render_materialized_source
from sdc_agent.tooling import resolve_local_tools
from sdc_agent.vault import SDCVault, VaultEntry


def test_render_materialized_source_embeds_digest_and_asm():
    source = render_materialized_source("mov x0, x1\nfmov d0, d1", "seed-1")

    assert "SDC_DIGEST=" in source
    assert "mov x0, x1" in source
    assert "fmov d0, d1" in source
    assert "Materialized from vault testcase: seed-1" in source
    assert "static void sdc_prepare_memory(void)" in source
    assert "static uint8_t sdc_memory[8192]" in source
    assert "str x30, [x16, #240]" in source
    assert "adrp x18, sdc_memory" in source
    assert "str x30, [sp]" in source
    assert "ldr x30, [sp]" in source


def test_materialize_testcase_writes_source_and_updates_metadata(tmp_path):
    db_path = tmp_path / "vault.sqlite3"
    with SDCVault(db_path) as vault:
        vault.upsert_testcase(
            VaultEntry(
                testcase_key="seed-2",
                asm_content="mov x0, x0",
                target_name="armv8_common-armv8_common-aarch64_linux_gcc",
            )
        )
        source_path = materialize_testcase(vault, "seed-2", output_root=tmp_path / "out")

        assert source_path.exists()
        payload = source_path.read_text(encoding="utf-8")
        assert "mov x0, x0" in payload

        row = vault.get_testcase("seed-2")
        assert row is not None
        metadata = json.loads(row["metadata_json"])
        assert metadata["source_path"] == str(source_path.resolve())
        assert metadata["materialized"]["output_root"] == str((tmp_path / "out").resolve())


def test_render_materialized_source_normalizes_gnu_assembler_syntax():
    source = render_materialized_source(
        "\n".join(
            [
                "MOVZ x29, 6189, 0",
                "MOVK x29, 55662, 1",
                "FMLA v11, v6, v4",
                "FMSUB v8, v2, v11, v5",
                "FMADD v0, v1, v2, v3",
            ]
        ),
        "seed-gnu",
    )

    assert "movz x29, #6189, lsl #0" in source
    assert "movk x29, #55662, lsl #16" in source
    assert "fmadd d11, d6, d4, d11" in source
    assert "fmsub d8, d2, d11, d5" in source
    assert "fmadd d0, d1, d2, d3" in source
    assert "MOVK x29, 55662, 1" not in source
    assert "FMLA v11, v6, v4" not in source


def test_render_materialized_source_compiles_directly_when_compiler_is_available(
    tmp_path,
):
    compiler = resolve_local_tools(compiler=None).compiler
    if compiler is None:
        pytest.skip("No usable AArch64 compiler available in test environment")

    source = render_materialized_source(
        "\n".join(
            [
                "MOVZ x29, 6189, 0",
                "MOVK x29, 55662, 1",
                "FMLA v11, v6, v4",
                "FMSUB v8, v2, v11, v5",
            ]
        ),
        "seed-compile",
    )
    source_path = Path(tmp_path / "seed-compile.c")
    elf_path = Path(tmp_path / "seed-compile.elf")
    source_path.write_text(source, encoding="utf-8")

    result = subprocess.run(
        [
            compiler,
            "-static",
            "-O0",
            "-g0",
            "-fno-inline",
            "-o",
            str(elf_path),
            str(source_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert elf_path.exists()

    if platform.machine().lower() not in {"aarch64", "arm64"}:
        return

    run_result = subprocess.run(
        [str(elf_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert run_result.returncode == 0, run_result.stderr
    assert "SDC_DIGEST=" in run_result.stdout
