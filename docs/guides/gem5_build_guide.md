# Ubuntu 24.04 ARM Sim Runner Guide

本文档定义仓库当前认可的真实仿真执行面：`Ubuntu 24.04 aarch64`。

规范与当前状态请优先查看根目录：

- `plan.md`
- `progress.md`

## 1. 执行面约定

- `e2e-dev`：开发主机 smoke，只验证控制面、生成和物料化。
- `e2e-sim`：Ubuntu 24.04 ARM 上的真实仿真验收，是默认的端到端口径。
- `e2e-hw`：OpenDCDiag staging / promotion lane，不替代 `e2e-sim`。

如果你在 macOS 上开发，先跑 `e2e-dev`；不要再把 macOS 当成完整仿真 runner。

## 2. Bootstrap

在 Ubuntu 24.04 ARM 主机上执行：

```bash
./scripts/bootstrap_ubuntu_24_04_arm.sh
```

该脚本会安装：

- `build-essential`
- `gcc` / `g++`
- `python3` / `python3-dev` / `python3-pip`
- `python3-pytest`
- `pkg-config`
- `qemu-user`
- `qemu-system-arm`
- `libglib2.0-dev`
- `libpixman-1-dev`
- `meson`
- `ninja-build`
- `scons`
- `swig`
- `protobuf-compiler`
- gem5 / McPAT 常用系统依赖
- 根目录 `requirements-dev.txt` 中声明的 Python 依赖

## 3. 构建 gem5 与 McPAT

```bash
./scripts/build_gem5_linux_arm.sh
./scripts/build_mcpat.sh
```

构建完成后，应至少满足：

```bash
python3 -m sdc_agent.preflight --profile sim --verbose
```

其中关键路径应解析到：

- `qemu-aarch64`
- `qemu-system-aarch64`
- `gem5/build/ARM/gem5.opt`
- `mcpat/mcpat`

如果 `preflight --profile sim` 仍失败，优先修复下面这些系统检查，而不是直接反复运行 build 脚本：

- `pkg_config`
- `python_config`
- `scons`
- `swig`
- `protobuf`

## 4. 运行真实 sim E2E

```bash
python3 tools/sdc_agent.py e2e-sim \
  --output-root artifacts/e2e-sim/smoke
```

统一报告位于：

```text
artifacts/e2e-sim/<run-id>/report.json
```

成功结果至少应包含：

- `phase2.status == INNER_READY`
- `phase4.summary_status in {MATCHED, SDC_FOUND}`
- `cycle.campaign.counts.executed > 0`
- `cycle.evolve.emitted > 0`

## 5. 手动 smoke

仓库提供了一个真实集成 smoke：

```bash
SDC_RUN_REAL_SIM_SMOKE=1 python3 -m pytest tests/test_e2e_sim_integration_smoke.py -q
```

该测试不会在默认快速单测中执行，适合手动验收或 nightly runner。

## 6. macOS 开发者说明

macOS 仍可用于：

- `python3 -m pytest tests -q`
- `python3 -m sdc_agent.preflight --profile dev --verbose`
- `python3 tools/sdc_agent.py e2e-dev`

兼容别名 `e2e-local` 仍保留，但它现在只是 `e2e-dev` 的入口，不再承诺完整仿真闭环。
