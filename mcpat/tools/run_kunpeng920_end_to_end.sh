#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCPAT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${MCPAT_DIR}/.." && pwd)"
MATRIX_SCRIPT="${SCRIPT_DIR}/collect_kunpeng920_matrix.sh"
BUILD_SCRIPT="${SCRIPT_DIR}/build_kunpeng920_calibration.py"
DEFAULT_MATRIX_FILE="${SCRIPT_DIR}/kunpeng920_collection_matrix.tsv"

usage() {
  cat <<'EOF'
Usage:
  run_kunpeng920_end_to_end.sh --target-dir M5OUT --out-dir DIR [options]

This wrapper provides exactly two calibration modes:

1. manual
   collect -> build kunpeng920_calibration.json -> run pypat with --calibration-file

2. auto
   collect -> run pypat with --calibration-dataset

Options:
  --target-dir DIR          gem5 output directory containing config.json and stats.txt/stats.h5.
  --out-dir DIR             Root directory for collection logs, calibration output, and mcpat output.
  --calibration-mode MODE   manual or auto. Defaults to auto.
  --matrix-file FILE        Collection matrix TSV. Defaults to tools/kunpeng920_collection_matrix.tsv.
  --outfile FILE            Optional McPAT XML output path passed to pypat.
  --print-level N           McPAT print level. Defaults to 1.
  --opt-for-clk N           McPAT clock optimization flag. Defaults to 0.
  --mcpat-binary PATH       Optional mcpat binary path.
  --skip-collection         Reuse an existing collection dataset under <out-dir>/collection.
  --dry-run                 Print commands without executing them.

Examples:
  sudo mcpat/tools/run_kunpeng920_end_to_end.sh \
    --target-dir /path/to/m5out \
    --out-dir artifacts/kunpeng920-e2e \
    --calibration-mode auto

  sudo mcpat/tools/run_kunpeng920_end_to_end.sh \
    --target-dir /path/to/m5out \
    --out-dir artifacts/kunpeng920-e2e \
    --calibration-mode manual \
    --matrix-file mcpat/tools/kunpeng920_collection_matrix.tsv
EOF
}

TARGET_DIR=""
OUT_DIR=""
CALIBRATION_MODE="auto"
MATRIX_FILE="${DEFAULT_MATRIX_FILE}"
OUTFILE=""
PRINT_LEVEL="1"
OPT_FOR_CLK="0"
MCPAT_BINARY=""
SKIP_COLLECTION=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --calibration-mode)
      CALIBRATION_MODE="$2"
      shift 2
      ;;
    --matrix-file)
      MATRIX_FILE="$2"
      shift 2
      ;;
    --outfile)
      OUTFILE="$2"
      shift 2
      ;;
    --print-level)
      PRINT_LEVEL="$2"
      shift 2
      ;;
    --opt-for-clk)
      OPT_FOR_CLK="$2"
      shift 2
      ;;
    --mcpat-binary)
      MCPAT_BINARY="$2"
      shift 2
      ;;
    --skip-collection)
      SKIP_COLLECTION=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${TARGET_DIR}" || -z "${OUT_DIR}" ]]; then
  usage >&2
  exit 1
fi

if [[ "${CALIBRATION_MODE}" != "manual" && "${CALIBRATION_MODE}" != "auto" ]]; then
  echo "Invalid --calibration-mode: ${CALIBRATION_MODE}" >&2
  exit 1
fi

COLLECTION_DIR="${OUT_DIR}/collection"
CALIBRATION_FILE="${COLLECTION_DIR}/kunpeng920_calibration.json"
PYPAT_OUTFILE="${OUTFILE:-${OUT_DIR}/conv.xml}"

mkdir -p "${OUT_DIR}"

print_cmd() {
  printf '  '
  printf '%q ' "$@"
  printf '\n'
}

run_cmd() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    print_cmd "$@"
    return 0
  fi
  "$@"
}

if [[ "${SKIP_COLLECTION}" -eq 0 ]]; then
  echo "[e2e] collection phase"
  run_cmd "${MATRIX_SCRIPT}" \
    --out-dir "${COLLECTION_DIR}" \
    --matrix-file "${MATRIX_FILE}"
else
  echo "[e2e] skipping collection phase"
  if [[ ! -d "${COLLECTION_DIR}" ]]; then
    echo "[e2e] collection dataset not found: ${COLLECTION_DIR}" >&2
    exit 1
  fi
fi

if [[ "${CALIBRATION_MODE}" == "manual" ]]; then
  echo "[e2e] manual calibration phase"
  run_cmd python3 "${BUILD_SCRIPT}" "${COLLECTION_DIR}" -o "${CALIBRATION_FILE}"
fi

PYPAT_CMD=(
  python3 -m pypat "${TARGET_DIR}"
  --template-profile arm64-kunpeng920
  --outfile "${PYPAT_OUTFILE}"
  --print-level "${PRINT_LEVEL}"
  --opt-for-clk "${OPT_FOR_CLK}"
)

if [[ -n "${MCPAT_BINARY}" ]]; then
  PYPAT_CMD+=(--mcpat-binary "${MCPAT_BINARY}")
fi

if [[ "${CALIBRATION_MODE}" == "manual" ]]; then
  PYPAT_CMD+=(--calibration-file "${CALIBRATION_FILE}")
else
  PYPAT_CMD+=(--calibration-dataset "${COLLECTION_DIR}")
fi

echo "[e2e] calibrated pypat phase"
run_cmd env "PYTHONPATH=${MCPAT_DIR}:${PYTHONPATH:-}" "${PYPAT_CMD[@]}"

echo "[e2e] completed"
echo "[e2e] target_dir=${TARGET_DIR}"
echo "[e2e] out_dir=${OUT_DIR}"
echo "[e2e] calibration_mode=${CALIBRATION_MODE}"
if [[ "${CALIBRATION_MODE}" == "manual" ]]; then
  echo "[e2e] calibration_file=${CALIBRATION_FILE}"
else
  echo "[e2e] calibration_dataset=${COLLECTION_DIR}"
fi
echo "[e2e] mcpat_input=${PYPAT_OUTFILE}"
