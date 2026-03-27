
# 🚀 面向 ARM64 架构的 SDC 自动化 Fuzzing 工具集开发方案

整合**Microprobe 深度定制、A/B 异步架构（离线高吞吐+在线外循环）、以及极简高效的差分测试（QEMU vs gem5）**。

## 一、 项目概述与核心方法论
本项目旨在基于开源微基准测试框架 **Microprobe**，深度定制一套面向 ARM64（如 TaiShan v110 微架构）的静默数据破坏（SDC, Silent Data Corruption）Fuzzing 工具集。

针对物理级/周期级微架构仿真（gem5）极其耗时的痛点，系统摒弃了传统的“单轨在线循环”和笨重的测试框架（如 OpenDCDiag），转而采用 **“A/B 异步架构 + 轻量级差分测试”** 的全新方法论：
1. **纯静态降维打击**：在不运行任何仿真的情况下，通过计算指令级的寄存器存活期（ACE）和数据位宽（IBR），离线生成并筛选出几十万个“高潜在风险”用例。
2. **零开销差分判定**：将裸汇编编译为极简静态 ELF，通过对比 **QEMU（纯指令集逻辑金标准）** 与 **gem5（带故障注入的物理微架构）** 输出的寄存器与内存状态哈希值，精准判定 SDC，零误报、低开销。

---

## 二、 系统架构设计 (A/B 异步架构)

系统由两个完全解耦的引擎组成，中间通过一个轻量级本地 SQLite 数据库（Testcase Vault）作为“弹药库”进行衔接。

### 阶段 A：离线扫街引擎 (High-Throughput Inner Loop)
* **特性**：纯静态、无环境依赖、高并发。
* **工作流**：
    1. 生成器（基于 Microprobe Policies）应用预设的变异算子，疯狂生成 ARM64 汇编序列（重点照顾 NEON, FMA, 跨步场内存访问）。
    2. 覆盖率评估器（基于 Microprobe Passes）解析依赖图，纯静态计算 ACE（寄存器暴露周期）和 IBR（宽数据占比）得分。
    3. 淘汰低分用例，将高价值汇编序列存入 SQLite 数据库，标记为 `PENDING`。

### 阶段 B：在线精准狙击引擎 (Precision Outer Loop)
* **特性**：物理级仿真、精准测试、动态进化。
* **工作流**：
    1. 定期从 SQLite 中拉取综合得分 Top N 的危险用例。
    2. 使用 `BareMetalDiffWrapper` 将汇编包裹为带有**状态哈希打印**功能的静态 ELF。
    3. **差分测试**：
       - 无故障极速跑 QEMU，记录 `Golden_Hash`。
       - 注入瞬态故障跑 gem5 (SE 模式) 并收集 McPAT 功耗，记录 `Gem5_Hash`。
    4. **SDC 判定**：若 gem5 正常退出（无 Crash）但 `Gem5_Hash != Golden_Hash`，判定为 SDC 触发。
    5. 将测试结果和真实功耗回写数据库，高优种子喂给**遗传算法（GA）**进行定向交叉变异，回流到阶段 A。

---

## 三、 微架构源码映射与 AI 开发分步计划

请指导您的 AI 编码助手（如 Cursor / Cline）按以下 5 个 Phase 依次交付代码，严格遵循 Microprobe 源码规范：

### Phase 1: 构建 SDC 敏感特征库 (Features & Context)
* **目标**：提取微架构敏感指令，扩展 Benchmark 上下文。
* **开发任务**：
    1. 在 `targets/arm64/policies/` 创建 `sdc_fuzzing_policy.py`。
    2. 实现 `SDCSensitiveAnalyzer`，调用 `microprobe.target.isa` 筛选出 NEON 的 FMA 指令和 `LDP/STP` 多寄存器访存指令。
    3. 规范化数据传输：将后续计算所需的 `ace_score, ibr_score, power_estimate` 统一挂载到 `benchmark.context` 字典中以实现解耦。

### Phase 2: 开发离线静态 SDC 覆盖率 Pass (Static Analysis)
* **目标**：利用 Microprobe 依赖图解析能力，纯静态地计算启发式风险得分。
* **开发任务**：
    1. 在 `src/microprobe/passes/` 下新建 `sdc_analysis/offline_coverage.py`。
    2. **`StaticACECalculatorPass`**：遍历 `bbl.instructions`，通过 `.sets()` 和 `.uses()` 提取寄存器 Def-Use 链，计算写入到最后读取之间的指令跨度并归一化。
    3. **`StaticIBRCoveragePass`**：检查指令的 `operands`，统计 64-bit/128-bit 指令占比。
    4. **`CapstoneValidationPass`**：反汇编校验语法，剔除非法用例。

### Phase 3: 开发离线引擎与用例金库 (CLI & Database)
* **目标**：高并发生成汇编并进行持久化管理。
* **开发任务**：
    1. **用例金库 (`sdc_vault.py`)**：基于 SQLite 构建 `OfflineTestCases` 表。字段包括 `test_id, asm_content, ace_score, ibr_score, qemu_golden_hash, status`。实现 `fetch_top_k_risky()` 方法（按 `ace*0.6 + ibr*0.4` 降序拉取）。
    2. **离线 CLI (`targets/generic/tools/mp_sdc_offline_gen.py`)**：利用 `multiprocessing.Pool` 多进程调用 Microprobe generator。执行 Phase 2 的 Pass 进行静态打分，过滤后批量存入 SQLite。

### Phase 4: 轻量级 C Wrapper 与差分测试流水线 (The Execution Engine)
* **目标**：抛弃繁重的框架，实现极速、零误报的 SDC 捕获。
* **开发任务**：
    1. **定制 Wrapper (`src/microprobe/code/wrapper.py`)**：编写 `BareMetalDiffWrapper`。它只需生成一个带有 `main()` 的 C 文件，在注入汇编后，**追加一段遍历打印 X0-X30 寄存器值及内存 Checksum 的 C/内联汇编代码**。
    2. **差分判定器 (`run_sdc_differential.py`)**：
       - 调用 `aarch64-linux-gnu-gcc -static` 极速编译 ELF。
       - `subprocess` 跑 `qemu-aarch64` 获取 `Golden_Hash`。
       - `subprocess` 跑 `gem5.opt` (SE 模式) + 故障注入脚本获取 `Gem5_Hash`。
       - 判定逻辑：`if gem5_return_code == 0 and gem5_hash != golden_hash: return SDC_FOUND`。

### Phase 5: 在线遗传算法与闭环优化 (Genetic Algorithm)
* **目标**：根据差分测试的真实反馈，进化 Fuzzing 种群。
* **开发任务**：
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
1. **彻底摒弃重量级框架**：在执行层，绝对不允许使用 OpenDCDiag 或任何复杂的 C++ 夹具。所有的可执行文件必须由裸汇编 + 简单的 C main 函数（仅包含寄存器 Hashing 打印）静态链接而成。
2. **Microprobe 原生扩展**：
   - 绝不重复造轮子。修改指令请使用现有的 `ReplaceOpcodePass`。
   - 自定义分析（如 ACE 和 IBR）必须实现为继承自 `microprobe.passes.Pass` 的类。
3. **数据解耦原则**：各类分析算子计算出的分数，必须统一写入 `benchmark.context['key_name']` 中，不准使用全局变量。
4. **代码质量**：使用严格的 Python 3 Type Hinting；针对 gem5/QEMU 的调用必须做容错处理（try-except 和 timeout 机制）。
```

通过这套降本增效的极致方案，您不仅利用了 Microprobe 强大的指令生成和依赖梳理能力，还巧妙避开了物理仿真极度耗时的死亡陷阱，这是一套具备工业级可用性的 SDC Fuzzing 顶层设计。
