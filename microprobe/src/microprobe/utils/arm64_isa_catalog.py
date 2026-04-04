"""Utilities for building and consuming an ARM64/A64 instruction catalog."""

from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence


DEFAULT_CLASSES = ("general", "system", "float", "advsimd")
_MODULE_PATH = Path(__file__).resolve()
MICROPROBE_TREE = _MODULE_PATH.parents[3]
REPO_ROOT = MICROPROBE_TREE.parent
DEFAULT_DOCS_DIR = REPO_ROOT / "docs" / "armv8-isa"
DEFAULT_CATALOG_PATH = (
    MICROPROBE_TREE
    / "targets"
    / "arm64"
    / "isa"
    / "armv8-common"
    / "arm_a64_catalog.json"
)

PROFILE_ALL_GENERATABLE = "ALL_GENERATABLE"
PROFILE_EXECUTABLE_SAFE = "EXECUTABLE_SAFE"
PROFILE_KUNPENG920_STRESS = "KUNPENG920_STRESS"

_DEFAULT_BRANCH_LABEL = ".Lmicroprobe_catalog_target"
_TRAP_MNEMONICS = {
    "BRK",
    "DCPS1",
    "DCPS2",
    "DCPS3",
    "DRPS",
    "ERET",
    "HLT",
    "HVC",
    "SMC",
    "SVC",
    "UDF",
}
_SAFE_SYSTEM_MNEMONICS = {
    "BTI",
    "CLREX",
    "CSDB",
    "DGH",
    "DMB",
    "DSB",
    "ESB",
    "ISB",
    "NOP",
    "PRFM",
    "PSB",
    "PSSBB",
    "SB",
    "SEV",
    "SEVL",
    "SSBB",
    "TSB",
    "WFE",
    "WFI",
    "WFIT",
    "YIELD",
}
_KUNPENG_MEMORY_PREFIXES = (
    "CAS",
    "LD",
    "PRFM",
    "ST",
    "SWP",
)
_KUNPENG_BRANCH_PREFIXES = (
    "B",
    "BL",
    "BR",
    "CB",
    "TB",
    "RET",
)
_KUNPENG_SIMD_PREFIXES = (
    "F",
    "CRC",
    "SHA",
    "AES",
)
_WHITESPACE_RE = re.compile(r"\s+")
_ALT_RE = re.compile(r"\(([^()|]+)\|[^()]+\)")


def _normalize_space(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "")).strip()


def _normalize_heading(text: str) -> str:
    text = _normalize_space(text)
    text = text.replace(" -- A64", "")
    return text


def _docvars(node: ET.Element) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for elem in node.findall("./docvars/docvar"):
        key = elem.attrib.get("key")
        value = elem.attrib.get("value")
        if key and value is not None:
            payload[key] = value
    return payload


def _load_docs_index(docs_dir: Path) -> Dict[str, str]:
    docs_index: Dict[str, str] = {}
    if not docs_dir.exists():
        return docs_index

    for path in sorted(docs_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = ""
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if not title:
            continue
        docs_index[_normalize_heading(title)] = str(path.resolve())
    return docs_index


def _parse_aliases(root: ET.Element) -> List[Dict[str, str]]:
    aliases: List[Dict[str, str]] = []
    alias_root = root.find("./alias_list")
    if alias_root is None:
        return aliases

    for aliasref in alias_root.findall("./aliasref"):
        aliases.append(
            {
                "text": _normalize_space("".join(aliasref.itertext())),
                "alias_page_id": aliasref.attrib.get("aliaspageid", ""),
                "alias_file": aliasref.attrib.get("aliasfile", ""),
                "hover": _normalize_space(aliasref.attrib.get("hover", "")),
            }
        )
    return aliases


def _parse_template_parts(asmtemplate: Optional[ET.Element]) -> List[Dict[str, str]]:
    if asmtemplate is None:
        return []

    parts: List[Dict[str, str]] = []
    if asmtemplate.text:
        parts.append({"kind": "text", "text": asmtemplate.text})

    for child in asmtemplate:
        tag = child.tag.lower()
        if tag == "text":
            parts.append({"kind": "text", "text": child.text or ""})
        elif tag == "a":
            parts.append(
                {
                    "kind": "operand",
                    "text": child.text or "",
                    "hover": child.attrib.get("hover", ""),
                    "link": child.attrib.get("link", ""),
                }
            )
        if child.tail:
            parts.append({"kind": "text", "text": child.tail})

    return parts


def _parts_to_template(parts: Sequence[Mapping[str, str]]) -> str:
    return "".join(part.get("text", "") for part in parts)


def _extract_features(root: ET.Element, encoding: ET.Element) -> List[str]:
    features = set()
    for variant in root.findall(".//arch_variant"):
        feature = _normalize_space(variant.attrib.get("feature", ""))
        if feature:
            features.add(feature)
    for variant in encoding.findall("../arch_variants/arch_variant"):
        feature = _normalize_space(variant.attrib.get("feature", ""))
        if feature:
            features.add(feature)
    return sorted(features)


def _classify_execution(
    mnemonic: str,
    instr_class: str,
    title: str,
    description: str,
) -> Dict[str, Any]:
    upper = mnemonic.upper()
    lower_desc = f"{title} {description}".lower()
    trap_like = upper in _TRAP_MNEMONICS or "exception" in lower_desc
    privileged = False
    if instr_class == "system" and upper not in _SAFE_SYSTEM_MNEMONICS:
        privileged = True
    if upper.startswith(("MRS", "MSR", "SYS", "SYSL", "TLBI", "AT ", "IC ", "DC ")):
        privileged = True

    executable = not trap_like and not privileged
    if instr_class == "system" and upper in _SAFE_SYSTEM_MNEMONICS:
        executable = True

    return {
        "trap_like": trap_like,
        "privileged": privileged,
        "executable": executable,
        "execution_block_reason": None
        if executable
        else ("trap_like" if trap_like else "privileged"),
    }


def _kunpeng_score(mnemonic: str, instr_class: str) -> float:
    upper = mnemonic.upper()
    if any(upper.startswith(prefix) for prefix in _KUNPENG_MEMORY_PREFIXES):
        return 1.0
    if any(upper.startswith(prefix) for prefix in _KUNPENG_BRANCH_PREFIXES):
        return 0.75
    if instr_class in {"float", "advsimd"} or any(
        upper.startswith(prefix) for prefix in _KUNPENG_SIMD_PREFIXES
    ):
        return 0.70
    if instr_class == "system":
        return 0.10
    return 0.45


def _register_value(prefix: str, index: int) -> str:
    if prefix == "sp":
        return "sp"
    return f"{prefix}{index}"


def _range_values(text: str) -> Optional[tuple[int, int]]:
    match = re.search(r"range\s+(-?\d+)\s+to\s+(-?\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _extract_multiple(text: str) -> int:
    match = re.search(r"multiple of (\d+)", text)
    if not match:
        return 1
    return max(int(match.group(1)), 1)


def _render_symbol_value(
    symbol: str,
    hover: str,
    *,
    mnemonic: str,
    instr_class: str,
    operand_index: int,
    label_name: str,
) -> str:
    token = symbol.strip().strip("<>").strip()
    lower_token = token.lower()
    hover_text = _normalize_space(hover).lower()
    upper = token.upper()

    if "label" in lower_token or "branch target" in hover_text or "pc-relative" in hover_text:
        return label_name

    if "system register name" in hover_text or lower_token == "systemreg":
        return "nzcv"

    if lower_token in {"cond", "condition"} or "condition code" in hover_text:
        return "eq"

    if "arrangement specifier" in hover_text or lower_token == "t":
        if "half-precision" in hover_text:
            return "8h"
        if "double-precision" in hover_text and "single-precision" not in hover_text:
            return "2d"
        return "4s"

    if "shift type" in hover_text or lower_token == "shift":
        return "lsl"

    if "extend option" in hover_text or lower_token == "extend":
        return "uxtx"

    if lower_token in {"prfop", "prfop1"} or "prefetch operation" in hover_text:
        return "pldl1keep"

    if lower_token in {"barrier", "option"} and "barrier" in hover_text:
        return "sy"

    if "name 'cn'" in hover_text or lower_token == "cn":
        return "c0"

    if "name 'cm'" in hover_text or lower_token == "cm":
        return "c0"

    if lower_token in {"op0", "op1", "op2", "imm", "amount", "lsb", "width", "index"}:
        if lower_token == "op0":
            return "3"
        return "0"

    if "signed immediate" in hover_text or "unsigned immediate" in hover_text:
        limits = _range_values(hover_text)
        step = _extract_multiple(hover_text)
        if limits is None:
            return "0"
        low, high = limits
        if low <= 0 <= high:
            return "0"
        candidate = low if low > 0 else high
        if step > 1:
            candidate = int(math.ceil(candidate / float(step)) * step)
            if candidate > high:
                candidate = low
        return str(candidate)

    if "stack pointer" in hover_text or "base register or stack pointer" in hover_text:
        return "sp"

    if any(name in upper for name in ["XD", "XN", "XM", "XA", "XT", "XR", "XS"]):
        return _register_value("x", min(operand_index, 5))

    if any(name in upper for name in ["WD", "WN", "WM", "WA", "WT", "WR", "WS"]):
        return _register_value("w", min(operand_index, 5))

    if any(name in upper for name in ["VD", "VN", "VM", "VA", "VT"]):
        return _register_value("v", min(operand_index, 5))

    if any(name in upper for name in ["DD", "DN", "DM", "DT"]):
        return _register_value("d", min(operand_index, 5))

    if any(name in upper for name in ["SD", "SN", "SM", "ST"]):
        return _register_value("s", min(operand_index, 5))

    if upper.startswith("H"):
        return _register_value("h", min(operand_index, 5))

    if upper.startswith("B"):
        return _register_value("b", min(operand_index, 5))

    if lower_token.startswith("imm"):
        return "0"

    if lower_token.endswith("|sp"):
        return "sp"

    if instr_class == "system":
        return "0"

    return "0"


def _finalize_asm(asm: str) -> str:
    asm = asm.replace("{", "").replace("}", "")
    asm = _ALT_RE.sub(r"\1", asm)
    asm = re.sub(r"\s+,", ",", asm)
    asm = re.sub(r"\(\s+", "(", asm)
    asm = re.sub(r"\s+\)", ")", asm)
    asm = re.sub(r"#\s+", "#", asm)
    asm = re.sub(r",\s*,", ", ", asm)
    asm = _normalize_space(asm)
    return asm


def render_sample_asm(
    encoding: Mapping[str, Any],
    *,
    label_name: str = _DEFAULT_BRANCH_LABEL,
) -> str:
    mnemonic = str(encoding.get("mnemonic", ""))
    instr_class = str(encoding.get("instr_class", "general"))
    parts = encoding.get("parts", [])
    rendered: List[str] = []
    operand_index = 0

    for part in parts:
        kind = part.get("kind", "text")
        if kind == "text":
            rendered.append(part.get("text", ""))
            continue

        value = _render_symbol_value(
            part.get("text", ""),
            part.get("hover", ""),
            mnemonic=mnemonic,
            instr_class=instr_class,
            operand_index=operand_index,
            label_name=label_name,
        )
        operand_index += 1
        rendered.append(value)

    return _finalize_asm("".join(rendered))


def _sequence_body(encodings: Sequence[Mapping[str, Any]], label_name: str) -> str:
    lines: List[str] = [".arch armv8-a", ".text"]
    needs_label = False

    for encoding in encodings:
        sample = encoding.get("sample_asm") or render_sample_asm(
            encoding, label_name=label_name
        )
        if label_name in sample:
            needs_label = True
        lines.append(sample)

    if needs_label:
        lines.append(f"{label_name}:")
        lines.append("nop")

    return "\n".join(lines) + "\n"


def validate_sequence_asm(
    encodings: Sequence[Mapping[str, Any]],
    *,
    clang: str = "clang",
    target: str = "aarch64-none-elf",
    label_name: str = _DEFAULT_BRANCH_LABEL,
) -> Dict[str, Any]:
    asm_text = _sequence_body(encodings, label_name)
    with tempfile.TemporaryDirectory(prefix="microprobe-a64-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        asm_path = tmpdir_path / "catalog.s"
        obj_path = tmpdir_path / "catalog.o"
        asm_path.write_text(asm_text, encoding="utf-8")
        cmd = [clang, "-target", target, "-c", str(asm_path), "-o", str(obj_path)]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": cmd,
        "asm_text": asm_text,
    }


def _encoding_payload(
    root: ET.Element,
    encoding: ET.Element,
    *,
    mnemonic: str,
    instr_class: str,
    title: str,
    description: str,
) -> Dict[str, Any]:
    parts = _parse_template_parts(encoding.find("./asmtemplate"))
    payload = _classify_execution(mnemonic, instr_class, title, description)
    entry: Dict[str, Any] = {
        "name": encoding.attrib.get("name", ""),
        "label": encoding.attrib.get("label", ""),
        "docvars": _docvars(encoding),
        "template": _parts_to_template(parts),
        "parts": parts,
        "mnemonic": mnemonic,
        "instr_class": instr_class,
        "feature_tags": _extract_features(root, encoding),
        "kunpeng_hotness": _kunpeng_score(mnemonic, instr_class),
    }
    entry.update(payload)
    entry["sample_asm"] = render_sample_asm(entry)
    return entry


def build_catalog(
    xml_dir: Path | str,
    *,
    docs_dir: Path | str = DEFAULT_DOCS_DIR,
    classes: Iterable[str] = DEFAULT_CLASSES,
) -> Dict[str, Any]:
    xml_root = Path(xml_dir)
    docs_root = Path(docs_dir)
    docs_index = _load_docs_index(docs_root)
    wanted = set(classes)
    instructions: List[Dict[str, Any]] = []

    for xml_file in sorted(xml_root.glob("*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue

        docvars = _docvars(root)
        if docvars.get("isa") != "A64":
            continue

        instr_class = docvars.get("instr-class", "")
        if instr_class not in wanted:
            continue

        mnemonic = docvars.get("alias_mnemonic") or docvars.get("mnemonic")
        if not mnemonic:
            continue

        title = _normalize_heading(root.attrib.get("title", "") or root.findtext("./heading", ""))
        description = _normalize_space(" ".join(root.find("./desc").itertext())) if root.find("./desc") is not None else ""
        encodings: List[Dict[str, Any]] = []
        for encoding in root.findall(".//encoding"):
            encodings.append(
                _encoding_payload(
                    root,
                    encoding,
                    mnemonic=mnemonic,
                    instr_class=instr_class,
                    title=title,
                    description=description,
                )
            )

        if not encodings:
            continue

        instructions.append(
            {
                "xml_file": xml_file.name,
                "xml_path": str(xml_file.resolve()),
                "xml_id": root.attrib.get("id", xml_file.stem),
                "mnemonic": mnemonic,
                "title": title,
                "instr_class": instr_class,
                "docvars": docvars,
                "doc_path": docs_index.get(title),
                "aliases": _parse_aliases(root),
                "description": description,
                "feature_tags": sorted(
                    {feature for encoding in encodings for feature in encoding["feature_tags"]}
                ),
                "kunpeng_hotness": max(
                    encoding["kunpeng_hotness"] for encoding in encodings
                ),
                "encodings": encodings,
            }
        )

    all_encodings = [encoding for item in instructions for encoding in item["encodings"]]
    mapped_docs = sum(1 for item in instructions if item.get("doc_path"))
    return {
        "catalog_version": 1,
        "xml_dir": str(xml_root.resolve()),
        "docs_dir": str(docs_root.resolve()),
        "classes": sorted(wanted),
        "instruction_count": len(instructions),
        "encoding_count": len(all_encodings),
        "unique_mnemonics": sorted({item["mnemonic"] for item in instructions}),
        "docs_pages": len(docs_index),
        "docs_mapped_pages": mapped_docs,
        "instructions": instructions,
    }


def save_catalog(catalog: Mapping[str, Any], path: Path | str = DEFAULT_CATALOG_PATH) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def load_catalog(path: Path | str = DEFAULT_CATALOG_PATH) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iter_catalog_encodings(
    catalog: Mapping[str, Any],
    *,
    profile_name: str = PROFILE_ALL_GENERATABLE,
) -> Iterator[Dict[str, Any]]:
    normalized = str(profile_name or PROFILE_ALL_GENERATABLE).strip().upper()
    for instruction in catalog.get("instructions", []):
        for encoding in instruction.get("encodings", []):
            merged = dict(encoding)
            merged["title"] = instruction.get("title", "")
            merged["doc_path"] = instruction.get("doc_path")
            merged["xml_file"] = instruction.get("xml_file")
            merged["xml_id"] = instruction.get("xml_id")
            if normalized == PROFILE_ALL_GENERATABLE:
                yield merged
                continue
            if normalized == PROFILE_EXECUTABLE_SAFE and merged.get("executable"):
                yield merged
                continue
            if normalized == PROFILE_KUNPENG920_STRESS:
                if merged.get("executable") and float(merged.get("kunpeng_hotness", 0.0)) >= 0.60:
                    yield merged


def select_catalog_encodings(
    catalog: Mapping[str, Any],
    *,
    profile_name: str,
    sequence_length: int,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    encodings = list(iter_catalog_encodings(catalog, profile_name=profile_name))
    if not encodings:
        return []
    start = max(offset, 0)
    selected = encodings[start : start + sequence_length]
    if len(selected) >= sequence_length:
        return selected

    index = 0
    while len(selected) < sequence_length:
        selected.append(encodings[index % len(encodings)])
        index += 1
    return selected


def plan_catalog_task_count(
    catalog: Mapping[str, Any],
    *,
    profile_name: str,
    requested_count: int,
    sequence_length: int,
) -> int:
    encodings = list(iter_catalog_encodings(catalog, profile_name=profile_name))
    if not encodings:
        return requested_count
    required = int(math.ceil(len(encodings) / float(max(sequence_length, 1))))
    return max(requested_count, required)


def build_catalog_summary(catalog: Mapping[str, Any]) -> Dict[str, Any]:
    instructions = catalog.get("instructions", [])
    encodings = [encoding for item in instructions for encoding in item.get("encodings", [])]
    return {
        "instruction_count": len(instructions),
        "encoding_count": len(encodings),
        "unique_mnemonics": len({item.get("mnemonic") for item in instructions}),
        "docs_pages": int(catalog.get("docs_pages", 0)),
        "docs_mapped_pages": int(catalog.get("docs_mapped_pages", 0)),
        "executable_encodings": len([encoding for encoding in encodings if encoding.get("executable")]),
        "privileged_encodings": len([encoding for encoding in encodings if encoding.get("privileged")]),
        "trap_like_encodings": len([encoding for encoding in encodings if encoding.get("trap_like")]),
    }
