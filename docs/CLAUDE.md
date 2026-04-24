# 🚀 面向 ARM64 架构的 SDC 自动化 Fuzzing 工具集开发方案

整合**Microprobe 深度定制、A/B 异步架构（高频内循环 + 低频外循环）、极简高效的差分测试（QEMU vs gem5），以及最终的硬件验证环（opendcdiag-arm）**。

## 一、 项目概述与核心方法论

本项目旨在基于开源微基准测试框架 **Microprobe**，深度定制一套面向 ARM64（如 TaiShan v110 微架构）的静默数据破坏（SDC, Silent Data Corruption）Fuzzing 工具集。

针对物理级/周期级微架构仿真（gem5）极其耗时的痛点，系统摒弃了传统的“单轨在线循环”，转而采用 **“高频内循环 + 低频外循环 + 最终硬件验证环”** 的方法论：

1. **纯静态降维打击**：在不运行任何仿真的情况下，通过计算指令级的寄存器存活期（ACE）和数据位宽（IBR），离线生成并筛选出几十万个“高潜在风险”用例。
2. **轻量级差分判定**：将裸汇编编译为极简静态 ELF，通过对比 **QEMU（纯指令集逻辑金标准）** 与 **gem5（带故障注入的微架构执行侧）** 输出的寄存器与内存状态哈希值，低成本判定 SDC。
3. **最终硬件验证环**：将外循环筛出的高价值样本推广到 `opendcdiag-arm`，在真实机器上验证检测能力，并把结果回灌数据库。

---

## 二、 系统架构设计（三层闭环）

系统由三个层次组成，中间通过一个轻量级本地 SQLite 数据库（Testcase Vault）作为“弹药库”进行衔接。

### 阶段 A：离线扫街引擎 (High-Throughput Inner Loop)

- **特性**：纯静态、无环境依赖、高并发。
- **工作流**：
  1. 生成器（基于 Microprobe Policies）应用预设的变异算子，疯狂生成 ARM64 汇编序列（重点照顾 NEON, FMA, 跨步场内存访问）。
  2. 覆盖率评估器（基于 Microprobe Passes）解析依赖图，纯静态计算 ACE（寄存器暴露周期）和 IBR（宽数据占比）得分。
  3. 淘汰低分用例，将高价值汇编序列存入 SQLite 数据库，标记为 `PENDING`。

### 阶段 B：在线精准狙击引擎 (Precision Outer Loop)

- **特性**：物理级仿真、精准测试、动态进化。
- **工作流**：
  1. 定期从 SQLite 中拉取综合得分 Top N 的危险用例。
  2. 使用 `BareMetalDiffWrapper` 将汇编包裹为带有**状态哈希打印**功能的静态 ELF。
  3. **差分测试**：
    - 无故障极速跑 QEMU，记录 `Golden_Hash`。
    - 注入瞬态故障跑 gem5 (SE 模式) 并收集 McPAT 功耗，记录 `Gem5_Hash`。
  4. **SDC 判定**：若 gem5 正常退出（无 Crash）但 `Gem5_Hash != Golden_Hash`，判定为 SDC 触发。
  5. 将测试结果和真实功耗回写数据库，高优种子喂给**遗传算法（GA）**进行定向交叉变异，回流到阶段 A。

### 阶段 C：真实硬件验证环 (Hardware Validation Lane)

- **特性**：最低频、最高置信度。
- **工作流**：
  1. 从 SQLite 中选择外循环评分最高、且具备明确检测价值的样本。
  2. 将 testcase 封装成 `opendcdiag-arm` 可运行测试。
  3. 在真实 ARM64 服务器上执行 SDC 检测，并采集 CRC/ECC/checksum 等结果。
  4. 将硬件检测结果回灌数据库，为后续 profile 调优和样本选择提供依据。

---

## 三、 微架构源码映射与 AI 开发分步计划

请指导您的 AI 编码助手（如 Cursor / Cline）按以下 5 个 Phase 依次交付代码，严格遵循 Microprobe 源码规范：

### Phase 1: 构建 SDC 敏感特征库 (Features & Context)

- **目标**：提取微架构敏感指令，扩展 Benchmark 上下文。
- **开发任务**：
  1. 在 `targets/arm64/policies/` 创建 `sdc_fuzzing_policy.py`。
  2. 实现 `SDCSensitiveAnalyzer`，调用 `microprobe.target.isa` 筛选出 NEON 的 FMA 指令和 `LDP/STP` 多寄存器访存指令。
  3. 规范化数据传输：将后续计算所需的 `ace_score, ibr_score, power_estimate` 统一挂载到 `benchmark.context` 字典中以实现解耦。

### Phase 2: 开发离线静态 SDC 覆盖率 Pass (Static Analysis)

- **目标**：利用 Microprobe 依赖图解析能力，纯静态地计算启发式风险得分。
- **开发任务**：
  1. 在 `src/microprobe/passes/` 下新建 `sdc_analysis/offline_coverage.py`。
  2. `**StaticACECalculatorPass`**：遍历 `bbl.instructions`，通过 `.sets()` 和 `.uses()` 提取寄存器 Def-Use 链，计算写入到最后读取之间的指令跨度并归一化。
  3. `**StaticIBRCoveragePass**`：检查指令的 `operands`，统计 64-bit/128-bit 指令占比。
  4. `**CapstoneValidationPass**`：反汇编校验语法，剔除非法用例。

### Phase 3: 开发离线引擎与用例金库 (CLI & Database)

- **目标**：高并发生成汇编并进行持久化管理。
- **开发任务**：
  1. **用例金库 (`sdc_agent/vault.py`)**：基于 SQLite 构建 `OfflineTestCases` 表。字段包括 `test_id, asm_content, ace_score, ibr_score, qemu_golden_hash, status`。实现 `fetch_top_k_risky()` 方法（按 `ace*0.6 + ibr*0.4` 降序拉取）。
  2. **离线 CLI (`targets/generic/tools/mp_sdc_offline_gen.py`)**：利用 `multiprocessing.Pool` 多进程调用 Microprobe generator。执行 Phase 2 的 Pass 进行静态打分，过滤后批量存入 SQLite。

### Phase 4: 轻量级 C Wrapper 与差分测试流水线 (The Execution Engine)

- **目标**：抛弃繁重的框架，实现极速、零误报的 SDC 捕获。
- **开发任务**：
  1. **定制 Wrapper (`src/microprobe/code/wrapper.py`)**：编写 `BareMetalDiffWrapper`。它只需生成一个带有 `main()` 的 C 文件，在注入汇编后，**追加一段遍历打印 X0-X30 寄存器值及内存 Checksum 的 C/内联汇编代码**。
  2. **差分判定器 (`sdc_agent/differential.py`)**：
    - 调用 `aarch64-linux-gnu-gcc -static` 极速编译 ELF。
    - `subprocess` 跑 `qemu-aarch64` 获取 `Golden_Hash`。
    - `subprocess` 跑 `gem5.opt` (SE 模式) + 故障注入脚本获取 `Gem5_Hash`。
    - 判定逻辑：`if gem5_return_code == 0 and gem5_hash != golden_hash: return SDC_FOUND`。

### Phase 5: 在线遗传算法与闭环优化 (Genetic Algorithm)

- **目标**：根据差分测试的真实反馈，进化 Fuzzing 种群。
- **开发任务**：
  1. 在 `src/microprobe/driver/genetic.py` 基础上派生 `SDCFuzzingGeneticDriver`。
  2. **Fitness 函数改造**：将目标函数改为 `(ACE * IBR) / (McPAT_Power + 1)`，优先保留高覆盖低功耗（或极端高功耗易发热）的边界用例。
  3. **变异算子绑定**：强化内存变异，调用 Microprobe 现有内存 Pass 时，强制对 `[Base + Offset]` 注入 ≥8KB 的偏移量步长，用于针对 TaiShan v110 触发 Cache 驱逐（Eviction）。
  4. 将成功引发 SDC 或高分红的子 BBL 通过交叉算子进行重组，注入回 `sdc_vault` 数据库。

---

## 四、 给 AI 编码助手的全局系统提示词 (Master System Prompt)

在开启 IDE (如 VSCode + Cursor) 准备写代码时，请先将以下内容发送给 AI：

```markdown
# 角色定义
你是一个高级 C/Python 系统软件工程师和硬件安全架构师。你精通 ARM64 ISA、计算机微架构（特别是 Cache/OoO 行为），并深入掌握 Microprobe 框架的内部机制（Passes, Policies, Target ISA 抽象）。

# 核心任务
我们需要在 Microprobe 源码基础上扩展一套“面向 ARM64 的 SDC 自动化 Fuzzing 框架”。该框架由“离线静态分析扫街生成（SQLite 存储）”与“在线轻量级差分测试（QEMU vs gem5 SE模式）”组成。

# 架构约束与编码规范（必须遵守！）
1. **高频/低频仿真执行层必须保持轻量**：在内循环和外循环的仿真执行层，不允许使用 OpenDCDiag 或其他复杂 C++ 夹具。所有快速执行工件都应由裸汇编 + 简单的 C main 函数（仅包含寄存器 Hashing 打印）静态链接而成。`OpenDCDiag` 只允许出现在最终硬件验证环。
2. **Microprobe 原生扩展**：
   - 绝不重复造轮子。修改指令请使用现有的 `ReplaceOpcodePass`。
   - 自定义分析（如 ACE 和 IBR）必须实现为继承自 `microprobe.passes.Pass` 的类。
3. **数据解耦原则**：各类分析算子计算出的分数，必须统一写入 `benchmark.context['key_name']` 中，不准使用全局变量。
4. **代码质量**：使用严格的 Python 3 Type Hinting；针对 gem5/QEMU 的调用必须做容错处理（try-except 和 timeout 机制）。
5. **编译规范**：生成的 C 源码必须使用 `-static -O0` 编译以确保可重现行为；裸机 ELF 使用定制 linker script 且 `-nostdlib`；不同编译路径的 compiler 候选顺序由 `sdc_agent/tooling.py` 统一解析。
```

通过这套降本增效的极致方案，您不仅利用了 Microprobe 强大的指令生成和依赖梳理能力，还巧妙避开了物理仿真极度耗时的死亡陷阱，这是一套具备工业级可用性的 SDC Fuzzing 顶层设计。

---

## 五、 编译问题记录与排查指南

### 5.1 编译路径总览

项目包含三条独立的测试用例编译路径和三个子项目的源码构建。

#### 测试用例编译路径

| 路径 | 源码入口 | 编译器 | 关键 Flags | 产物 | 用途 |
| --- | --- | --- | --- | --- | --- |
| 用户态静态 ELF | `sdc_agent/differential.py` `compile_static_elf()` | `aarch64-linux-gnu-gcc`（或 `tooling.py` 解析结果） | `-static -O0 -g0 -fno-inline` | Linux user-mode 静态 ELF | QEMU user-mode + gem5 SE 差分测试 |
| 裸机 Semihost ELF | `sdc_agent/phase2_validation.py` `build_semihost_validation_elf()` | 同上 | `-nostdlib -static -O0 -ggdb -lgcc -Wl,-T,kernel.ld` | bare-metal ELF（依赖 `boot.S`） | QEMU system + gem5 baremetal 验证 |
| 功耗分析裸机 ELF | `sdc_agent/power_analysis.py` | `aarch64-elf-gcc`（bare-metal 工具链） | `-nostdlib -static -O0 -T linker.ld` | bare-metal ELF | gem5 SE 功耗采集 + McPAT |

#### 子项目构建

| 子项目 | 构建系统 | 构建脚本 | 产物路径 |
| --- | --- | --- | --- |
| QEMU | Meson + Make | `scripts/build_qemu_headless.sh` | `qemu/build/qemu-aarch64`, `qemu/build/qemu-system-aarch64` |
| gem5 | SCons | `scripts/build_gem5_linux_arm.sh` | `gem5/build/ARM/gem5.opt` |
| McPAT | Make | `scripts/build_mcpat.sh` | `mcpat/mcpat` |

### 5.2 编译器解析规则

`sdc_agent/tooling.py` 中 `resolve_local_tools()` 按以下优先级解析 ARM64 编译器：

1. 调用方显式传入的 `compiler` 参数
2. 环境变量 `SDC_COMPILER`
3. PATH 搜索候选列表（按顺序尝试）：
   - `aarch64-linux-gnu-gcc`（跨平台交叉编译器）
   - `aarch64-conda-linux-gnu-gcc`（Conda 环境）
   - 仅在 **Linux aarch64** 主机上额外尝试：`gcc`、`cc`（原生编译器）

功耗分析路径 (`power_analysis.py`) 使用独立的 `aarch64-elf-gcc` 解析逻辑，候选路径为 `/opt/homebrew/bin/aarch64-elf-gcc`、`/usr/local/bin/aarch64-elf-gcc`、`aarch64-elf-gcc`。

### 5.3 已知问题与排查

#### P1: 交叉编译器缺失

**现象**：`compile_static_elf` 返回 `returncode=-2`（`FileNotFoundError`），或 `preflight` 报告 `install_compiler`。

**原因**：主机上未安装 `aarch64-linux-gnu-gcc`。在非 ARM64 Linux 主机上，原生 `gcc` 不会被自动候选。

**解决**：
```bash
# Ubuntu / Debian
sudo apt-get install gcc-aarch64-linux-gnu
# 或在 Ubuntu 24.04 ARM 上直接使用原生 gcc（tooling.py 自动检测）

# 验证
aarch64-linux-gnu-gcc --version
```

#### P2: 系统构建依赖缺失

**现象**：`preflight --profile sim` 报告 `pkg_config`、`python_config`、`scons`、`swig`、`protobuf` 等检查失败；gem5 或 QEMU 构建脚本中途报错退出。

**解决**：在 Ubuntu 24.04 ARM 上执行 bootstrap 脚本一次性安装所有依赖：
```bash
./scripts/bootstrap_ubuntu_24_04_arm.sh
```

如果无法使用 `sudo`，需要手动联系管理员安装以下关键包：
`build-essential pkg-config python3-dev scons swig protobuf-compiler libprotobuf-dev libglib2.0-dev libpixman-1-dev meson ninja-build`

#### P3: 内联汇编编译失败

**现象**：`compile_static_elf` 返回非零 `returncode`，`stderr` 包含 `Error: operand ...` 或 `Error: unknown mnemonic`。

**原因**：Microprobe 生成器产出的汇编序列包含非法指令或 operand 格式错误。已知案例包括 ARM64 operand 定义中三条 relative immediate 使用了错误字段。

**排查**：
1. 检查 `stderr` 中的具体汇编报错行号和指令
2. 对照 `microprobe/targets/arm64/` 下的 ISA 定义确认 operand 合法性
3. 当 `CapstoneValidationPass` 开启时，非法指令应在静态分析阶段被剔除
4. 如果本地缺少 assembler 工具链，catalog 校验会标记 `toolchain_limited` 并降级为 best-effort

#### P4: 静态链接失败

**现象**：`-static` 链接报错 `cannot find -lc` 或 `cannot find -lpthread`。

**原因**：宿主机缺少 glibc 静态库。

**解决**：
```bash
# Ubuntu / Debian（原生 ARM64）
sudo apt-get install libc6-dev
# 交叉编译场景
sudo apt-get install gcc-aarch64-linux-gnu
```

#### P5: 裸机 ELF Linker 问题

**现象**：`build_semihost_validation_elf` 中 `boot.S` 编译或链接失败。

**已知场景**：

- **`boot.S` 路径不存在**：Phase 2 依赖 `qemu/tests/tcg/aarch64/system/boot.S`。如果 QEMU 子树不完整（如浅克隆），该文件可能缺失。确保 `qemu/` 子树包含 `tests/tcg/` 目录。
- **`kernel.ld` 内存区段冲突**：`phase2_validation.py` 生成的 linker script 将 `.text` 放在 `ORIGIN = 2 << 30`（2GB）。如果生成的测试用例数据段过大，可能超出 `LENGTH = 2M` 限制，需要调整 `LENGTH` 参数。
- **`-lgcc` 找不到**：裸机工具链可能未附带 `libgcc.a`。确认使用的编译器对应的 `libgcc` 路径可达。

#### P6: gem5 构建问题

**现象**：`build_gem5_linux_arm.sh` 失败。

**已知场景**：

- **仅支持 Linux aarch64 原生构建**：脚本首先检查 `uname -m == aarch64`，非 ARM64 主机会直接退出。gem5 的交叉编译不在项目支持范围内。
- **protobuf 版本不兼容**：gem5 对 protobuf 版本有严格要求。Ubuntu 24.04 的 `protobuf-compiler` + `libprotobuf-dev` 是经过验证的基线。更新版本的发行版（如 Ubuntu 25.10）可能存在 ABI 不兼容问题。
- **SCons 版本**：gem5 要求 SCons >= 3.0。通过 `scons --version` 确认。
- **内存不足**：gem5 完整构建需要约 8GB+ 内存。在内存受限的 CI 环境中，降低并行度：`python3 -m SCons -j2 build/ARM/gem5.opt`。

#### P7: QEMU 构建问题

**现象**：`build_qemu_headless.sh` 失败。

**已知场景**：

- **Meson 版本**：QEMU 要求 Meson >= 0.63.0。`meson --version` 确认。
- **缺少 `libglib2.0-dev` / `libpixman-1-dev`**：configure 阶段报错。通过 `bootstrap_ubuntu_24_04_arm.sh` 安装。
- **`--target-list` 配置**：构建脚本已限定 `aarch64-softmmu,aarch64-linux-user`，如需其他 target 需手动调整。

#### P8: McPAT 构建问题

**现象**：`build_mcpat.sh` 失败。

**已知场景**：

- **C++ 标准兼容性**：McPAT 源码较旧，部分 GCC 版本需要 `-std=c++14` 或更低标准。
- **Boost 依赖**：需要 `libboost-all-dev`，由 bootstrap 脚本安装。

### 5.4 快速排查流程

遇到编译相关问题时，按以下顺序排查：

```
1. 运行 preflight 诊断
   python3 -m sdc_agent.preflight --profile sim --verbose

2. 查看 preflight 输出中的 missing_steps 列表，
   按提示执行对应的 bootstrap / build 脚本

3. 如果是首次搭建环境
   ./scripts/bootstrap_ubuntu_24_04_arm.sh   # 系统依赖
   ./scripts/build_qemu_headless.sh          # QEMU（可选，sim 用 apt 包即可）
   ./scripts/build_gem5_linux_arm.sh         # gem5
   ./scripts/build_mcpat.sh                  # McPAT

4. 如果是测试用例编译失败（非环境问题）
   - 检查 DifferentialResult.compile.stderr 中的具体报错
   - 确认 asm_content 是否通过了 CapstoneValidationPass
   - 尝试手动编译生成的 .c 文件定位问题行

5. 如果仍然无法解决
   - 确认主机架构：uname -m（预期 aarch64）
   - 确认发行版：cat /etc/os-release（基线为 Ubuntu 24.04）
   - 检查 progress.md 中是否有相关记录
   - 非基线发行版（如 Ubuntu 25.10）只能做 best-effort 验证
```
