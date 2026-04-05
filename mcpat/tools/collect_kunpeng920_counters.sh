#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collect_kunpeng920_counters.sh --out-dir DIR --cmd "WORKLOAD"

Options:
  --out-dir DIR         Output directory for snapshots and logs.
  --cmd CMD             Workload command to execute.
  --perf-events EVENTS  Optional perf event list for "perf stat -a -e".
  --label NAME          Optional label for metadata.

Environment:
  PERF_EVENTS           Alternative way to pass perf event list.

Examples:
  sudo mcpat/tools/collect_kunpeng920_counters.sh \
    --out-dir artifacts/kunpeng920-rsa2048 \
    --perf-events "hisi_sccl0_hha0/rx_operations/" \
    --cmd "sleep 10"
EOF
}

OUT_DIR=""
WORKLOAD_CMD=""
PERF_EVENTS="${PERF_EVENTS:-}"
LABEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --cmd)
      WORKLOAD_CMD="$2"
      shift 2
      ;;
    --perf-events)
      PERF_EVENTS="$2"
      shift 2
      ;;
    --label)
      LABEL="$2"
      shift 2
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

if [[ -z "${OUT_DIR}" || -z "${WORKLOAD_CMD}" ]]; then
  usage >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

BEFORE_DIR="${OUT_DIR}/before"
AFTER_DIR="${OUT_DIR}/after"
META_DIR="${OUT_DIR}/meta"
DELTA_DIR="${OUT_DIR}/delta"

mkdir -p "${BEFORE_DIR}" "${AFTER_DIR}" "${META_DIR}" "${DELTA_DIR}"

capture_text() {
  local target="$1"
  shift
  if "$@" >"${target}" 2>&1; then
    return 0
  fi
  echo "command failed: $*" >"${target}"
}

snapshot_numeric_tree() {
  local root="$1"
  local outfile="$2"
  : >"${outfile}"
  if [[ ! -d "${root}" ]]; then
    return 0
  fi
  while IFS= read -r file; do
    local value
    value="$(tr -d '\0' <"${file}" 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
    if [[ "${value}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
      printf '%s\t%s\n' "${file}" "${value}" >>"${outfile}"
    fi
  done < <(find "${root}" -type f | sort)
}

snapshot_debugfs_group() {
  local group="$1"
  local outdir="$2"
  mkdir -p "${outdir}"
  if [[ ! -d "/sys/kernel/debug/${group}" ]]; then
    return 0
  fi

  capture_text "${outdir}/tree.txt" find "/sys/kernel/debug/${group}" -maxdepth 4 -print
  snapshot_numeric_tree "/sys/kernel/debug/${group}" "${outdir}/numeric.tsv"

  while IFS= read -r cap_file; do
    local rel
    rel="${cap_file#/sys/kernel/debug/${group}/}"
    mkdir -p "${outdir}/$(dirname "${rel}")"
    capture_text "${outdir}/${rel}" cat "${cap_file}"
  done < <(find "/sys/kernel/debug/${group}" -type f \( -name 'cap_regs' -o -name 'regs' \) | sort)
}

snapshot_event_source_tree() {
  local outdir="$1"
  mkdir -p "${outdir}"
  while IFS= read -r devdir; do
    local name
    name="$(basename "${devdir}")"
    mkdir -p "${outdir}/${name}"
    capture_text "${outdir}/${name}/type.txt" cat "${devdir}/type"
    capture_text "${outdir}/${name}/cpumask.txt" cat "${devdir}/cpumask"
    capture_text "${outdir}/${name}/format.txt" find "${devdir}/format" -type f -maxdepth 1 -print
    capture_text "${outdir}/${name}/events.txt" find "${devdir}/events" -type f -maxdepth 1 -print
    while IFS= read -r f; do
      local rel
      rel="${f#${devdir}/}"
      mkdir -p "${outdir}/${name}/$(dirname "${rel}")"
      capture_text "${outdir}/${name}/${rel}" cat "${f}"
    done < <(find "${devdir}" \( -path '*/events/*' -o -path '*/format/*' \) -type f | sort)
  done < <(find /sys/bus/event_source/devices -maxdepth 1 -type d \
    \( -name 'hisi_*' -o -name 'hns3*' \) | sort)
}

snapshot_hwmon_numeric() {
  local outfile="$1"
  : >"${outfile}"
  if [[ ! -d /sys/class/hwmon ]]; then
    return 0
  fi
  while IFS= read -r file; do
    local value
    value="$(tr -d '\0' <"${file}" 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
    if [[ "${value}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
      printf '%s\t%s\n' "${file}" "${value}" >>"${outfile}"
    fi
  done < <(find /sys/class/hwmon -type f \
    \( -name 'power*_input' -o -name 'energy*_input' -o -name 'temp*_input' -o -name 'curr*_input' -o -name 'in*_input' \) | sort)
}

snapshot_powercap_numeric() {
  local outfile="$1"
  : >"${outfile}"
  if [[ ! -d /sys/class/powercap ]]; then
    return 0
  fi
  while IFS= read -r file; do
    local value
    value="$(tr -d '\0' <"${file}" 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
    if [[ "${value}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
      printf '%s\t%s\n' "${file}" "${value}" >>"${outfile}"
    fi
  done < <(find /sys/class/powercap -type f \
    \( -name 'energy_uj' -o -name 'max_energy_range_uj' -o -name 'power_uw' \) | sort)
}

compute_delta() {
  local before="$1"
  local after="$2"
  local out="$3"
  awk -F '\t' '
    NR==FNR { before[$1]=$2; next }
    {
      prev = ($1 in before) ? before[$1] : ""
      if (prev == "") {
        printf "%s\t\t%s\t\n", $1, $2
      } else {
        printf "%s\t%s\t%s\t%.10f\n", $1, prev, $2, ($2 - prev)
      }
    }
  ' "${before}" "${after}" >"${out}"
}

capture_metadata() {
  printf 'label=%s\n' "${LABEL}" >"${META_DIR}/run.env"
  printf 'command=%s\n' "${WORKLOAD_CMD}" >>"${META_DIR}/run.env"
  printf 'perf_events=%s\n' "${PERF_EVENTS}" >>"${META_DIR}/run.env"
  capture_text "${META_DIR}/date.txt" date -Iseconds
  capture_text "${META_DIR}/uname.txt" uname -a
  capture_text "${META_DIR}/lscpu.txt" lscpu
  capture_text "${META_DIR}/lsblk.txt" lsblk
  capture_text "${META_DIR}/lspci.txt" lspci -nn
  capture_text "${META_DIR}/numactl.txt" numactl --hardware
  capture_text "${META_DIR}/perf_list.txt" perf list
}

capture_phase() {
  local phase_dir="$1"
  mkdir -p "${phase_dir}"
  snapshot_debugfs_group "hisi_hpre" "${phase_dir}/hisi_hpre"
  snapshot_debugfs_group "hisi_sec2" "${phase_dir}/hisi_sec2"
  snapshot_debugfs_group "hisi_zip" "${phase_dir}/hisi_zip"
  snapshot_event_source_tree "${phase_dir}/event_sources"
  snapshot_hwmon_numeric "${phase_dir}/hwmon.tsv"
  snapshot_powercap_numeric "${phase_dir}/powercap.tsv"
}

run_workload() {
  local start_epoch
  local end_epoch
  local rc

  start_epoch="$(date +%s)"
  printf 'workload_start_epoch_s=%s\n' "${start_epoch}" >>"${META_DIR}/run.env"
  if [[ -n "${PERF_EVENTS}" ]] && command -v perf >/dev/null 2>&1; then
    set +e
    perf stat -a -x, -o "${OUT_DIR}/perf_stat.csv" -e "${PERF_EVENTS}" -- \
      bash -lc "${WORKLOAD_CMD}" >"${OUT_DIR}/workload.stdout.log" 2>"${OUT_DIR}/workload.stderr.log"
    rc=$?
    set -e
  else
    set +e
    bash -lc "${WORKLOAD_CMD}" >"${OUT_DIR}/workload.stdout.log" 2>"${OUT_DIR}/workload.stderr.log"
    rc=$?
    set -e
  fi
  end_epoch="$(date +%s)"
  printf 'workload_end_epoch_s=%s\n' "${end_epoch}" >>"${META_DIR}/run.env"
  printf 'workload_duration_s=%s\n' "$(( end_epoch - start_epoch ))" >>"${META_DIR}/run.env"
  printf 'workload_exit_code=%s\n' "${rc}" >>"${META_DIR}/run.env"
  return "${rc}"
}

capture_metadata
capture_phase "${BEFORE_DIR}"
run_workload
capture_phase "${AFTER_DIR}"

compute_delta "${BEFORE_DIR}/hisi_hpre/numeric.tsv" "${AFTER_DIR}/hisi_hpre/numeric.tsv" "${DELTA_DIR}/hisi_hpre.tsv"
compute_delta "${BEFORE_DIR}/hisi_sec2/numeric.tsv" "${AFTER_DIR}/hisi_sec2/numeric.tsv" "${DELTA_DIR}/hisi_sec2.tsv"
compute_delta "${BEFORE_DIR}/hisi_zip/numeric.tsv" "${AFTER_DIR}/hisi_zip/numeric.tsv" "${DELTA_DIR}/hisi_zip.tsv"
compute_delta "${BEFORE_DIR}/hwmon.tsv" "${AFTER_DIR}/hwmon.tsv" "${DELTA_DIR}/hwmon.tsv"
compute_delta "${BEFORE_DIR}/powercap.tsv" "${AFTER_DIR}/powercap.tsv" "${DELTA_DIR}/powercap.tsv"

echo "Kunpeng920 collection finished: ${OUT_DIR}"
