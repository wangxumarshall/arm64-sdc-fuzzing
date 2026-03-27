import json

from sdc_materialize import materialize_testcase, render_materialized_source
from sdc_vault import SDCVault, VaultEntry


def test_render_materialized_source_embeds_digest_and_asm():
    source = render_materialized_source("mov x0, x1\nfmov d0, d1", "seed-1")

    assert "SDC_DIGEST=" in source
    assert "mov x0, x1" in source
    assert "fmov d0, d1" in source
    assert "Materialized from vault testcase: seed-1" in source


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
