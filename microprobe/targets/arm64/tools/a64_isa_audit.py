#!/usr/bin/env python3
"""Audit the local ARM64 ISA definitions against the official Arm A64 XML."""

from __future__ import annotations

import argparse
import json
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MICROPROBE_SRC = REPO_ROOT / "microprobe" / "src"
if str(REPO_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(REPO_ROOT))
if str(MICROPROBE_SRC) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(MICROPROBE_SRC))

from microprobe.utils.arm64_isa_catalog import load_catalog  # noqa: E402

OFFICIAL_XML_URL = (
    "https://developer.arm.com/-/cdn-downloads/permalink/"
    "Exploration-Tools-A64-ISA/ISA_A64/ISA_A64_xml_A_profile-2025-09_ASL1.tar.gz"
)
DEFAULT_XML_DIR = Path(".codex_tmp/arm_a64_xml/xml")
DEFAULT_INSTRUCTION_FILE = Path("targets/arm64/isa/armv8-common/instruction.yaml")
DEFAULT_CATALOG_FILE = Path("targets/arm64/isa/armv8-common/arm_a64_catalog.json")


def _safe_extractall(tf: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in tf.getmembers():
        if member.islnk() or member.issym():
            raise ValueError(
                f"Refusing to extract link member '{member.name}' from '{tf.name}'"
            )

        target = (destination / member.name).resolve()
        if target != destination and destination not in target.parents:
            raise ValueError(
                f"Refusing to extract '{member.name}' outside '{destination}'"
            )

    tf.extractall(destination)


def _download_official_xml(xml_dir: Path) -> Path:
    xml_dir.parent.mkdir(parents=True, exist_ok=True)
    archive = xml_dir.parent / "arm_a64.tar.gz"
    if not archive.exists():
        print(f"[audit] downloading official XML from {OFFICIAL_XML_URL}")
        urllib.request.urlretrieve(OFFICIAL_XML_URL, archive)
    if not xml_dir.exists():
        print(f"[audit] extracting {archive}")
        with tarfile.open(archive, "r:gz") as tf:
            _safe_extractall(tf, xml_dir.parent)
        extracted = xml_dir.parent / "ISA_A64_xml_A_profile-2025-09_ASL1"
        if extracted.exists():
            extracted.rename(xml_dir)
    return xml_dir


def _load_current_mnemonics(instruction_file: Path) -> Counter:
    with instruction_file.open("r", encoding="utf-8") as stream:
        instructions = yaml.safe_load(stream) or []
    return Counter(item["Mnemonic"] for item in instructions)


def _parse_official_xml(
    xml_dir: Path, classes: Iterable[str]
) -> Tuple[Dict[str, List[Tuple[str, str]]], Counter]:
    wanted = set(classes)
    by_class: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    class_counts: Counter = Counter()

    for xml_file in sorted(xml_dir.glob("*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue

        docvars = {
            elem.attrib.get("key"): elem.attrib.get("value")
            for elem in root.findall("./docvars/docvar")
        }

        if docvars.get("isa") != "A64":
            continue

        instr_class = docvars.get("instr-class")
        if instr_class not in wanted:
            continue

        mnemonic = docvars.get("alias_mnemonic") or docvars.get("mnemonic")
        if mnemonic is None:
            continue

        by_class[instr_class].append((mnemonic, xml_file.name))
        class_counts[instr_class] += 1

    return by_class, class_counts


def build_report(
    instruction_file: Path,
    xml_dir: Path,
    classes: Iterable[str],
    catalog_file: Path | None = None,
) -> Dict[str, object]:
    current = _load_current_mnemonics(instruction_file)
    official, class_counts = _parse_official_xml(xml_dir, classes)
    catalog_mnemonics: Counter = Counter()
    catalog_classes: Dict[str, set[str]] = defaultdict(set)
    catalog_summary: Dict[str, object] = {}
    if catalog_file is not None and catalog_file.exists():
        catalog = load_catalog(catalog_file)
        catalog_summary = {
            "catalog_instruction_count": int(catalog.get("instruction_count", 0)),
            "catalog_encoding_count": int(catalog.get("encoding_count", 0)),
            "catalog_unique_mnemonics": len(catalog.get("unique_mnemonics", [])),
            "docs_pages": int(catalog.get("docs_pages", 0)),
            "docs_mapped_pages": int(catalog.get("docs_mapped_pages", 0)),
        }
        for instruction in catalog.get("instructions", []):
            mnemonic = str(instruction.get("mnemonic", ""))
            instr_class = str(instruction.get("instr_class", ""))
            if mnemonic:
                catalog_mnemonics[mnemonic] += 1
            if mnemonic and instr_class:
                catalog_classes[instr_class].add(mnemonic)

    report: Dict[str, object] = {
        "instruction_file": str(instruction_file),
        "xml_dir": str(xml_dir),
        "current_entries": sum(current.values()),
        "current_unique_mnemonics": len(current),
        "current_mnemonics": sorted(current),
        "classes": {},
    }
    report.update(catalog_summary)

    for instr_class, entries in sorted(official.items()):
        unique: Dict[str, str] = {}
        for mnemonic, filename in entries:
            unique.setdefault(mnemonic, filename)

        missing = sorted(set(unique) - set(current))
        present = sorted(set(unique) & set(current))
        catalog_present = sorted(set(unique) & set(catalog_classes.get(instr_class, set())))
        catalog_missing = sorted(set(unique) - set(catalog_classes.get(instr_class, set())))
        report["classes"][instr_class] = {
            "xml_entries": class_counts[instr_class],
            "xml_unique_mnemonics": len(unique),
            "present_unique_mnemonics": len(present),
            "missing_unique_mnemonics": len(missing),
            "catalog_present_unique_mnemonics": len(catalog_present),
            "catalog_missing_unique_mnemonics": len(catalog_missing),
            "missing": [
                {"mnemonic": mnemonic, "xml_file": unique[mnemonic]}
                for mnemonic in missing
            ],
            "catalog_missing": [
                {"mnemonic": mnemonic, "xml_file": unique[mnemonic]}
                for mnemonic in catalog_missing
            ],
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the local ARM64 instruction set definition against the "
            "official Arm A64 XML catalog."
        )
    )
    parser.add_argument(
        "--instruction-file",
        default=str(DEFAULT_INSTRUCTION_FILE),
        help="Path to the local ARM64 instruction.yaml file.",
    )
    parser.add_argument(
        "--xml-dir",
        default=str(DEFAULT_XML_DIR),
        help="Path to an extracted Arm A64 XML directory.",
    )
    parser.add_argument(
        "--catalog-file",
        default=str(DEFAULT_CATALOG_FILE),
        help="Path to a generated ARM64 catalog JSON file.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the official XML archive when --xml-dir does not exist.",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=["general", "system", "float", "advsimd"],
        help="Official Arm instruction classes to include in the audit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full report as JSON.",
    )
    parser.add_argument(
        "--top-missing",
        type=int,
        default=25,
        help="Number of missing mnemonics to show per class in text mode.",
    )
    args = parser.parse_args()

    instruction_file = Path(args.instruction_file)
    xml_dir = Path(args.xml_dir)

    if not xml_dir.exists():
        if not args.download:
            raise SystemExit(
                f"XML directory '{xml_dir}' does not exist. Re-run with --download."
            )
        _download_official_xml(xml_dir)

    report = build_report(
        instruction_file,
        xml_dir,
        args.classes,
        catalog_file=Path(args.catalog_file) if args.catalog_file else None,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print("ARM64 ISA audit")
    print(f"  instruction file : {instruction_file}")
    print(f"  official xml dir : {xml_dir}")
    print(f"  current entries  : {report['current_entries']}")
    print(f"  current mnemonics: {report['current_unique_mnemonics']}")
    if "catalog_unique_mnemonics" in report:
        print(f"  catalog encodings: {report['catalog_encoding_count']}")
        print(f"  catalog mnemonics: {report['catalog_unique_mnemonics']}")
        print(
            f"  docs mapped      : "
            f"{report['docs_mapped_pages']}/{report['docs_pages']}"
        )

    for instr_class, payload in report["classes"].items():
        print(f"\n[{instr_class}]")
        print(f"  xml unique   : {payload['xml_unique_mnemonics']}")
        print(f"  present      : {payload['present_unique_mnemonics']}")
        print(f"  missing      : {payload['missing_unique_mnemonics']}")
        if "catalog_present_unique_mnemonics" in payload:
            print(f"  catalog      : {payload['catalog_present_unique_mnemonics']}")
            print(f"  cat missing  : {payload['catalog_missing_unique_mnemonics']}")
        for missing in payload["missing"][: args.top_missing]:
            print(f"    - {missing['mnemonic']} ({missing['xml_file']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
