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
