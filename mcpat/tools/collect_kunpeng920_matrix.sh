#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SINGLE_COLLECT_SCRIPT="${SCRIPT_DIR}/collect_kunpeng920_counters.sh"
DEFAULT_MATRIX_FILE="${SCRIPT_DIR}/kunpeng920_collection_matrix.tsv"

usage() {
  cat <<'EOF'
Usage:
  collect_kunpeng920_matrix.sh --out-dir DIR [--matrix-file FILE]

Options:
  --out-dir DIR         Root output directory. One subdirectory is created per workload row.
  --matrix-file FILE    TSV matrix file. Defaults to tools/kunpeng920_collection_matrix.tsv.
  --dry-run             Print the commands without executing them.
  --stop-on-error       Stop immediately when any workload fails.

Matrix format:
  name<TAB>label<TAB>perf_events<TAB>command

Rules:
  - Empty lines and lines beginning with '#' are ignored.
  - "perf_events" may be empty.
  - "command" is passed as-is to collect_kunpeng920_counters.sh --cmd.

Example:
  sudo mcpat/tools/collect_kunpeng920_matrix.sh \
    --out-dir artifacts/kunpeng920-runs \
    --matrix-file mcpat/tools/kunpeng920_collection_matrix.tsv
EOF
}

OUT_DIR=""
MATRIX_FILE="${DEFAULT_MATRIX_FILE}"
DRY_RUN=0
STOP_ON_ERROR=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --matrix-file)
      MATRIX_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --stop-on-error)
      STOP_ON_ERROR=1
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

if [[ -z "${OUT_DIR}" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "${MATRIX_FILE}" ]]; then
  echo "Matrix file not found: ${MATRIX_FILE}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

row_num=0
failures=0

while IFS= read -r raw_line || [[ -n "${raw_line:-}" ]]; do
  [[ -z "${raw_line//[$'\r\n']/}" ]] && continue
  [[ "${raw_line}" =~ ^# ]] && continue

  name="$(printf '%s\n' "${raw_line}" | awk -F '\t' '{print $1}')"
  label="$(printf '%s\n' "${raw_line}" | awk -F '\t' '{print $2}')"
  perf_events="$(printf '%s\n' "${raw_line}" | awk -F '\t' '{print $3}')"
  command="$(printf '%s\n' "${raw_line}" | awk -F '\t' '{print $4}')"

  [[ -z "${name:-}" ]] && continue
  [[ -z "${command:-}" ]] && { echo "[matrix] ${name}: empty command" >&2; exit 1; }
  [[ "${perf_events}" == "-" ]] && perf_events=""

  row_num=$((row_num + 1))
  run_out_dir="${OUT_DIR}/${name}"

  cmd=(
    "${SINGLE_COLLECT_SCRIPT}"
    --out-dir "${run_out_dir}"
    --label "${label:-${name}}"
    --cmd "${command}"
  )
  if [[ -n "${perf_events:-}" ]]; then
    cmd+=(--perf-events "${perf_events}")
  fi

  echo "[matrix] (${row_num}) ${name}"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '  '
    printf '%q ' "${cmd[@]}"
    printf '\n'
    continue
  fi

  if "${cmd[@]}"; then
    echo "[matrix] ${name}: ok"
  else
    echo "[matrix] ${name}: failed" >&2
    failures=$((failures + 1))
    if [[ "${STOP_ON_ERROR}" -eq 1 ]]; then
      exit 1
    fi
  fi
done < "${MATRIX_FILE}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[matrix] dry run complete"
  exit 0
fi

if [[ "${failures}" -gt 0 ]]; then
  echo "[matrix] completed with ${failures} failed workloads" >&2
  exit 1
fi

echo "[matrix] completed successfully"
