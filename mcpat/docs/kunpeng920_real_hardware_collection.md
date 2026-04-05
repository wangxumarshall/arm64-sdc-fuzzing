# Kunpeng920 Real-Hardware Collection Guide

## Goal

Use public kernel/UADK interfaces plus real-machine measurements to close the
remaining Kunpeng920 McPAT calibration gaps that cannot be recovered from public
internet sources alone.

This guide separates:

- **hard structural constants** recovered from kernel/UADK source
- **runtime counters** exposed by Linux debugfs/perf
- **still-missing calibration fields** that require real-machine power data

## Hard Constants Recovered From Kernel Source

### Queue Manager

Source:

- `linux/drivers/crypto/hisilicon/qm.c`

Recovered constants:

- `QM_TOTAL_QP_NUM_CAP`: `0x400` on QM HW v2/v3, `0x1000` on QM HW v1
- `QM_FUNC_MAX_QP_CAP`: `0x400` on QM HW v2/v3, `0x1000` on QM HW v1
- `QM_SUPPORT_SVA_PREFETCH`: advertised through `QM_FUNC_CAPS_REG`

Interpretation:

- Kunpeng920-class accelerators should be treated as **1024-QP-class** devices
  unless `cap_regs` from the target machine say otherwise.

### HPRE

Sources:

- `linux/drivers/crypto/hisilicon/hpre/hpre_main.c`
- `linux/drivers/crypto/hisilicon/hpre/hpre.h`

Recovered constants:

- `HPRE_PF_DEF_Q_NUM = 64`
- `HPRE_CLUSTERS_NUM_MAX = 4`
- `HPRE_CORE_INFO` capability value for v2 path: `0x420802`
- `HPRE_CLUSTER_NUM_CAP`: 4 clusters on v2
- `HPRE_CORE_TYPE_NUM_CAP`: 2
- `HPRE_CORE_NUM_CAP`: 8 total cores on v2
- `HPRE_CLUSTER_CORE_NUM_CAP`: 2 cores per cluster on v2
- DFX counters:
  - `send_cnt`
  - `recv_cnt`
  - `send_fail_cnt`
  - `send_busy_cnt`
  - `over_thrhld_cnt`
  - `overtime_thrhld`
  - `invalid_req_cnt`

Important caveat:

- The mainline driver capability tables indicate that **v2 HPRE exposes only the
  low bitmap (`0x03`)**, which maps to RSA/DH-class capability in the driver.
  Treat `cap_regs` on the target machine as the runtime source of truth before
  assuming ECC/SM2/X25519/X448 are hardware-backed on Kunpeng920.

### SEC

Sources:

- `linux/drivers/crypto/hisilicon/sec2/sec_main.c`
- `linux/drivers/crypto/hisilicon/sec2/sec.h`

Recovered constants:

- `SEC_PF_DEF_Q_NUM = 256`
- `SEC_QUEUE_NUM_V1 = 4096`
- `SEC_CTX_Q_NUM_DEF = 2`
- `SEC_CTX_Q_NUM_MAX = 32`
- `SEC_SQE_SIZE = 128`
- `SEC_CORE_INFO` capability value: `0x110404`
- `SEC_CLUSTER_NUM_CAP = 1`
- `SEC_CORE_TYPE_NUM_CAP = 1`
- `SEC_CORE_NUM_CAP = 4`
- `SEC_CORES_PER_CLUSTER_NUM_CAP = 4`
- DFX counters:
  - `send_cnt`
  - `recv_cnt`
  - `send_busy_cnt`
  - `recv_busy_cnt`
  - `err_bd_cnt`
  - `invalid_req_cnt`
  - `done_flag_cnt`

### ZIP

Sources:

- `linux/drivers/crypto/hisilicon/zip/zip_main.c`
- `linux/drivers/crypto/hisilicon/zip/zip.h`

Recovered constants:

- `HZIP_PF_DEF_Q_NUM = 64`
- `HZIP_QUEUE_NUM_V1 = 4096`
- `HZIP_CTX_Q_NUM_DEF = 2`
- `HZIP_SQE_SIZE = 128`
- `ZIP_CORE_INFO` capability value for v2 path: `0x12080206`
- `ZIP_CLUSTER_NUM_CAP = 1`
- `ZIP_CORE_TYPE_NUM_CAP = 2`
- `ZIP_CORE_NUM_CAP = 8` on v2
- `ZIP_CLUSTER_COMP_NUM_CAP = 2`
- `ZIP_CLUSTER_DECOMP_NUM_CAP = 6`
- debugfs core layout is emitted as:
  - `comp_core0`
  - `comp_core1`
  - `decomp_core0..5`
- DFX counters:
  - `send_cnt`
  - `recv_cnt`
  - `send_busy_cnt`
  - `err_bd_cnt`

Additional driver constants:

- `HZIP_SHAPER_RATE_COMPRESS = 750`
- `HZIP_SHAPER_RATE_DECOMPRESS = 140`

## UADK Benchmark Harness Constants

These are **benchmark-harness constants**, not silicon constants, but they are
useful when reproducing a consistent calibration setup.

### HPRE benchmark harness

Source:

- `Linaro/uadk/uadk_tool/benchmark/hpre_uadk_benchmark.c`

Useful constants:

- `SQE_SIZE = 128`
- `POOL_MULTIPLY_FACTOR = 2`
- RSA/DH/ECDH/ECDSA/SM2/X25519/X448 all have dedicated benchmark paths

### SEC benchmark harness

Source:

- `Linaro/uadk/uadk_tool/benchmark/sec_uadk_benchmark.c`

Useful constants:

- `SQE_SIZE = 128`
- `SEC_PERF_AUTH_SIZE = 16`
- Supports cipher / digest / AEAD benchmark paths

### ZIP benchmark harness

Source:

- `Linaro/uadk/uadk_tool/benchmark/zip_uadk_benchmark.c`

Useful constants:

- `CHUNK_SIZE = 128 * 1024`
- `COMPRESSION_RATIO_FACTOR = 0.7`
- `MAX_UNRECV_PACKET_NUM = 1`
- stream mode is explicitly not used in async mode

## Remaining Missing Fields

These are the fields that still cannot be recovered with 100% accuracy from
public internet sources:

### McPAT custom block calibration fields

- `custom_hccs_area`
- `custom_hccs_static_power`
- `custom_hccs_switch_energy`
- `custom_hpre_area`
- `custom_hpre_static_power`
- `custom_hpre_switch_energy`
- `custom_sec_area`
- `custom_sec_static_power`
- `custom_sec_switch_energy`
- `custom_zip_area`
- `custom_zip_static_power`
- `custom_zip_switch_energy`

### Why they are still missing

- Public docs expose topology, queues, algorithm support, debugfs counters, and
  some throughput benchmarks.
- Public docs do **not** expose module-level area, leakage, or per-transaction
  energy constants for HCCS/HPRE/SEC/ZIP.

## What To Collect On Real Hardware

### A. One-time structural snapshot

Collect once per machine / firmware version:

- `cap_regs` for:
  - `hisi_hpre`
  - `hisi_sec2`
  - `hisi_zip`
- `perf list` filtered to:
  - `hisi_sccl`
  - `hisi_pcie`
  - `hns3_pmu`
- sysfs PMU descriptions under `/sys/bus/event_source/devices/`
- `lspci -nn`
- `uname -a`
- `lscpu`

Purpose:

- Confirm actual device generation and capability bitmaps.
- Avoid relying on the driver’s default capability tables when firmware differs.

### B. Runtime accelerator counters

Collect before/after each workload:

- `hisi_hpre/*/hpre_dfx/*`
- `hisi_sec2/*/sec_dfx/*`
- `hisi_zip/*/zip_dfx/*`

Purpose:

- Drive `switch_count`
- derive `activation_factor`
- validate queue saturation and reject-path behavior

### C. Uncore traffic counters

Collect with `perf stat`:

- `hisi_sccl*_hha*/...`
- `hisi_sccl*_l3c*/...`
- `hisi_sccl*_ddrc*/...`
- `hisi_pcie*_core*/...`
- `hns3_pmu_sicl_*/...`

Purpose:

- `HCCS`: infer coherence/inter-die/home-agent activity
- `L3/DDRC`: separate memory-system contribution from accelerator contribution
- `PCIe/RoCE`: correlate off-chip traffic with controller/custom-block activity

### D. Power measurements

Collect at the same time as counters:

- board-level power if only package power is available
- rail-level power if available for:
  - CPU package
  - memory
  - NIC / PCIe
  - accelerator power rails
- temperature
- frequency / governor state

Without this category, you can fit **activity**, but not **energy constants**.

## Recommended Workload Matrix

### HCCS / memory / uncore isolation

- STREAM or memcpy-style bandwidth benchmark with local NUMA binding
- remote-NUMA memory bandwidth benchmark
- multi-socket traffic benchmark if available

### HPRE

- RSA2048 sign/verify
- RSA4096 sign/verify
- DH phase1 / phase2 if supported

### SEC

- AES-128-CBC
- AES-128-GCM
- SM4-CBC
- SM3

### ZIP

- zlib compress
- zlib decompress
- gzip compress
- gzip decompress

### PCIe

- `fio` against downstream NVMe
- traffic isolated to one root port where possible

### RoCE

- `ib_write_bw`
- `ib_send_bw`
- `ib_write_lat`

## Suggested Calibration Sequence

1. Collect idle baseline with all counters and rails.
2. Run one isolated workload class at a time.
3. For each run, record:
   - workload command
   - packet size / key size
   - thread count
   - ctx count
   - duration
   - before/after counter snapshots
   - power / temperature / frequency
4. Fit custom-block `switch_energy` first.
5. Fit `static_power` from idle + near-idle states.
6. Fit `area` only if you also have floorplan / die-photo / internal estimates;
   otherwise keep it as an explicit approximation.

## Ready-To-Use Script

Use:

- [collect_kunpeng920_counters.sh](/Users/wangxu/1-project/sdc-fuzzing/mcpat/tools/collect_kunpeng920_counters.sh)
- [build_kunpeng920_calibration.py](/Users/wangxu/1-project/sdc-fuzzing/mcpat/tools/build_kunpeng920_calibration.py)

Example:

```bash
sudo mcpat/tools/collect_kunpeng920_counters.sh \
  --out-dir artifacts/kunpeng920-rsa2048 \
  --perf-events "hisi_sccl0_hha0/rx_operations/,hisi_sccl0_ddrc0/flux_wr/" \
  --cmd "uadk_tool benchmark --help && sleep 10"
```

The script:

- snapshots accelerator debugfs counters before/after
- snapshots PMU sysfs descriptions
- records environment metadata
- optionally wraps the workload in `perf stat`
- computes numeric before/after deltas for debugfs and powercap/hwmon files

Supported usage is limited to two modes:

1. Manual explicit calibration

First synthesize a runtime calibration JSON:

```bash
python3 mcpat/tools/build_kunpeng920_calibration.py \
  artifacts/kunpeng920-calibration-runs \
  -o artifacts/kunpeng920-calibration-runs/kunpeng920_calibration.json
```

Then pass it explicitly to `pypat`:

```bash
python3 -m pypat /path/to/m5out \
  --template-profile arm64-kunpeng920 \
  --calibration-file artifacts/kunpeng920-calibration-runs/kunpeng920_calibration.json
```

2. Automatic calibration

Let `pypat` synthesize and apply the calibration on the fly:

```bash
python3 -m pypat /path/to/m5out \
  --template-profile arm64-kunpeng920 \
  --calibration-dataset artifacts/kunpeng920-calibration-runs
```

## Minimum Deliverable For McPAT Calibration

For each workload row, persist at least:

- `workload_name`
- `duration_s`
- `threads`
- `ctxs`
- `packet_or_key_size`
- `hpre_send_delta`
- `hpre_recv_delta`
- `sec_send_delta`
- `sec_recv_delta`
- `zip_send_delta`
- `zip_recv_delta`
- `hha/l3c/ddrc/pcie/roce perf counters`
- `total_power_w`
- `temperature_c`
- `cpu_freq_mhz`

That is the minimum dataset needed to turn the current Kunpeng920 custom blocks
from explicit placeholders into fitted McPAT coefficients.
