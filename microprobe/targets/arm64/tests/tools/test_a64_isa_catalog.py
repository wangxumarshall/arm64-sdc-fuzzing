import json
from pathlib import Path

from microprobe.utils.arm64_isa_catalog import (
    DEFAULT_CATALOG_PATH,
    PROFILE_ALL_GENERATABLE,
    PROFILE_ARMV82_TO_ARMV92_EXECUTABLE,
    PROFILE_ARMV82_TO_ARMV92_GENERATABLE,
    PROFILE_EXECUTABLE_SAFE,
    build_catalog,
    build_catalog_summary,
    iter_catalog_encodings,
    load_catalog,
    render_sample_asm,
    save_catalog,
    validate_sequence_asm,
)


def _catalog_encodings_by_mnemonic(catalog):
    return {
        str(encoding["mnemonic"]): encoding
        for instruction in catalog["instructions"]
        for encoding in instruction["encodings"]
    }


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


def _write_armv92_xml(path: Path, *, mnemonic: str, instr_class: str, feature: str, template: str, description: str) -> None:
    path.write_text(
        f"""<?xml version="1.0"?>
<instructionsection id="{mnemonic}" title="{mnemonic} -- A64" type="instruction">
  <docvars>
    <docvar key="instr-class" value="{instr_class}"/>
    <docvar key="isa" value="A64"/>
    <docvar key="mnemonic" value="{mnemonic}"/>
  </docvars>
  <heading>{mnemonic}</heading>
  <desc><brief><para>{description}</para></brief></desc>
  <alias_list howmany="0"/>
  <classes>
    <iclass name="{instr_class.title()}" oneof="1" id="iclass_{instr_class}" no_encodings="1" isa="A64">
      <arch_variants>
        <arch_variant feature="{feature}"/>
      </arch_variants>
      <encoding name="{mnemonic}_enc" oneofinclass="1" oneof="1" label="">
        <docvars>
          <docvar key="instr-class" value="{instr_class}"/>
          <docvar key="isa" value="A64"/>
          <docvar key="mnemonic" value="{mnemonic}"/>
        </docvars>
        <asmtemplate>
{template}
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
    assert validation["validation_mode"] in {
        "strict",
        "fallback_assembler",
        "toolchain_limited",
    }


def test_real_catalog_derives_minimum_arch_across_armv82_to_armv92():
    catalog = load_catalog(DEFAULT_CATALOG_PATH)
    encodings = _catalog_encodings_by_mnemonic(catalog)

    assert encodings["FMLAL"]["minimum_arch"] == "armv8.2-a"
    assert encodings["FCMLA"]["minimum_arch"] == "armv8.3-a"
    assert encodings["SDOT"]["minimum_arch"] == "armv8.4-a"
    assert encodings["AXFLAG"]["minimum_arch"] == "armv8.5-a"
    assert encodings["BFCVT"]["minimum_arch"] == "armv8.6-a"
    assert encodings["WFET"]["minimum_arch"] == "armv8.7-a"
    assert encodings["CPYFP"]["minimum_arch"] == "armv8.8-a"
    assert encodings["LDGM"]["minimum_arch"] == "armv8.9-a"
    assert encodings["SMSTART"]["minimum_arch"] == "armv9-a"


def test_armv82_to_armv92_profiles_filter_catalog_window():
    catalog = load_catalog(DEFAULT_CATALOG_PATH)

    generatable = list(
        iter_catalog_encodings(
            catalog,
            profile_name=PROFILE_ARMV82_TO_ARMV92_GENERATABLE,
        )
    )
    executable = list(
        iter_catalog_encodings(
            catalog,
            profile_name=PROFILE_ARMV82_TO_ARMV92_EXECUTABLE,
        )
    )

    minimum_arches = {encoding["minimum_arch"] for encoding in generatable}
    mnemonics = {encoding["mnemonic"] for encoding in generatable}

    assert generatable
    assert executable
    assert minimum_arches.issubset(
        {
            "armv8.2-a",
            "armv8.3-a",
            "armv8.4-a",
            "armv8.5-a",
            "armv8.6-a",
            "armv8.7-a",
            "armv8.8-a",
            "armv8.9-a",
            "armv9-a",
            "armv9.1-a",
            "armv9.2-a",
        }
    )
    assert "ADD" not in mnemonics
    assert {
        "FMLAL",
        "FCMLA",
        "SDOT",
        "AXFLAG",
        "BFCVT",
        "WFET",
        "CPYFP",
        "LDGM",
        "SMSTART",
    }.issubset(mnemonics)
    assert all(encoding["executable"] for encoding in executable)


def test_build_catalog_supports_armv92_ls64_and_wfxt_sequences(tmp_path):
    xml_dir = tmp_path / "xml"
    docs_dir = tmp_path / "docs"
    xml_dir.mkdir()
    docs_dir.mkdir()

    _write_armv92_xml(
        xml_dir / "ld64b.xml",
        mnemonic="LD64B",
        instr_class="general",
        feature="FEAT_LS64",
        description="Single-copy Atomic 64-byte Load",
        template="""          <text>LD64B </text>
          <a hover="Is the 64-bit name of the first general-purpose register to be transferred, encoded in the &quot;Rt&quot; field." link="Xt">&lt;Xt&gt;</a>
          <text>, [</text>
          <a hover="Is the 64-bit name of the general-purpose base register or stack pointer, encoded in the &quot;Rn&quot; field." link="Xn|SP">&lt;Xn|SP&gt;</a>
          <text> {, #0}]</text>""",
    )
    _write_armv92_xml(
        xml_dir / "st64bv.xml",
        mnemonic="ST64BV",
        instr_class="general",
        feature="FEAT_LS64_V",
        description="Single-copy Atomic 64-byte Store with Return",
        template="""          <text>ST64BV </text>
          <a hover="Is the 64-bit name of the general-purpose register into which the status result of this instruction is written, encoded in the &quot;Rs&quot; field." link="Xs">&lt;Xs&gt;</a>
          <text>, </text>
          <a hover="Is the 64-bit name of the first general-purpose register to be transferred, encoded in the &quot;Rt&quot; field." link="Xt">&lt;Xt&gt;</a>
          <text>, [</text>
          <a hover="Is the 64-bit name of the general-purpose base register or stack pointer, encoded in the &quot;Rn&quot; field." link="Xn|SP">&lt;Xn|SP&gt;</a>
          <text>]</text>""",
    )
    _write_armv92_xml(
        xml_dir / "wfet.xml",
        mnemonic="WFET",
        instr_class="system",
        feature="FEAT_WFxT",
        description=(
            "Wait For Event with Timeout. The execution of a WFET instruction "
            "can be trapped to a higher Exception level."
        ),
        template="""          <text>WFET </text>
          <a hover="Is the 64-bit name of the general-purpose source register, encoded in the &quot;Rd&quot; field." link="Xt">&lt;Xt&gt;</a>""",
    )
    _write_armv92_xml(
        xml_dir / "wfit.xml",
        mnemonic="WFIT",
        instr_class="system",
        feature="FEAT_WFxT",
        description=(
            "Wait For Interrupt with Timeout. The execution of a WFIT instruction "
            "can be trapped to a higher Exception level."
        ),
        template="""          <text>WFIT </text>
          <a hover="Is the 64-bit name of the general-purpose source register, encoded in the &quot;Rd&quot; field." link="Xt">&lt;Xt&gt;</a>""",
    )

    catalog = build_catalog(xml_dir, docs_dir=docs_dir, classes=("general", "system"))
    encodings = {
        encoding["mnemonic"]: encoding
        for instruction in catalog["instructions"]
        for encoding in instruction["encodings"]
    }

    assert encodings["LD64B"]["arch_extensions"] == ["ls64"]
    assert encodings["LD64B"]["sample_asm"] == "LD64B x0, [x1]"
    assert "#0" not in encodings["LD64B"]["sample_asm"]
    assert encodings["ST64BV"]["arch_extensions"] == ["ls64"]
    assert encodings["WFET"]["minimum_arch"] == "armv8.7-a"
    assert encodings["WFET"]["trap_like"] is False
    assert encodings["WFET"]["executable"] is True
    assert encodings["WFIT"]["minimum_arch"] == "armv8.7-a"
    assert encodings["WFIT"]["trap_like"] is False
    assert encodings["WFIT"]["executable"] is True

    validation = validate_sequence_asm(
        [
            encodings["LD64B"],
            encodings["ST64BV"],
            encodings["WFET"],
            encodings["WFIT"],
        ]
    )
    assert validation["ok"] is True
    assert ".arch armv8.7-a" in validation["asm_text"]
    assert ".arch_extension ls64" in validation["asm_text"]
    assert "LD64B x0, [x1]" in validation["asm_text"]
    assert validation["validation_mode"] in {
        "strict",
        "fallback_assembler",
        "toolchain_limited",
    }


def test_load_catalog_normalizes_legacy_armv92_metadata(tmp_path):
    legacy_catalog = {
        "instruction_count": 2,
        "encoding_count": 2,
        "unique_mnemonics": ["LD64B", "WFET"],
        "instructions": [
            {
                "mnemonic": "LD64B",
                "instr_class": "general",
                "title": "LD64B",
                "description": "Single-copy Atomic 64-byte Load",
                "encodings": [
                    {
                        "name": "LD64B_enc",
                        "mnemonic": "LD64B",
                        "instr_class": "general",
                        "feature_tags": ["FEAT_LS64"],
                        "parts": [
                            {"kind": "text", "text": "LD64B "},
                            {
                                "kind": "operand",
                                "text": "<Xt>",
                                "hover": 'Is the 64-bit name of the first general-purpose register to be transferred, encoded in the "Rt" field.',
                                "link": "Xt",
                            },
                            {"kind": "text", "text": ", ["},
                            {
                                "kind": "operand",
                                "text": "<Xn|SP>",
                                "hover": 'Is the 64-bit name of the general-purpose base register or stack pointer, encoded in the "Rn" field.',
                                "link": "Xn|SP",
                            },
                            {"kind": "text", "text": " {, #0}]"},
                        ],
                        "sample_asm": "LD64B x0, [sp, #0]",
                    }
                ],
            },
            {
                "mnemonic": "WFET",
                "instr_class": "system",
                "title": "WFET",
                "description": (
                    "Wait For Event with Timeout. The execution of a WFET "
                    "instruction can be trapped to a higher Exception level."
                ),
                "encodings": [
                    {
                        "name": "WFET_enc",
                        "mnemonic": "WFET",
                        "instr_class": "system",
                        "feature_tags": ["FEAT_WFxT"],
                        "parts": [
                            {"kind": "text", "text": "WFET "},
                            {
                                "kind": "operand",
                                "text": "<Xt>",
                                "hover": 'Is the 64-bit name of the general-purpose source register, encoded in the "Rd" field.',
                                "link": "Xt",
                            },
                        ],
                        "trap_like": True,
                        "executable": False,
                    }
                ],
            },
        ],
    }

    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(legacy_catalog), encoding="utf-8")

    normalized = load_catalog(catalog_path)
    encodings = {
        encoding["mnemonic"]: encoding
        for instruction in normalized["instructions"]
        for encoding in instruction["encodings"]
    }

    assert encodings["LD64B"]["arch_extensions"] == ["ls64"]
    assert encodings["LD64B"]["sample_asm"] == "LD64B x0, [x1]"
    assert encodings["WFET"]["minimum_arch"] == "armv8.7-a"
    assert encodings["WFET"]["trap_like"] is False
    assert encodings["WFET"]["executable"] is True
