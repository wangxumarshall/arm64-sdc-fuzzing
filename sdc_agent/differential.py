#!/usr/bin/env python3
"""Lightweight ARM64 SDC differential runner."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .power_backends import McPATBackend

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEM5_CONFIG = (
    REPO_ROOT / "gem5" / "configs" / "example" / "arm" / "sdc_kunpeng920_se.py"
)
DEFAULT_GEM5_OUTDIR = REPO_ROOT / "m5out-sdc"
DIGEST_PATTERN = re.compile(r"SDC_(?:DIGEST|HASH)=([0-9a-fA-F]+)")
FAULT_MANIFEST_NAME = "sdc_fault_request.json"
INJECTED_EXECUTION_PLANES = {"gem5_scripted"}
INJECTION_LOG_PATTERN = re.compile(
    r"\[sdc\] injected (?P<target_kind>register|vector register) bit flip: "
    r"cpu=(?P<cpu_index>\d+) "
    r"reg=(?P<register_name>[A-Za-z0-9_]+) "
    r"bit=(?P<fault_bit>\d+) "
    r"old=(?P<old_value>0x[0-9a-fA-F]+) "
    r"new=(?P<new_value>0x[0-9a-fA-F]+) "
    r"tick=(?P<fault_tick>\d+)"
)


@dataclass
class CommandResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DifferentialResult:
    status: str
    golden_digest: Optional[str]
    faulted_digest: Optional[str]
    compile: CommandResult
    qemu: CommandResult
    gem5: Optional[CommandResult]
    mcpat: Optional[Dict[str, Any]]
    fault_request: Optional[Dict[str, Any]] = None
    mcpat_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.mcpat is not None:
            payload["mcpat"] = {
                key: str(value) if isinstance(value, Path) else value
                for key, value in self.mcpat.items()
            }
        return payload


def run_command(
    command: List[str], cwd: Optional[Path], timeout: int
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            command=command,
            returncode=-2,
            stdout="",
            stderr=str(exc),
            timed_out=False,
        )


def extract_digest(command_result: CommandResult) -> Optional[str]:
    for payload in (command_result.stdout, command_result.stderr):
        match = DIGEST_PATTERN.search(payload)
        if match is not None:
            return match.group(1).lower()
    return None


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def load_fault_request_manifest(gem5_outdir: Path) -> Dict[str, Any]:
    manifest_path = gem5_outdir / FAULT_MANIFEST_NAME
    if not manifest_path.exists():
        return {"manifest_found": False}

    payload: Dict[str, Any]
    try:
        raw_payload = json.loads(
            manifest_path.read_text(encoding="utf-8", errors="replace")
        )
    except json.JSONDecodeError as exc:
        return {
            "manifest_found": True,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_error": str(exc),
        }

    if isinstance(raw_payload, dict):
        payload = dict(raw_payload)
    else:
        payload = {"manifest_payload": raw_payload}

    payload["manifest_found"] = True
    payload["manifest_path"] = str(manifest_path.resolve())
    if "binary_args" in payload and not isinstance(payload["binary_args"], list):
        payload["binary_args"] = list(payload.get("binary_args") or [])
    return payload


def parse_injection_observation(
    command_result: Optional[CommandResult],
) -> Optional[Dict[str, Any]]:
    if command_result is None:
        return None
    for payload in (command_result.stderr, command_result.stdout):
        match = INJECTION_LOG_PATTERN.search(payload)
        if match is None:
            continue
        groups = match.groupdict()
        return {
            "cpu_index": int(groups["cpu_index"]),
            "target_kind": groups["target_kind"].replace(" ", "_"),
            "register_name": groups["register_name"],
            "fault_bit": int(groups["fault_bit"]),
            "fault_tick": int(groups["fault_tick"]),
            "old_value": groups["old_value"].lower(),
            "new_value": groups["new_value"].lower(),
        }
    return None


def _infer_fault_execution_plane(
    fault_request: Dict[str, Any],
    *,
    observation: Optional[Dict[str, Any]],
) -> str:
    if str(fault_request.get("fault_model", "none")) == "none":
        return "none"
    if observation is not None:
        return "gem5_scripted"
    if bool(fault_request.get("implemented_in_script", False)):
        return "gem5_script_capable_unobserved"
    if bool(fault_request.get("manifest_found", False)):
        return "manifest_only"
    return "request_only"


def fault_request_requires_injection(
    fault_request: Optional[Mapping[str, Any]],
) -> bool:
    if not isinstance(fault_request, Mapping):
        return False
    fault_model = str(fault_request.get("fault_model", "none")).strip().lower()
    return fault_model not in {"", "none"}


def fault_request_has_observed_injection(
    fault_request: Optional[Mapping[str, Any]],
) -> bool:
    if not fault_request_requires_injection(fault_request):
        return False
    if not isinstance(fault_request, Mapping):
        return False
    return bool(fault_request.get("injection_observed", False)) and (
        str(fault_request.get("execution_plane", "")).strip().lower()
        in INJECTED_EXECUTION_PLANES
    )


def build_fault_request_summary(
    *,
    gem5_outdir: Optional[Path],
    gem5_result: Optional[CommandResult],
    fault_model: str,
    fault_target: str,
    fault_bit: Optional[int],
    fault_tick: Optional[int],
) -> Dict[str, Any]:
    payload = (
        load_fault_request_manifest(gem5_outdir.resolve())
        if gem5_outdir is not None
        else {"manifest_found": False}
    )
    payload.setdefault("fault_model", fault_model)
    payload.setdefault("fault_target", fault_target)
    payload.setdefault("fault_bit", fault_bit)
    payload.setdefault("fault_tick", fault_tick)
    payload["implemented_in_script"] = bool(payload.get("implemented_in_script", False))

    observation = parse_injection_observation(gem5_result)
    payload["injection_observed"] = observation is not None
    if observation is not None:
        payload["observation"] = observation
    payload["execution_plane"] = _infer_fault_execution_plane(
        payload,
        observation=observation,
    )
    return payload


def compile_static_elf(
    source: Path,
    output: Path,
    compiler: str,
    compiler_flags: List[str],
    timeout: int,
) -> CommandResult:
    command = [
        compiler,
        "-static",
        "-O0",
        "-g0",
        "-fno-inline",
        "-o",
        str(output),
        str(source),
    ] + compiler_flags
    return run_command(command, cwd=source.parent, timeout=timeout)


def run_qemu(
    elf: Path, qemu_binary: str, qemu_args: List[str], timeout: int
) -> CommandResult:
    command = [qemu_binary] + qemu_args + [str(elf)]
    return run_command(command, cwd=elf.parent, timeout=timeout)


def run_gem5(
    elf: Path,
    gem5_binary: str,
    gem5_config: Path,
    gem5_outdir: Path,
    gem5_args: List[str],
    gem5_cmd_flag: str,
    timeout: int,
) -> CommandResult:
    gem5_outdir.mkdir(parents=True, exist_ok=True)
    guest_stdout = gem5_outdir / "guest.stdout"
    guest_stderr = gem5_outdir / "guest.stderr"

    resolved_cmd_flag = gem5_cmd_flag
    if gem5_cmd_flag == "auto":
        if gem5_config.name in {
            "starter_se.py",
            "etrace_se.py",
            "sdc_kunpeng920_se.py",
        }:
            resolved_cmd_flag = ""
        else:
            resolved_cmd_flag = "--cmd"

    command = [
        gem5_binary,
        "-d",
        str(gem5_outdir),
        str(gem5_config),
    ]

    if gem5_config.name == "se.py":
        command.extend(
            [
                "--arm-iset",
                "aarch64",
                "--output",
                str(guest_stdout),
                "--errout",
                str(guest_stderr),
            ]
        )

    command.extend(gem5_args)

    if resolved_cmd_flag:
        command.extend([resolved_cmd_flag, str(elf)])
    else:
        command.append(str(elf))

    result = run_command(command, cwd=REPO_ROOT, timeout=timeout)

    guest_stdout_text = read_text_if_exists(guest_stdout)
    guest_stderr_text = read_text_if_exists(guest_stderr)
    if guest_stdout_text:
        result.stdout = (
            result.stdout
            + ("\n" if result.stdout else "")
            + "[guest stdout]\n"
            + guest_stdout_text
        )
    if guest_stderr_text:
        result.stderr = (
            result.stderr
            + ("\n" if result.stderr else "")
            + "[guest stderr]\n"
            + guest_stderr_text
        )

    return result


def build_fault_args(
    *,
    fault_model: str = "none",
    fault_target: str = "",
    fault_bit: Optional[int] = None,
    fault_tick: Optional[int] = None,
) -> List[str]:
    arguments = [
        "--fault-model",
        fault_model,
        "--fault-target",
        fault_target,
    ]
    if fault_bit is not None:
        arguments.extend(["--fault-bit", str(fault_bit)])
    if fault_tick is not None:
        arguments.extend(["--fault-tick", str(fault_tick)])
    return arguments


def classify(
    compile_result: CommandResult,
    qemu_result: CommandResult,
    gem5_result: Optional[CommandResult],
    golden_digest: Optional[str],
    faulted_digest: Optional[str],
    fault_request: Optional[Mapping[str, Any]] = None,
) -> str:
    if compile_result.returncode != 0:
        return "compile_failed"
    if qemu_result.returncode != 0:
        return "golden_failed"
    if gem5_result is None:
        if fault_request_requires_injection(fault_request):
            return "no_injection"
        return "golden_only"
    if gem5_result.timed_out:
        return "gem5_timeout"
    if gem5_result.returncode != 0:
        return "gem5_failed"
    if fault_request_requires_injection(fault_request) and not fault_request_has_observed_injection(
        fault_request
    ):
        return "no_injection"
    if golden_digest is None or faulted_digest is None:
        return "digest_missing"
    if golden_digest != faulted_digest:
        return "sdc_found"
    return "matched"


def run_differential(
    source: Path,
    *,
    elf: Optional[Path] = None,
    skip_compile: bool = False,
    skip_qemu: bool = False,
    cached_golden_digest: Optional[str] = None,
    compiler: str = "aarch64-linux-gnu-gcc",
    compiler_flags: Optional[List[str]] = None,
    qemu_binary: str = "qemu-aarch64",
    qemu_args: Optional[List[str]] = None,
    gem5_binary: str = "gem5/build/ARM/gem5.opt",
    gem5_config: Path = DEFAULT_GEM5_CONFIG,
    gem5_outdir: Path = DEFAULT_GEM5_OUTDIR,
    gem5_args: Optional[List[str]] = None,
    gem5_cmd_flag: str = "auto",
    fault_model: str = "none",
    fault_target: str = "",
    fault_bit: Optional[int] = None,
    fault_tick: Optional[int] = None,
    skip_gem5: bool = False,
    skip_mcpat: bool = False,
    mcpat_template_profile: str = "arm64-kunpeng920",
    mcpat_binary: Optional[Path] = None,
    timeout: int = 120,
) -> DifferentialResult:
    source = source.resolve()
    elf = elf.resolve() if elf is not None else source.with_suffix(".elf")
    compiler_flags = list(compiler_flags or [])
    qemu_args = list(qemu_args or [])
    gem5_args = build_fault_args(
        fault_model=fault_model,
        fault_target=fault_target,
        fault_bit=fault_bit,
        fault_tick=fault_tick,
    ) + list(gem5_args or [])

    if skip_compile and elf.exists():
        compile_result = CommandResult(
            command=[],
            returncode=0,
            stdout="",
            stderr="Skipped compilation; reused cached ELF.",
        )
    else:
        compile_result = compile_static_elf(
            source=source,
            output=elf,
            compiler=compiler,
            compiler_flags=compiler_flags,
            timeout=timeout,
        )

    qemu_result = (
        CommandResult(
            command=[],
            returncode=0,
            stdout=f"SDC_DIGEST={cached_golden_digest}",
            stderr="Skipped QEMU; reused cached golden digest.",
        )
        if compile_result.returncode == 0 and skip_qemu and cached_golden_digest is not None
        else run_qemu(
            elf=elf,
            qemu_binary=qemu_binary,
            qemu_args=qemu_args,
            timeout=timeout,
        )
        if compile_result.returncode == 0
        else CommandResult(
            command=[],
            returncode=-3,
            stdout="",
            stderr="Skipped because compilation failed.",
        )
    )
    golden_digest = extract_digest(qemu_result)

    gem5_result: Optional[CommandResult] = None
    mcpat_result: Optional[Dict[str, Any]] = None
    mcpat_error: Optional[str] = None
    faulted_digest: Optional[str] = None

    if not skip_gem5 and compile_result.returncode == 0:
        gem5_result = run_gem5(
            elf=elf,
            gem5_binary=gem5_binary,
            gem5_config=gem5_config.resolve(),
            gem5_outdir=gem5_outdir.resolve(),
            gem5_args=gem5_args,
            gem5_cmd_flag=gem5_cmd_flag,
            timeout=timeout,
        )
        faulted_digest = extract_digest(gem5_result)
        if gem5_result.returncode == 0 and not skip_mcpat:
            backend = McPATBackend(
                template_profile=mcpat_template_profile,
                mcpat_binary=mcpat_binary.resolve() if mcpat_binary is not None else None,
            )
            try:
                mcpat_result = backend.run(gem5_outdir.resolve())
            except Exception as exc:  # pragma: no cover - runtime environment dependent
                mcpat_error = str(exc)

    fault_request = build_fault_request_summary(
        gem5_outdir=gem5_outdir if gem5_result is not None else None,
        gem5_result=gem5_result,
        fault_model=fault_model,
        fault_target=fault_target,
        fault_bit=fault_bit,
        fault_tick=fault_tick,
    )

    return DifferentialResult(
        status=classify(
            compile_result=compile_result,
            qemu_result=qemu_result,
            gem5_result=gem5_result,
            golden_digest=golden_digest,
            faulted_digest=faulted_digest,
            fault_request=fault_request,
        ),
        golden_digest=golden_digest,
        faulted_digest=faulted_digest,
        compile=compile_result,
        qemu=qemu_result,
        gem5=gem5_result,
        mcpat=mcpat_result,
        fault_request=fault_request,
        mcpat_error=mcpat_error,
    )


def result_exit_code(result: DifferentialResult) -> int:
    return 0 if result.status in {"matched", "sdc_found", "golden_only"} else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile an ARM64 test, run QEMU and gem5, and classify SDC."
    )
    parser.add_argument("source", type=Path, help="Path to generated C source.")
    parser.add_argument(
        "--elf",
        type=Path,
        default=None,
        help="Optional ELF output path. Defaults to <source stem>.elf",
    )
    parser.add_argument(
        "--compiler", default="aarch64-linux-gnu-gcc", help="ARM64 C compiler."
    )
    parser.add_argument(
        "--compiler-flag",
        action="append",
        default=[],
        help="Extra compiler flag. Repeat as needed.",
    )
    parser.add_argument(
        "--qemu-binary", default="qemu-aarch64", help="QEMU user-mode binary."
    )
    parser.add_argument(
        "--qemu-arg",
        action="append",
        default=[],
        help="Extra argument passed to QEMU. Repeat as needed.",
    )
    parser.add_argument(
        "--gem5-binary", default="gem5/build/ARM/gem5.opt", help="gem5 executable."
    )
    parser.add_argument(
        "--gem5-config",
        type=Path,
        default=DEFAULT_GEM5_CONFIG,
        help="gem5 configuration script.",
    )
    parser.add_argument(
        "--gem5-outdir",
        type=Path,
        default=DEFAULT_GEM5_OUTDIR,
        help="gem5 output directory.",
    )
    parser.add_argument(
        "--gem5-arg",
        action="append",
        default=[],
        help="Extra argument passed through to gem5 config. Repeat as needed.",
    )
    parser.add_argument(
        "--gem5-cmd-flag",
        default="auto",
        help=(
            "Flag used by the chosen gem5 script to pass the workload binary. "
            "Use 'auto' to match the selected script."
        ),
    )
    parser.add_argument(
        "--fault-model",
        default="none",
        help="Fault model name forwarded to the gem5 SDC config.",
    )
    parser.add_argument(
        "--fault-target",
        default="",
        help="Fault target identifier forwarded to the gem5 SDC config.",
    )
    parser.add_argument(
        "--fault-bit",
        type=int,
        default=None,
        help="Optional bit index forwarded to the gem5 SDC config.",
    )
    parser.add_argument(
        "--fault-tick",
        type=int,
        default=None,
        help="Optional tick forwarded to the gem5 SDC config.",
    )
    parser.add_argument(
        "--skip-gem5",
        action="store_true",
        help="Only run compile + QEMU golden execution.",
    )
    parser.add_argument(
        "--skip-mcpat",
        action="store_true",
        help="Skip McPAT post-processing even after a gem5 run.",
    )
    parser.add_argument(
        "--mcpat-template-profile",
        default="arm64-kunpeng920",
        help="McPAT template profile used for gem5 post-processing.",
    )
    parser.add_argument(
        "--mcpat-binary",
        type=Path,
        default=None,
        help="Optional path to the local McPAT binary.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-command timeout in seconds.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON output file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_differential(
        source=args.source,
        elf=args.elf,
        compiler=args.compiler,
        compiler_flags=args.compiler_flag,
        qemu_binary=args.qemu_binary,
        qemu_args=args.qemu_arg,
        gem5_binary=args.gem5_binary,
        gem5_config=args.gem5_config,
        gem5_outdir=args.gem5_outdir,
        gem5_args=args.gem5_arg,
        gem5_cmd_flag=args.gem5_cmd_flag,
        fault_model=args.fault_model,
        fault_target=args.fault_target,
        fault_bit=args.fault_bit,
        fault_tick=args.fault_tick,
        skip_gem5=args.skip_gem5,
        skip_mcpat=args.skip_mcpat,
        mcpat_template_profile=args.mcpat_template_profile,
        mcpat_binary=args.mcpat_binary,
        timeout=args.timeout,
    )

    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return result_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
