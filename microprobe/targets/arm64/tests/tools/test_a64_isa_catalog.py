import json
from pathlib import Path

from microprobe.utils.arm64_isa_catalog import (
    PROFILE_ALL_GENERATABLE,
    PROFILE_EXECUTABLE_SAFE,
    build_catalog,
    build_catalog_summary,
    iter_catalog_encodings,
    render_sample_asm,
    save_catalog,
    validate_sequence_asm,
)


def _write_add_xml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0"?>
<instructionsection id="ADD_addsub_shift" title="ADD (shifted register) -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="general"/>
    <docvar key="isa" value="A64"/>
    <docvar key="mnemonic" value="ADD"/>
  </docvars>
  <heading>ADD (shifted register)</heading>
  <desc><brief><para>Add optionally-shifted register</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="General" oneof="1" id="iclass_general" no_encodings="1" isa="A64">
      <encoding name="ADD_32_addsub_shift" oneofinclass="1" oneof="1" label="32-bit">
        <docvars>
          <docvar key="instr-class" value="general"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="ADD"/>
        </docvars>
        <asmtemplate>
          <text>ADD </text>
          <a hover="Is the 32-bit name of the general-purpose destination register, encoded in the &quot;Rd&quot; field." link="Wd">&lt;Wd&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the first general-purpose source register, encoded in the &quot;Rn&quot; field." link="Wn">&lt;Wn&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the second general-purpose source register, encoded in the &quot;Rm&quot; field." link="Wm">&lt;Wm&gt;</a>
          <text>{, </text>
          <a hover="Is the optional shift type to be applied to the second source operand." link="shift">&lt;shift&gt;</a>
          <text> #</text>
          <a hover="For the 32-bit variant: is the shift amount, in the range 0 to 31, defaulting to 0." link="amount">&lt;amount&gt;</a>
          <text>}</text>
        </asmtemplate>
      </encoding>
    </iclass>
  </classes>
</instructionsection>
""",
        encoding="utf-8",
    )


def _write_svc_xml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0"?>
<instructionsection id="SVC" title="SVC -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="system"/>
    <docvar key="isa" value="A64"/>
    <docvar key="mnemonic" value="SVC"/>
  </docvars>
  <heading>SVC</heading>
  <desc><brief><para>Supervisor call</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="System" oneof="1" id="iclass_system" no_encodings="1" isa="A64">
      <encoding name="SVC_EX_exception" oneofinclass="1" oneof="1" label="">
        <docvars>
          <docvar key="instr-class" value="system"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="SVC"/>
        </docvars>
        <asmtemplate>
          <text>SVC #</text>
          <a hover="Is a 16-bit unsigned immediate, in the range 0 to 65535, encoded in the &quot;imm16&quot; field." link="imm">&lt;imm&gt;</a>
        </asmtemplate>
      </encoding>
    </iclass>
  </classes>
</instructionsection>
""",
        encoding="utf-8",
    )


def _write_cas_xml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0"?>
<instructionsection id="CAS" title="CAS, CASA, CASAL, CASL -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="general"/>
    <docvar key="isa" value="A64"/>
  </docvars>
  <heading>CAS, CASA, CASAL, CASL</heading>
  <desc><brief><para>Compare and swap word or doubleword</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="General" oneof="1" id="iclass_general" no_encodings="2" isa="A64">
      <encoding name="CAS_32" oneofinclass="1" oneof="2" label="32-bit">
        <docvars>
          <docvar key="instr-class" value="general"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="CAS"/>
        </docvars>
        <asmtemplate>
          <text>CAS </text>
          <a hover="Is the 32-bit name of the first general-purpose register." link="Ws">&lt;Ws&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the second general-purpose register." link="Wt">&lt;Wt&gt;</a>
          <text>, [</text>
          <a hover="Is the 64-bit name of the general-purpose base register or stack pointer." link="Xn|SP">&lt;Xn|SP&gt;</a>
          <text>]</text>
        </asmtemplate>
      </encoding>
      <encoding name="CASA_32" oneofinclass="1" oneof="2" label="32-bit">
        <docvars>
          <docvar key="instr-class" value="general"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="CASA"/>
        </docvars>
        <asmtemplate>
          <text>CASA </text>
          <a hover="Is the 32-bit name of the first general-purpose register." link="Ws">&lt;Ws&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the second general-purpose register." link="Wt">&lt;Wt&gt;</a>
          <text>, [</text>
          <a hover="Is the 64-bit name of the general-purpose base register or stack pointer." link="Xn|SP">&lt;Xn|SP&gt;</a>
          <text>]</text>
        </asmtemplate>
      </encoding>
    </iclass>
  </classes>
</instructionsection>
""",
        encoding="utf-8",
    )


def _write_add_immediate_xml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0"?>
<instructionsection id="ADD_addsub_imm" title="ADD (immediate) -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="general"/>
    <docvar key="isa" value="A64"/>
    <docvar key="mnemonic" value="ADD"/>
  </docvars>
  <heading>ADD (immediate)</heading>
  <desc><brief><para>Add immediate</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="General" oneof="1" id="iclass_general" no_encodings="1" isa="A64">
      <encoding name="ADD_32_addsub_imm" oneofinclass="1" oneof="1" label="32-bit">
        <docvars>
          <docvar key="instr-class" value="general"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="ADD"/>
        </docvars>
        <asmtemplate>
          <text>ADD </text>
          <a hover="Is the 32-bit name of the destination general-purpose register or stack pointer, encoded in the &quot;Rd&quot; field." link="Wd|WSP">&lt;Wd|WSP&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the source general-purpose register or stack pointer, encoded in the &quot;Rn&quot; field." link="Wn|WSP">&lt;Wn|WSP&gt;</a>
          <text>, #</text>
          <a hover="Is an unsigned immediate, in the range 0 to 4095, encoded in the &quot;imm12&quot; field." link="imm">&lt;imm&gt;</a>
          <text>{, </text>
          <a hover="Is the optional left shift to apply to the immediate, defaulting to LSL #0 and sh &lt;shift&gt; 0 LSL #0 1 LSL #12" link="shift">&lt;shift&gt;</a>
          <text>}</text>
        </asmtemplate>
      </encoding>
    </iclass>
  </classes>
</instructionsection>
""",
        encoding="utf-8",
    )


def _write_add_extended_xml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0"?>
<instructionsection id="ADD_addsub_ext" title="ADD (extended register) -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="general"/>
    <docvar key="isa" value="A64"/>
    <docvar key="mnemonic" value="ADD"/>
  </docvars>
  <heading>ADD (extended register)</heading>
  <desc><brief><para>Add extended register</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="General" oneof="1" id="iclass_general" no_encodings="1" isa="A64">
      <encoding name="ADD_32_addsub_ext" oneofinclass="1" oneof="1" label="32-bit">
        <docvars>
          <docvar key="instr-class" value="general"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="ADD"/>
        </docvars>
        <asmtemplate>
          <text>ADD </text>
          <a hover="Is the 32-bit name of the destination general-purpose register or stack pointer, encoded in the &quot;Rd&quot; field." link="Wd|WSP">&lt;Wd|WSP&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the first source general-purpose register or stack pointer, encoded in the &quot;Rn&quot; field." link="Wn|WSP">&lt;Wn|WSP&gt;</a>
          <text>, </text>
          <a hover="Is the 32-bit name of the second general-purpose source register, encoded in the &quot;Rm&quot; field." link="Wm">&lt;Wm&gt;</a>
          <text>{, </text>
          <a hover="For the &quot;32-bit&quot; variant: is the extension to be applied to the second source operand. In all other cases &lt;extend&gt; is required and must be UXTW when &quot;option&quot; is '010'." link="extend">&lt;extend&gt;</a>
          <text> {#</text>
          <a hover="Is the left shift amount to be applied after extension in the range 0 to 4, defaulting to 0, encoded in the &quot;imm3&quot; field." link="amount">&lt;amount&gt;</a>
          <text>}}</text>
        </asmtemplate>
      </encoding>
    </iclass>
  </classes>
</instructionsection>
""",
        encoding="utf-8",
    )


def test_build_catalog_parses_xml_docs_and_execution_metadata(tmp_path):
    xml_dir = tmp_path / "xml"
    docs_dir = tmp_path / "docs"
    xml_dir.mkdir()
    docs_dir.mkdir()

    _write_add_xml(xml_dir / "add.xml")
    _write_svc_xml(xml_dir / "svc.xml")
    (docs_dir / "Arithmetic-ADD_shifted_register.md").write_text(
        "# ADD (shifted register)\n", encoding="utf-8"
    )
    (docs_dir / "System-SVC.md").write_text("# SVC\n", encoding="utf-8")

    catalog = build_catalog(xml_dir, docs_dir=docs_dir, classes=("general", "system"))
    summary = build_catalog_summary(catalog)

    assert catalog["instruction_count"] == 2
    assert catalog["encoding_count"] == 2
    assert summary["docs_mapped_pages"] == 2

    add_instruction = next(
        item for item in catalog["instructions"] if item["mnemonic"] == "ADD"
    )
    add_encoding = add_instruction["encodings"][0]
    assert add_encoding["sample_asm"] == "ADD w0, w1, w2, lsl #0"
    assert add_encoding["executable"] is True

    svc_instruction = next(
        item for item in catalog["instructions"] if item["mnemonic"] == "SVC"
    )
    svc_encoding = svc_instruction["encodings"][0]
    assert svc_encoding["trap_like"] is True
    assert svc_encoding["executable"] is False


def test_catalog_can_be_saved_filtered_and_validated(tmp_path):
    xml_dir = tmp_path / "xml"
    docs_dir = tmp_path / "docs"
    xml_dir.mkdir()
    docs_dir.mkdir()

    _write_add_xml(xml_dir / "add.xml")
    (docs_dir / "Arithmetic-ADD_shifted_register.md").write_text(
        "# ADD (shifted register)\n", encoding="utf-8"
    )

    catalog = build_catalog(xml_dir, docs_dir=docs_dir, classes=("general",))
    catalog_path = save_catalog(catalog, tmp_path / "catalog.json")
    loaded = json.loads(catalog_path.read_text(encoding="utf-8"))

    all_encodings = list(
        iter_catalog_encodings(loaded, profile_name=PROFILE_ALL_GENERATABLE)
    )
    safe_encodings = list(
        iter_catalog_encodings(loaded, profile_name=PROFILE_EXECUTABLE_SAFE)
    )

    assert len(all_encodings) == 1
    assert len(safe_encodings) == 1

    validation = validate_sequence_asm(safe_encodings)
    assert validation["ok"] is True
    assert "ADD w0, w1, w2, lsl #0" in validation["asm_text"]


def test_build_catalog_uses_encoding_level_mnemonics_when_page_root_lacks_one(tmp_path):
    xml_dir = tmp_path / "xml"
    docs_dir = tmp_path / "docs"
    xml_dir.mkdir()
    docs_dir.mkdir()

    _write_cas_xml(xml_dir / "cas.xml")
    (docs_dir / "Atomic-CAS_CASA_CASAL_CASL.md").write_text(
        "# CAS, CASA, CASAL, CASL\n", encoding="utf-8"
    )

    catalog = build_catalog(xml_dir, docs_dir=docs_dir, classes=("general",))

    assert catalog["instruction_count"] == 1
    assert catalog["docs_mapped_pages"] == 1
    assert set(catalog["unique_mnemonics"]) == {"CAS", "CASA"}
    instruction = catalog["instructions"][0]
    assert instruction["mnemonics"] == ["CAS", "CASA"]
    assert instruction["doc_path"].endswith("Atomic-CAS_CASA_CASAL_CASL.md")


def test_render_sample_asm_respects_base_shift_and_extend_constraints(tmp_path):
    xml_dir = tmp_path / "xml"
    docs_dir = tmp_path / "docs"
    xml_dir.mkdir()
    docs_dir.mkdir()

    _write_add_immediate_xml(xml_dir / "add_imm.xml")
    _write_add_extended_xml(xml_dir / "add_ext.xml")
    (docs_dir / "Arithmetic-ADD_immediate.md").write_text(
        "# ADD (immediate)\n", encoding="utf-8"
    )
    (docs_dir / "Arithmetic-ADD_extended_register.md").write_text(
        "# ADD (extended register)\n", encoding="utf-8"
    )

    catalog = build_catalog(xml_dir, docs_dir=docs_dir, classes=("general",))
    encodings = {
        encoding["name"]: encoding
        for instruction in catalog["instructions"]
        for encoding in instruction["encodings"]
    }

    add_imm = render_sample_asm(encodings["ADD_32_addsub_imm"])
    add_ext = render_sample_asm(encodings["ADD_32_addsub_ext"])

    assert add_imm == "ADD w0, w1, #0, lsl #0"
    assert add_ext == "ADD w0, w1, w2, uxtw #0"

    imm_validation = validate_sequence_asm([encodings["ADD_32_addsub_imm"]])
    ext_validation = validate_sequence_asm([encodings["ADD_32_addsub_ext"]])
    assert imm_validation["ok"] is True
    assert ext_validation["ok"] is True


def test_validate_sequence_asm_enables_required_arch_extensions():
    validation = validate_sequence_asm(
        [
            {
                "sample_asm": "ABS w0, w1",
                "feature_tags": ["FEAT_CSSC"],
            },
            {
                "sample_asm": "ADDG x0, x1, #0, #0",
                "feature_tags": ["FEAT_MTE"],
            },
        ]
    )

    assert validation["ok"] is True
    assert "cssc" in validation["arch_extensions"]
    assert "memtag" in validation["arch_extensions"]
    assert ".arch_extension cssc" in validation["asm_text"]
    assert ".arch_extension memtag" in validation["asm_text"]
