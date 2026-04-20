import json
from pathlib import Path
import sys

import yaml

PROJECT_MICROPROBE_ROOT = Path(__file__).resolve().parents[4]
PROJECT_MICROPROBE_SRC = PROJECT_MICROPROBE_ROOT / "src"

for extra_path in [PROJECT_MICROPROBE_SRC, PROJECT_MICROPROBE_ROOT]:
    if str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

from targets.arm64.tools.a64_isa_audit import build_report


def _write_xml(path: Path, mnemonic: str, instr_class: str):
    path.write_text(
        (
            '<?xml version="1.0"?>\n'
            f'<instructionsection id="{mnemonic}" title="{mnemonic} -- A64" type="instruction">\n'
            "  <docvars>\n"
            f'    <docvar key="instr-class" value="{instr_class}"/>\n'
            '    <docvar key="isa" value="A64"/>\n'
            f'    <docvar key="mnemonic" value="{mnemonic}"/>\n'
            "  </docvars>\n"
            "</instructionsection>\n"
        ),
        encoding="utf-8",
    )


def _write_multi_mnemonic_xml(path: Path):
    path.write_text(
        (
            '<?xml version="1.0"?>\n'
            '<instructionsection id="CAS" title="CAS, CASA -- A64" type="instruction">\n'
            "  <docvars>\n"
            '    <docvar key="instr-class" value="general"/>\n'
            '    <docvar key="isa" value="A64"/>\n'
            "  </docvars>\n"
            "  <heading>CAS, CASA</heading>\n"
            "  <classes>\n"
            '    <iclass name="General" oneof="1" id="iclass_general" no_encodings="2" isa="A64">\n'
            '      <encoding name="CAS_32" oneofinclass="1" oneof="2" label="">\n'
            "        <docvars>\n"
            '          <docvar key="instr-class" value="general"/>\n'
            '          <docvar key="isa" value="A64"/>\n'
            '          <docvar key="mnemonic" value="CAS"/>\n'
            "        </docvars>\n"
            "      </encoding>\n"
            '      <encoding name="CASA_32" oneofinclass="1" oneof="2" label="">\n'
            "        <docvars>\n"
            '          <docvar key="instr-class" value="general"/>\n'
            '          <docvar key="isa" value="A64"/>\n'
            '          <docvar key="mnemonic" value="CASA"/>\n'
            "        </docvars>\n"
            "      </encoding>\n"
            "    </iclass>\n"
            "  </classes>\n"
            "</instructionsection>\n"
        ),
        encoding="utf-8",
    )


def test_build_report_counts_present_and_missing(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    _write_xml(xml_dir / "add.xml", "ADD", "general")
    _write_xml(xml_dir / "sub.xml", "SUB", "general")
    _write_xml(xml_dir / "nop.xml", "NOP", "system")

    instruction_file = tmp_path / "instruction.yaml"
    instruction_file.write_text(
        yaml.safe_dump(
            [
                {"Name": "ADD_X_IMM_V0", "Mnemonic": "ADD", "Format": "F"},
                {"Name": "RET_V0", "Mnemonic": "RET", "Format": "F"},
            ]
        ),
        encoding="utf-8",
    )

    report = build_report(instruction_file, xml_dir, ["general", "system"])

    assert report["current_unique_mnemonics"] == 2
    assert report["classes"]["general"]["present_unique_mnemonics"] == 1
    assert report["classes"]["general"]["missing_unique_mnemonics"] == 1
    assert report["classes"]["system"]["missing_unique_mnemonics"] == 1
    assert report["classes"]["system"]["missing"][0]["mnemonic"] == "NOP"


def test_build_report_includes_catalog_coverage(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    _write_xml(xml_dir / "add.xml", "ADD", "general")
    _write_xml(xml_dir / "nop.xml", "NOP", "system")

    instruction_file = tmp_path / "instruction.yaml"
    instruction_file.write_text(
        yaml.safe_dump(
            [
                {"Name": "ADD_X_IMM_V0", "Mnemonic": "ADD", "Format": "F"},
            ]
        ),
        encoding="utf-8",
    )

    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(
        json.dumps(
            {
                "instruction_count": 2,
                "encoding_count": 2,
                "unique_mnemonics": ["ADD", "NOP"],
                "docs_pages": 2,
                "docs_mapped_pages": 2,
                "instructions": [
                    {
                        "mnemonic": "ADD",
                        "instr_class": "general",
                        "encodings": [{"name": "ADD_32"}],
                    },
                    {
                        "mnemonic": "NOP",
                        "instr_class": "system",
                        "encodings": [{"name": "NOP"}],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_report(
        instruction_file,
        xml_dir,
        ["general", "system"],
        catalog_file=catalog_file,
    )

    assert report["catalog_unique_mnemonics"] == 2
    assert report["docs_mapped_pages"] == 2
    assert report["classes"]["general"]["catalog_present_unique_mnemonics"] == 1
    assert report["classes"]["system"]["catalog_present_unique_mnemonics"] == 1
    assert report["classes"]["system"]["catalog_missing_unique_mnemonics"] == 0


def test_build_report_counts_encoding_level_mnemonics_from_official_xml(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    _write_multi_mnemonic_xml(xml_dir / "cas.xml")

    instruction_file = tmp_path / "instruction.yaml"
    instruction_file.write_text(
        yaml.safe_dump(
            [
                {"Name": "CAS_X_V0", "Mnemonic": "CAS", "Format": "F"},
            ]
        ),
        encoding="utf-8",
    )

    report = build_report(instruction_file, xml_dir, ["general"])

    assert report["classes"]["general"]["xml_unique_mnemonics"] == 2
    assert report["classes"]["general"]["present_unique_mnemonics"] == 1
    assert report["classes"]["general"]["missing_unique_mnemonics"] == 1
    assert report["classes"]["general"]["missing"][0]["mnemonic"] == "CASA"


def test_build_report_counts_instruction_extensions_from_instruction_props(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    _write_xml(xml_dir / "add.xml", "ADD", "general")
    _write_xml(xml_dir / "wfit.xml", "WFIT", "system")

    instruction_file = tmp_path / "instruction.yaml"
    instruction_file.write_text(
        yaml.safe_dump(
            [
                {"Name": "ADD_X_IMM_V0", "Mnemonic": "ADD", "Format": "F"},
            ]
        ),
        encoding="utf-8",
    )

    props_dir = tmp_path / "instruction_props"
    props_dir.mkdir()
    (props_dir / "armv9_2.yaml").write_text(
        yaml.safe_dump(
            [
                {"Name": "WFIT_V0", "Mnemonic": "WFIT", "Format": "F"},
            ]
        ),
        encoding="utf-8",
    )

    report = build_report(instruction_file, xml_dir, ["general", "system"])

    assert report["current_unique_mnemonics"] == 2
    assert report["classes"]["general"]["present_unique_mnemonics"] == 1
    assert report["classes"]["system"]["present_unique_mnemonics"] == 1
    assert report["classes"]["system"]["missing_unique_mnemonics"] == 0


def test_current_repo_includes_armv92_instruction_definitions(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    for mnemonic, instr_class in [
        ("LD64B", "general"),
        ("ST64B", "general"),
        ("ST64BV", "general"),
        ("ST64BV0", "general"),
        ("WFET", "system"),
        ("WFIT", "system"),
    ]:
        _write_xml(xml_dir / f"{mnemonic.lower()}.xml", mnemonic, instr_class)

    report = build_report(
        PROJECT_MICROPROBE_ROOT / "targets/arm64/isa/armv8-common/instruction.yaml",
        xml_dir,
        ["general", "system"],
    )

    assert report["classes"]["general"]["missing_unique_mnemonics"] == 0
    assert report["classes"]["system"]["missing_unique_mnemonics"] == 0
