# 计划：构造能触发 SDC 的相似测试变体

## 目标

把 22 个测试中与 movbe/mrn_rmw 相似但不触发的候选测试，按三个方向合理修改输入方式/指令序列，构造变体使其也能检出 SDC。验证"触发特征"假设的正向实验，与之前的反向删减探针互补。

## 设计依据（来自已确认的 objdump + 源码分析）

触发基准的依赖链结构（objdump 取证）：

- **mrn_rmw(触发)**: `ldr源A → ldr源B → eor(ALU) → str temp → ldr temp(forwarding背靠背) → str dst`
  - 关键：2 源 load → ALU → store → forwarding → store，**连续依赖链 6 跳**，首尾相扣
- **movbe(触发)**: `ldr w1,[input] → rev(ALU) → str [swapped] → ldr w1,[input](同址重读!) → cmp`
  - 关键：store(swapped) 与 load(input) 异址非 forwarding；**两次 ldr 读同址 input** 走 L1D 阵列重读

不触发候选的差异（已确认）：

- **mrn_nuke(0-fail)**: 1 源 load → store(原值无ALU) → forwarding → store。链 4 跳，少"2源+ALU"
- **mem_disambig(0-fail)**: 2 源(offsets,values) → store(原值) → forwarding。有2源但无ALU，地址随机
- **mrn_pairs(0-fail)**: 1 源 → 8 store → 8 forwarding(load)。同址但时序拉开7条
- **mrn_reloaded(0-fail)**: 1 源 → store → forwarding，sub-word粒度

## 改造方案（按用户选定的三个方向）

### 方向一：加 2 源 load + ALU 依赖链（复刻 mrn_rmw 连续依赖链）

针对 mrn_nuke/mem_disambig——它们缺"2源+ALU"组合。这是 mrn_rmw 与 mrn_nuke**唯一尚未被探针干净测过**的差异（v2 探针 confound：仍 1 源）。

#### 变体 1: mrn_nuke_2src_alu（基于 mrn_nuke，1源→2源+ALU）
- 改 mrn_nuke：src 单源 → srcA+srcB 双源，store 值从原值改为 `a op b`(轮换 add/sub/eor/and)
- 保持骨架完全不变：`store_qword(&temp[i], res); store_qword(&dst[i], load_qword(&temp[i]))`
- 预期：若触发 → "2源+ALU依赖链"是 mrn_rmw 区别于 mrn_nuke 的关键；若仍 0-fail → 该组合非充分

#### 变体 2: mem_disambig_alu（基于 mem_disambig，原值→ALU加工）
- mem_disambig 已是 2 源(offsets,values)，store 原值 → 改为 store `values[i] op offsets[i]`(ALU)
- 保持 pattern1 的 `store(buf+off,val); load(buf+off)` 骨架
- 预期：若触发 → ALU+2源+随机地址组合触发；若 0-fail → 随机地址(非线性)破坏窗口

### 方向二：改同址 L1D 重读模式（movbe 式）

针对 mrn_nuke/mrn_pairs——它们缺"两次 ldr 同址重读"模式。

movbe 精确时序（objdump 取证）：`ldr w1,[input,i] → rev w4,w1(ALU) → str w4,[swapped,i](异址store) → ldr w4,[input,i](同址重读!) → cmp w4,w1`
- 关键：第二次 ldr 读 input（第一次同址），中间隔 `rev + str(异址)`——ALU + 一个异址 store

#### 变体 3: mrn_nuke_recross（基于 mrn_nuke，forwarding→L1D同址重读）
- 改 mrn_nuke：不再 `store temp; load temp`(forwarding)，改为 `load src[i]; rev/eor(ALU); str dst[i](异址); load src[i](同址重读); cmp`
- **精确复刻 movbe 时序**：第一次读 src → ALU(rev) → store 异址(dst) → 第二次读 src(同址) → cmp
- 用 inline asm 固定 `[base, idx, lsl #3]` 寻址（避免寻址模式破坏触发 [[movbe-l1d-variants-schedule-sensitivity]]）
- 预期：若触发 → L1D 同址重读是 movbe 族的独立触发路径，可移植到 mrn_nuke 骨架；若 0-fail → movbe 触发还依赖别的（如 64KB 共享 buffer / w 寄存器 32 位粒度）

### 方向三：调整时序窗口密度（load 次数）

#### 变体 4: mrn_nuke_dense（基于 mrn_nuke，提高 str→ldr 背靠背密度）
- mrn_nuke 从 1024 count → 16384 count（对齐 movbe 的 32768 ldr/轮的量级）
- 测试"load 绝对次数"假设（虽 movbe 32768 触发 / mrn_nuke 24576 不触发已部分证伪，但 mrn_nuke 每轮只 1024，量级差 24 倍）
- 预期：若触发 → 密度有阈值效应；若 0-fail → load 次数非驱动

## 实现细节

### 代码风格（遵循 probe_asm_fwd.cpp 已验证的惯例）
- inline asm 用 `=&r` early-clobber 标记地址寄存器（避免 [[movbe-l1d-variants-schedule-sensitivity]] 的崩溃坑）
- 寻址用 `[base, idx, lsl #3]` 线性寻址（复刻 mrn_rmw objdump，避免 [[movbe-l1d-variants-schedule-sensitivity]] 寻址模式破坏触发）
- buffer/迭代数与基准一致（1024 元素，8KB temp+8KB dst，per-thread）
- 不用 dump 冷分支（[[dump-variant-noremove-report-fail-verified]]：连冷分支都碰会降率，用 report_fail_msg 即可）

### 文件清单（4 个新变体）
- `tests/cpu/misc/mrn_nuke_2src_alu.cpp`（变体1）
- `tests/cpu/memory/mem_disambig_alu.cpp`（变体2）
- `tests/cpu/misc/mrn_nuke_recross.cpp`（变体3）
- `tests/cpu/misc/mrn_nuke_dense.cpp`（变体4）

### meson.build 注册
在 `tests/cpu/meson.build` 的 misc/memory 列表各加一行。

## 验证协议（[[arithmetic-test-sdc-verification-protocol]] 两阶段）
- 阶段1：排除179核（taskset 0-178,180-191）跑60s须0-fail，证明变体可靠
- 阶段2：全核192含179+auto seed跑60s看SDC触发
- 交叉确认：exit:fail + 唯一 result:fail 块数（[[sdc-fail-count-unique-blocks]] 口径，不 grep miscompare 双计）

## 判别逻辑
变体1触发+变体4不触发 → "2源+ALU依赖链"非密度驱动，是依赖结构
变体1不触发 → "2源+ALU"非充分，mrn_rmw 还有未被识别的特征
变体3触发 → L1D同址重读可移植，是独立触发路径
多变体都触发 → 触发是多因素，单变量探针测不出是正常的
