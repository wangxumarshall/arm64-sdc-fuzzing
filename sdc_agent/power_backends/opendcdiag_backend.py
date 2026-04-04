"""OpenDCDiag execution backend for the hardware validation lane."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPENDCDIAG_ROOT = REPO_ROOT / "opendcdiag"
DEFAULT_BUILD_DIR_NAME = "builddir"
DEFAULT_RUNTIME_DIR_NAME = "opendcdiag-run"
DEFAULT_EXECUTABLE_NAME = "sandstone"


def _run_command(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _load_promotion_manifest(bundle_dir: Path) -> Dict[str, Any]:
    manifest_path = (bundle_dir / "promotion.json").resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing promotion manifest: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Promotion manifest must be an object: {manifest_path}")
    return payload


def _copy_workspace(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore(_base: str, names: list[str]) -> set[str]:
        ignored = {
            ".git",
            ".pytest_cache",
            ".claude",
            ".entire",
            ".omc",
            "builddir",
            "build",
            "__pycache__",
        }
        return {name for name in names if name in ignored}

    shutil.copytree(src, dst, ignore=_ignore)
    return dst


def _ensure_test_source(workspace_root: Path, external_test_name: str, bundle_dir: Path) -> Path:
    source_path = bundle_dir / f"{external_test_name}.cpp"
    if not source_path.exists():
        raise FileNotFoundError(f"Missing promotion source: {source_path}")
    target_path = workspace_root / "tests" / "cpu" / "arm64" / source_path.name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return target_path


def _patch_arm64_meson(workspace_root: Path, source_name: str) -> Path:
    meson_path = workspace_root / "tests" / "cpu" / "arm64" / "meson.build"
    content = meson_path.read_text(encoding="utf-8")
    needle = f"        '{source_name}',\n"
    if needle not in content:
        anchor_line = next(
            (line for line in content.splitlines(keepends=True) if "'sdc_test.cpp'" in line),
            None,
        )
        if anchor_line is None:
            raise RuntimeError(f"Failed to find insertion anchor in {meson_path}")
        indent = anchor_line[: len(anchor_line) - len(anchor_line.lstrip())]
        insertion = f"{indent}'{source_name}',\n"
        content = content.replace(anchor_line, anchor_line + insertion)
        meson_path.write_text(content, encoding="utf-8")
    return meson_path


def _detectors_from_result(returncode: int) -> Dict[str, Any]:
    return {"digest_match": "pass" if returncode == 0 else "fail", "returncode": returncode}


def _parse_tap_summary(stdout: str) -> Dict[str, int]:
    ok_count = 0
    fail_count = 0
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("ok "):
            ok_count += 1
        elif stripped.startswith("not ok "):
            fail_count += 1
    return {
        "tap_ok_count": ok_count,
        "tap_fail_count": fail_count,
        "tap_assertion_count": ok_count + fail_count,
    }


def _collect_machine_metadata() -> Dict[str, Any]:
    uname = platform.uname()
    return {
        "system": uname.system,
        "node": uname.node,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }


@dataclass(frozen=True)
class OpenDCDiagBackend:
    """Execute promoted ARM64 tests in a staged OpenDCDiag workspace."""

    enabled: bool = True
    opendcdiag_root: Path = DEFAULT_OPENDCDIAG_ROOT
    meson_binary: str = "meson"
    build_dir_name: str = DEFAULT_BUILD_DIR_NAME
    runtime_dir_name: str = DEFAULT_RUNTIME_DIR_NAME
    executable_name: str = DEFAULT_EXECUTABLE_NAME
    buildtype: str = "release"
    extra_setup_args: tuple[str, ...] = ()
    run_args: tuple[str, ...] = ("--beta", "-v")

    def run(self, target_dir: Path | str) -> Dict[str, Any]:
        bundle_dir = Path(target_dir).resolve()
        manifest = _load_promotion_manifest(bundle_dir)
        testcase_key = str(manifest["testcase_key"])
        external_test_name = str(manifest["external_test_name"])
        backend_name = str(manifest.get("backend_name", "opendcdiag"))

        workspace_root = _copy_workspace(
            self.opendcdiag_root.resolve(),
            bundle_dir / "opendcdiag-workspace",
        )
        injected_source = _ensure_test_source(workspace_root, external_test_name, bundle_dir)
        meson_file = _patch_arm64_meson(workspace_root, injected_source.name)

        build_dir = workspace_root / self.build_dir_name
        runtime_dir = bundle_dir / self.runtime_dir_name
        runtime_dir.mkdir(parents=True, exist_ok=True)

        setup_cmd = [
            self.meson_binary,
            "setup",
            str(build_dir),
            f"--buildtype={self.buildtype}",
            f"-Dexecutable_name={self.executable_name}",
            *self.extra_setup_args,
        ]
        compile_cmd = [
            self.meson_binary,
            "compile",
            "-C",
            str(build_dir),
            self.executable_name,
        ]
        executable_path = build_dir / self.executable_name
        run_cmd = [
            str(executable_path),
            *self.run_args,
            "-e",
            external_test_name,
            "--output-format=tap",
        ]

        setup_result = _run_command(setup_cmd, cwd=workspace_root)
        compile_result = (
            _run_command(compile_cmd, cwd=workspace_root)
            if setup_result.returncode == 0
            else subprocess.CompletedProcess(compile_cmd, -1, "", "meson setup failed")
        )
        run_result = (
            _run_command(run_cmd, cwd=workspace_root)
            if compile_result.returncode == 0 and executable_path.exists()
            else subprocess.CompletedProcess(run_cmd, -1, "", "meson compile failed")
        )

        setup_stdout = _write_text(runtime_dir / "meson-setup.stdout", setup_result.stdout)
        setup_stderr = _write_text(runtime_dir / "meson-setup.stderr", setup_result.stderr)
        compile_stdout = _write_text(runtime_dir / "meson-compile.stdout", compile_result.stdout)
        compile_stderr = _write_text(runtime_dir / "meson-compile.stderr", compile_result.stderr)
        run_stdout = _write_text(runtime_dir / "sandstone.stdout", run_result.stdout)
        run_stderr = _write_text(runtime_dir / "sandstone.stderr", run_result.stderr)

        result_status = "PASS" if run_result.returncode == 0 else "FAIL"
        detectors = {
            **_detectors_from_result(run_result.returncode),
            **_parse_tap_summary(run_result.stdout),
        }
        machine_metadata = _collect_machine_metadata()
        result_payload = {
            "backend": "opendcdiag",
            "backend_name": backend_name,
            "testcase_key": testcase_key,
            "external_test_name": external_test_name,
            "bundle_dir": str(bundle_dir),
            "workspace_root": str(workspace_root),
            "build_dir": str(build_dir),
            "result_status": result_status,
            "detectors": detectors,
            "machine_id": "local-opendcdiag",
            "machine_metadata": machine_metadata,
            "log_path": str(run_stdout),
            "runtime_dir": str(runtime_dir),
            "injected_source_path": str(injected_source),
            "meson_file": str(meson_file),
            "setup": {
                "command": setup_cmd,
                "returncode": setup_result.returncode,
                "stdout_path": str(setup_stdout),
                "stderr_path": str(setup_stderr),
            },
            "compile": {
                "command": compile_cmd,
                "returncode": compile_result.returncode,
                "stdout_path": str(compile_stdout),
                "stderr_path": str(compile_stderr),
            },
            "run": {
                "command": run_cmd,
                "returncode": run_result.returncode,
                "stdout_path": str(run_stdout),
                "stderr_path": str(run_stderr),
            },
        }
        result_json = runtime_dir / "result.json"
        result_json.write_text(
            json.dumps(result_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        result_payload["result_json"] = str(result_json.resolve())
        return result_payload
