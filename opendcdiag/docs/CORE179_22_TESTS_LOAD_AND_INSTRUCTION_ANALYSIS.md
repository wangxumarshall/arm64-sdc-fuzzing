# CORE179 SDC：22 个测试用例负载与 ARMv8 指令逐个分析

> 日期：2026-08-31
> 范围：逐个完整读完 `tests/cpu/` 下 22 个测试用例源码，分析各自检测的**负载条件**和压测的 **ARMv8/AArch64 指令**（Kunpeng 920 = ARMv8.1-A，L1D 64KB）。
> 数据来源：源码逐行核对（4 个 agent 并行各读一组，每个文件从首行读到末行，无片段截断）。
> 目的：为 179 核 SDC 研究判定"哪些测试走 store→load forwarding/L1D 路径（179 触发路径）、哪些不走、哪些在 ARM64 上不可用"。

---

## 一、总览表（22 个）

按"是否走 store→load forwarding / L1D 路径"分组（这是与 179 SDC 触发路径的相关性主线）。

### A. 走 store→load forwarding 路径（与 179 SDC 触发路径相关）

| 测试名 | 源文件 | 一句话功能 | str→ldr 形态 | 时序间隔 | aarch64 分支 | 检错 |
|---|---|---|---|---|---|---|
| mrn_rmw | misc/mrn_rmw.cpp | ALU(add/sub/xor/and)+str→ldr 同址转发 | 同址紧贴 | 0 间隔 | 有(内联 asm) | memcmp+report_fail |
| mrn_nuke | misc/mrn_nuke.cpp | 纯拷贝 str→ldr 同址转发（压 store buffer/renaming） | 同址紧贴 | 0 间隔 | 有(内联 asm) | memcmp+report_fail |
| mrn_pairs | misc/mrn_pairs.cpp | 8 路展开：8 store 后 8 load | 同址但拉开 | 7 条 store 间隔 | 有(内联 asm) | memcmp+report_fail |
| mrn_reloaded | misc/mrn_reloaded.cpp | 1/4/8 字节三粒度 str→ldr 同址 | 同址紧贴(三宽度) | 0 间隔 | 有(内联 asm) | 逐元素+report_fail(带索引) |
| mem_disambiguation | memory/mem_disambiguation.cpp | 三模式压 store→load forwarding（全宽/部分重叠/重复 store） | 同址+部分重叠 | 模式1紧贴/模式3重复 | 有(内联 asm) | report_fail(三处) |
| partial_store_forwarding | misc/partial_store_forwarding.cpp | 随机位宽 store→load 部分重叠+shadow 比对 | 同址部分重叠 | 随机 | 无(纯 C volatile) | report_fail(带 offset/size) |
| part_store_fwd_jit | jit/part_store_fwd_jit.cpp | JIT 生成"窄 store+紧接不同位宽 load 同址"（partial forwarding） | 同址紧贴(JIT) | 最窄(函数内背靠背) | 有(JIT emit_word) | report_fail(带 pattern) |
| atomic_seq_cst | atomic/atomic_seq_cst.cpp | C++11 seq_cst 原子 store/load（STLR→LDAR 同址） | 同址紧贴 | 0 间隔 | 无(纯 C++ std::atomic) | report_fail(带 idx) |

### B. 走 forwarding 但中间隔屏障（路径形态介于 forwarding 与 L1D 阵列读）

| 测试名 | 源文件 | 一句话功能 | 屏障 | aarch64 分支 | 检错 |
|---|---|---|---|---|---|
| mfence | memory/mfence.cpp | store A→DMB SY→store B→load A/B 比对 | DMB SY(__sync_synchronize) | 无(纯 C) | report_fail(带 idx) |
| mfence_pure | memory/mfence_pure.cpp | load src→DMB SY→store dst→load dst 比对 | DMB SY | 无(纯 C) | report_fail(带 idx) |

### C. 不走 store→load forwarding（纯 ALU / 寄存器间 / 向量通路）

| 测试名 | 源文件 | 一句话功能 | 压测通路 | aarch64 分支 | 检错 |
|---|---|---|---|---|---|
| mite | misc/mite.cpp | add/eor/sub+分支条件乘 13/17（MITE 解码切换） | 纯 ALU+分支(内联 asm) | 事实 ARM64 专有(%w0 语法) | report_fail(checksum) |
| mrn_flags | misc/mrn_flags.cpp | mvn/cmp/csel 标志位+条件选择 | 纯 ALU 标志位(异址 load→ALU→store) | 有(内联 asm) | memcmp+report_fail |
| modified_sort | memory/modified_sort.cpp | 冒泡排序变体压 memory renaming | RMW 同址但非紧贴(纯 C++) | 无(纯 C++) | report_fail(带 cpu) |
| move_elimination_jit | jit/move_elimination_jit.cpp | JIT 长链寄存器间 MOV(压 renamer) | 寄存器间 MOV(不访存) | 有(JIT emit_word) | report_fail |
| move_elimination_8_jit | jit/move_elimination_8_jit.cpp | 8 位寄存器间 MOV 长链（ARM64 降级用 32 位） | 寄存器间 MOV(不访存) | 有(JIT emit_word) | report_fail(验低字节) |
| move_elimination_vec_evex_jit | jit/move_elimination_vec_evex_jit.cpp | NEON 向量寄存器间 MOV 长链 | 向量寄存器间 MOV(含 1 对 LDR/STR 不紧贴) | 有(JIT emit_word) | memcmp_or_fail |
| movbe | misc/movbe.cpp | 字节交换可逆性(load→rev→str→rev→cmp) | ALU 字节交换(不压 forwarding) | 无(纯 C,__builtin_bswap32→rev) | report_fail(带 index) |
| movdq2q | misc/movdq2q.cpp | NEON V0 低 64 位→GPR X0 | vector→GPR element move(不访存) | ARM-only 文件(无 x86 分支) | report_fail(带 index) |
| movq2dq | misc/movq2dq.cpp | GPR→SIMD 低 64 位+清零高 64 位 | GPR→vector 标量 move(fmov) | 有(内联 asm) | report_fail(两处) |
| movmskpspd | misc/movmskpspd.cpp | 提取打包 float/double 符号位为 mask | 向量 load+ALU 移位+element move | 有(内联 asm) | report_fail(两处) |

### D. ARM64 上不可用（纯 x86 概念，走 EXIT_SKIP 空跑）

| 测试名 | 源文件 | 一句话功能 | 为何 ARM64 不可用 |
|---|---|---|---|
| zero_control_vec_sse_jit | jit/zero_control_vec_sse_jit.cpp | SSE 指令不污染 YMM/ZMM 高位 | 只有 x86 JIT 字节，无 aarch64 分支，init 返回 EXIT_SKIP |
| zero_control_vec_evex_jit | jit/zero_control_vec_evex_jit.cpp | EVEX 指令清零 YMM/ZMM 高位 | 同上（x86 EVEX 零合并语义） |
| zero_control_vec_vex_jit | jit/zero_control_vec_vex_jit.cpp | VEX 指令清零 YMM 高位 | 同上（x86 VEX 零合并语义） |

---

## 二、逐个详述

### 1. atomic_seq_cst（A 组：forwarding）
- **源文件**：`tests/cpu/atomic/atomic_seq_cst.cpp`（88 行）
- **功能**：验证 C++11 `std::atomic<uint64_t>` 的 `memory_order_seq_cst` store/load 在 ARMv8 的正确性。
- **负载**：`TEST_LOOP(1<<15)`，每轮随机 idx，对共享 `shared[idx]` 做 seq_cst store(golden) 后立即 seq_cst load 比对。buffer `shared[4096]`+`golden[4096]` 各 32KB，**全核共享**（多核同址同值写）。
- **ARMv8 指令**：纯 C++ 无内联汇编。`std::atomic::store(seq_cst)`→**STLR**（store-release）；`load(seq_cst)`→**LDAR**（load-acquire）。代码注释明示。
- **aarch64 分支**：无 `#if`，靠 C++ 标准库跨平台。
- **检错**：`report_fail_msg`（带 idx/expected/got，无 xor dump）。
- **forwarding 关系**：**强相关**。同址 STLR→LDAR 走 store buffer forwarding（与 movbe/mrn_rmw 同路径族）。

### 2. mfence（B 组：forwarding+屏障）
- **源文件**：`tests/cpu/memory/mfence.cpp`（94 行）
- **功能**：测全内存屏障在双 store 间保证可见性/正确性。
- **负载**：`TEST_LOOP(1<<14)`，每轮 `store_a[idx]=golden_a`→`__sync_synchronize()`→`store_b[idx]=golden_b`→load A 比对→load B 比对。buffer 各 32KB，共享。
- **ARMv8 指令**：纯 C 无内联汇编。`__sync_synchronize()`→**DMB SY**；volatile uint64 store/load→**STR/LDR**（非 STLR/LDAR）。
- **aarch64 分支**：无 `#if`。
- **检错**：`report_fail_msg`（带 idx，无 xor dump）。
- **forwarding 关系**：verify load A 紧跟自身 store，走 forwarding；但中间插 DMB SY 会 drain store buffer，可能改走 L1D 阵列读——路径形态介于两者间（参考 [intervention-decoupling-impossible-use-pmu]：DMB 同时改路径与时序）。

### 3. mfence_pure（B 组：forwarding+屏障）
- **源文件**：`tests/cpu/memory/mfence_pure.cpp`（93 行）
- **功能**：纯屏障隔离 load 与 store，测 load→barrier→store 正确性。
- **负载**：`TEST_LOOP(1<<14)`，每轮 `val=load(data_src[idx])`→`__sync_synchronize()`→`data_dst[idx]=golden_dst`→load dst 比对→比对 val。buffer 各 32KB，共享。
- **ARMv8 指令**：纯 C。`__sync_synchronize()`→**DMB SY**；volatile load/store→**LDR/STR**。
- **aarch64 分支**：无 `#if`。
- **检错**：`report_fail_msg`（带 idx，无 xor dump）。
- **forwarding 关系**：dst 的 verify load 紧跟自身 store→forwarding（但隔 DMB）；src load 走 L1D 阵列读。

### 4. mite（C 组：纯 ALU+分支）
- **源文件**：`tests/cpu/misc/mite.cpp`（162 行）
- **功能**：MITE switch 负载，压测指令解码器切换+分支预测+ALU。
- **负载**：`TEST_LOOP(1<<10)`，内层遍历 `input[512]`，对每个值执行 add/eor/sub + 条件乘 13/17 + 条件 +1，累加 checksum 比对。input 2KB 只读共享。
- **ARMv8 指令**：**显式内联汇编，ARM64 专有**。`register uint32_t w0 asm("w0")`/`w1` 强制绑 W0/W1；三段 asm：`add %w0,%w0,%w1`（ADD）、`eor %w0,%w0,%w1`（EOR）、`sub %w0,%w0,%w1`（SUB）。`%w0` 是 GCC ARM64 的 32 位寄存器操作数语法，三操作数形式是 AArch64 特有（x86 无法汇编）。C 分支→TST/B.cond/MUL。input 读→`ldr Wn,[Xbase,Xidx,LSL #2]`。
- **aarch64 分支**：无 `#if defined(__aarch64__)` 守卫，但内联 asm 语法事实上锁死 ARM64（x86 不可构建）。是 ARM64 本地新增测试。
- **检错**：`report_fail_msg`（checksum expected/got，无 xor dump）。
- **forwarding 关系**：**不相关**。热循环纯 ALU+分支，每轮仅 1 次 LDR 读 input，无 store→load。

### 5. modified_sort（C 组：RMW 非紧贴）
- **源文件**：`tests/cpu/memory/modified_sort.cpp`（85 行）
- **功能**：冒泡排序变体压测 memory renaming（load/store 单元重命名）。
- **负载**：`TEST_LOOP(1<<5)`，每轮随机初始化 `data_src[256]`→memcpy 到 dst→`std::sort` 作 golden→手写冒泡排序 src→memcmp。buffer 各 2KB，**per-thread**（run 内分配隔离）。
- **ARMv8 指令**：纯 C++ 无内联汇编。memcpy/memcmp→**LDP/STP**；冒泡 `temp=src[j];src[j]=src[j+1];src[j+1]=temp`→**LDR+STR** 序列。
- **aarch64 分支**：无 `#if`。
- **检错**：`report_fail_msg`（带 cpu，无 xor dump）。
- **forwarding 关系**：**弱相关**。冒泡是同址 RMW 命中 L1D，但 store→load 非紧贴（取决于循环展开）。测 memory renaming 非直接 forwarding。

### 6. movbe（C 组：ALU 字节交换）
- **源文件**：`tests/cpu/misc/movbe.cpp`（79 行）
- **功能**：字节交换可逆性——swap 一次再 swap 回来应等于原值。
- **负载**：`TEST_LOOP(1<<13)`，内层遍历 `input[16384]`，`val=bswap(input[i])`→`swapped[i]=val`→`val=bswap(val)`→cmp val vs input[i]。buffer 各 64KB，**共享**（swapped 被多核并发写，有竞态但 SDC 检测可接受）。
- **ARMv8 指令**：纯 C 无内联汇编。`__builtin_bswap32`→**rev wreg**。热循环：`ldr`（读 input）→`rev`→`str`（写 swapped）→`rev`→`cmp`。**注意：cmp 用的是已 load 到寄存器的 val，不重读 input[i]，所以无 reload**。
- **aarch64 分支**：无 `#if`，靠 `__builtin_bswap32` 可移植。
- **检错**：`report_fail_msg`（带 index，无 xor dump）。
- **forwarding 关系**：**不走该路径**。热循环无同址 store→load（写 swapped、读 input 不同址）。此原始版与触发 179 SDC 的 `movbe_l1d`/`movbe_dump`（那种做 store→reload→cmp 的变体）**不同**——原始版纯测 ALU 字节交换，不压 forwarding。

### 7. movdq2q（C 组：vector→GPR move）
- **源文件**：`tests/cpu/misc/movdq2q.cpp`（91 行）
- **功能**：ARM 版——从 NEON V0 寄存器提取低 64 位到 GPR X0，压测 vector→GPR 数据通路。
- **负载**：`TEST_LOOP(1<<10)`，内层遍历 `low_parts[1024]`/`high_parts[1024]` 各 8KB，用 `vcombine_u64(vld1...)` 构造 128 位 vector，`register ... asm("v0")`/`asm("x0")` 强制绑寄存器。只读共享。
- **ARMv8 指令**：有内联汇编。`mov %0, %1.d[0]`（即 `mov Xd, Vm.d[0]`，vector→GPR element move）。输入 `"w"(v0)`（SIMD 寄存器），输出 `"=r"(x0)`（GPR）。热循环：`ld1`→`fmov/vmov` 到 V0→`mov Xd,Vm.d[0]`→寄存器比较。
- **aarch64 分支**：**ARM-only 文件**（无条件 `#include <arm_neon.h>`，无 x86 分支，x86 不可编译）。专为 ARM64 写。
- **检错**：`report_fail_msg`（带 index，无 xor dump）。
- **forwarding 关系**：**不走**。热循环无 store，纯 load→vector→GPR move。

### 8. move_elimination_jit（C 组：寄存器间 MOV）
- **源文件**：`tests/cpu/jit/move_elimination_jit.cpp`（288 行）
- **功能**：JIT 生成长链寄存器间 MOV（压 move elimination/renamer）。move elimination 是 x86 概念（重命名阶段零周期消除 MOV），ARM64 无此优化但 `ORR Xd,XZR,Xsr`=MOV 等价压测 renamer。
- **负载**：`TEST_LOOP(1<<16)`，每轮调 func64+func32。JIT 生成 16 寄存器环形链×16 周期=256 条 MOV。mmap 4096×2 字节。
- **ARMv8 指令**：**有 aarch64 分支**（`emit_word` 生成）。`0xAA0003E0|(src<<16)|dst`=`ORR Xd,XZR,Xsr`=MOV(64 位)；`0x2A0003E0|...`=`ORR Wd,WZR,Wsr`=MOV(32 位)；`0xD65F03C0`=RET。
- **检错**：`report_fail_msg`（result!=val，无 xor dump）。
- **forwarding 关系**：**无**。纯寄存器间 MOV 不访存。

### 9. move_elimination_8_jit（C 组：寄存器间 MOV，降级）
- **源文件**：`tests/cpu/jit/move_elimination_8_jit.cpp`（213 行）
- **功能**：JIT 生成 8 位寄存器间 MOV 长链。**ARM64 无 8 位寄存器**，用 32 位 MOV 替代只验低字节。
- **负载**：`TEST_LOOP(1<<16)`，每轮调 func8。256 条 MOV。
- **ARMv8 指令**：有 aarch64 分支。`0x2A0003E0|...`=`MOV Wd,Wsr`(32 位)；RET。
- **检错**：`(result&0xFF)!=(val&0xFF)`→`report_fail_msg`。
- **forwarding 关系**：**无**。纯寄存器间 MOV。

### 10. move_elimination_vec_evex_jit（C 组：向量寄存器间 MOV）
- **源文件**：`tests/cpu/jit/move_elimination_vec_evex_jit.cpp`（349 行）
- **功能**：JIT 生成向量寄存器间 MOV 长链（x86 VMOVDQA，ARM 用 NEON `ORR Vd,Vn,Vn`=MOV）。EVEX/ZMM(512 位)是 x86 特有。
- **负载**：`TEST_LOOP(1<<13)`，每轮调 neon64+neon128，input 64 字节。128 条 ORR + 1 对 LDR/STR。
- **ARMv8 指令**：有 aarch64 分支。`0x4EA01C00|...`=`ORR Vd.16B,Vn.16B,Vn.16B`=MOV(128 位 NEON)；`0x0EA01C00|...`=MOV(64 位 NEON)；`0x3DC00000|...`=`LDR Qt`；`0x3D800000|...`=`STR Qt`；`LDR/STR Xt`；RET。
- **检错**：`memcmp_or_fail`。
- **forwarding 关系**：**弱相关**。含 1 对 LDR/STR 但不紧贴（中间隔 128 条 ORR），非 forwarding 压测。

### 11. zero_control_vec_sse_jit（D 组：ARM64 不可用）
- **源文件**：`tests/cpu/jit/zero_control_vec_sse_jit.cpp`（147 行）
- **功能**：测 SSE 指令不污染 YMM/ZMM 高位（x86 向后兼容）。**纯 x86 概念**，ARM64 无此架构行为。
- **ARMv8 指令**：**无 aarch64 分支**。只有 `#if defined(__x86_64__)` 块用 `emit_byte` 生成 x86 字节。
- **aarch64 分支**：**无**。init 非 x86_64 时 `log_skip` 返回 `EXIT_SKIP`，run 空跑 `return EXIT_SUCCESS`。**ARM64 上不可用/空跑**。
- **forwarding 关系**：无。

### 12. zero_control_vec_evex_jit（D 组：ARM64 不可用）
- **源文件**：`tests/cpu/jit/zero_control_vec_evex_jit.cpp`（166 行）
- **功能**：测 EVEX 指令清零 YMM/ZMM 高位（x86 EVEX 零合并语义）。**纯 x86 概念**。
- **aarch64 分支**：**无**。init 返回 EXIT_SKIP，run 空跑。**ARM64 上不可用**。
- **forwarding 关系**：无。

### 13. zero_control_vec_vex_jit（D 组：ARM64 不可用）
- **源文件**：`tests/cpu/jit/zero_control_vec_vex_jit.cpp`（143 行）
- **功能**：测 VEX 指令清零 YMM 高位（x86 VEX 零合并语义）。**纯 x86 概念**。
- **aarch64 分支**：**无**。init 返回 EXIT_SKIP，run 空跑。**ARM64 上不可用**。
- **forwarding 关系**：无。

### 14. movmskpspd（C 组：向量符号位提取）
- **源文件**：`tests/cpu/misc/movmskpspd.cpp`（189 行）
- **功能**：提取打包 float(4 路)/double(2 路)符号位为 mask（x86 MOVMSKPS/PD，ARM 用 USHR 右移 31/63 位隔离符号位）。
- **负载**：`TEST_LOOP(1<<13)`，内层遍历 256 元素。buffer `fvalues`(4KB float)+`dvalues`(4KB double)+expected，只读共享。golden mask 在 init 预计算。
- **ARMv8 指令**：有 aarch64 分支。ps：`ldr q0,[%4]`→`ushr v0.4s,#31`→`umov %w,Vs[idx]`(×4)；pd：`ushr v0.2d,#63`→`umov`。
- **检错**：两处 `report_fail_msg`（ps/pd mask≠golden，无 xor dump）。
- **forwarding 关系**：**不走**。热循环无 store，纯 load→向量 ALU 移位→element move。

### 15. movq2dq（C 组：GPR→vector move）
- **源文件**：`tests/cpu/misc/movq2dq.cpp`（140 行）
- **功能**：64 位 GPR→SIMD 低 64 位+清零高 64 位（x86 MOVQ2DQ，ARM `FMOV Dd,Rn`）。
- **负载**：`TEST_LOOP(1<<13)`，内层遍历 256 元素。`values` 2KB（malloc 未对齐），只读共享。
- **ARMv8 指令**：有 aarch64 分支。`fmov %d0, %1`（即 `fmov Dd,Rn`：GPR→vector 标量 move，高 64 清零）。输出 `"=w"`(SIMD)，输入 `"r"`(GPR)。之后 `vgetq_lane_u64` 提取 low/high。
- **检错**：两处 `report_fail_msg`（low≠原值；high≠0）。
- **forwarding 关系**：**不走**。热循环无 store，纯 load→GPR→fmov→lane extract。

### 16. mem_disambiguation（A 组：forwarding，核心相关）
- **源文件**：`tests/cpu/memory/mem_disambiguation.cpp`（212 行）
- **功能**：专为压测 store-to-load forwarding 和内存消歧而设计。三模式：全宽同址 forwarding、部分重叠 forwarding、重复 store 训练预测器。
- **负载**：`TEST_LOOP(1<<13)`，每轮 3 个内层循环各遍历 512 模式。**per-thread buffer** 4KB（run 内分配，注释明示"avoid data races"）。offsets/values 各 512 项共享只读。
- **ARMv8 指令**：有 aarch64 分支。`store_qword`:`str %1,[%0]`；`load_qword`:`ldr %0,[%1]`；`load_dword`:`ldr %w0,[%1]`。模式1 str→ldr 同址（全宽 forwarding）；模式2 str(8B)→ldr w(@off+2，部分重叠，期望 `value>>16`）；模式3 str×3 同址→ldr（训练预测器）。
- **检错**：三处 `report_fail_msg`（对应三模式，带 offset/expected/got，无 xor dump）。
- **forwarding 关系**：**是，核心目标**。是 22 个测试中最系统压 store→load forwarding 的。注意：str→ldr 之间无 ALU 插入，是纯 forwarding 压测（与 movbe_l1d/movbe_dump 的 str→reload→cmp 同源，但无 ALU）。

### 17. mrn_nuke（A 组：forwarding）
- **源文件**：`tests/cpu/misc/mrn_nuke.cpp`（101 行）
- **功能**：输入数组经 temp 拷贝到 dst，紧贴 str→temp/load→temp 压测 memory renaming/store-to-load forwarding，意图诱发 load-store queue 的 nuke（流水线重置）。
- **负载**：`TEST_LOOP(1<<13)`，每轮 1024 元素。`store(temp[i],src[i])`→`val=load(temp[i])`→`store(dst[i],val)`。纯拷贝无 ALU。temp/dst 各 8KB，per-thread。
- **ARMv8 指令**：有 aarch64 分支。`str %1,[%0]`/`ldr %0,[%1]`。
- **检错**：`memcmp(dst,src)`+`report_fail_msg`（无 xor dump）。
- **forwarding 关系**：**同址紧贴 forwarding**。与 mrn_rmw 同路径，区别是无 ALU（更纯粹压 forwarding 单元）。

### 18. mrn_pairs（A 组：forwarding 拉开时序）
- **源文件**：`tests/cpu/misc/mrn_pairs.cpp`（108 行）
- **功能**：8 路展开的 store→load 转发——先连续 8 个 store 到 temp[i..i+7]，再连续 8 个 load 回 dst，通过拉开 store 与对应 load 的时序间隔增加 renaming 单元并发压力。
- **负载**：`TEST_LOOP(1<<13)`，每轮 1024 元素步长 8。每块：8 条 `store(temp[i+k],src[i+k])` 后 8 条 `store(dst[i+k],load(temp[i+k]))`。temp/dst 各 8KB，per-thread。
- **ARMv8 指令**：有 aarch64 分支。`str %1,[%0]`/`ldr %0,[%1]`。
- **检错**：`memcmp`+`report_fail_msg`（无 xor dump）。
- **forwarding 关系**：**同址但时序拉开**。对 temp[i+0]，store 在第 1 条、load 在第 9 条（中间隔 7 条 store）。若 store 仍在 store buffer 则走 forwarding（但时序不紧贴）；若 SB 容量不足则 load 命中 L1D 阵列读。是这组唯一"用真 store 拉开 str→ldr 间隔"的变体（与 nop 拉开思路同类但手段不同）。

### 19. mrn_reloaded（A 组：forwarding 三宽度）
- **源文件**：`tests/cpu/misc/mrn_reloaded.cpp`（142 行）
- **功能**：用 1/4/8 字节三粒度做 store→load 对，检测不同数据宽度下 forwarding 正确性。
- **负载**：`TEST_LOOP(1<<8)`（轮数少，因有 3 子循环）。每轮三循环各 1024 元素：byte/dword/qword 各 store→load 同址→逐元素比较。temp8 1KB/temp32 4KB/temp64 8KB，per-thread。
- **ARMv8 指令**：有 aarch64 分支。`strb %w1,[%0]`/`ldrb %w0,[%1]`(1B)；`str %w1,[%0]`/`ldr %w0,[%1]`(4B,W)；`str %1,[%0]`/`ldr %0,[%1]`(8B,X)。
- **检错**：**逐元素立即比较**+`report_fail_msg`（带索引，三粒度各一条）。是 5 个 mrn 测试中唯一带元素索引的。
- **forwarding 关系**：**同址紧贴 forwarding，三宽度**。sub-word store→load 是 forwarding 边界情况。

### 20. mrn_rmw（A 组：forwarding+ALU）
- **源文件**：`tests/cpu/misc/mrn_rmw.cpp`（123 行）
- **功能**：两源数组做 add/sub/xor/and（按 i%4 轮换）ALU 运算，经 temp 缓冲用 str→ldr 转发搬到 dst，检测 ALU 读改写+forwarding 路径 SDC。
- **负载**：`TEST_LOOP(1<<13)`，每轮 1024 元素。`a=srcA[i]`,`b=srcB[i]`,ALU 算 res,`store(temp[i],res)`→`store(dst[i],load(temp[i]))`。temp/dst 各 8KB，per-thread；srcA/srcB/expected 共享只读。
- **ARMv8 指令**：有 aarch64 分支。`str %1,[%0]`/`ldr %0,[%1]`；C 层 ALU add/sub/eor/and。
- **检错**：`memcmp(dst,expected)`+`report_fail_msg`（无 xor dump）。
- **forwarding 关系**：**同址紧贴 forwarding**。与 movbe/mrn_rmw_fwd 同路径（store→reload→compare）。是 179 SDC 稳态触发器之一。

### 21. part_store_fwd_jit（A 组：forwarding，JIT 背靠背）
- **源文件**：`tests/cpu/jit/part_store_fwd_jit.cpp`（209 行）
- **功能**：JIT 生成"窄位宽 store+紧接不同位宽 load 同址"序列，压测 partial store-to-load forwarding（部分数据转发与合并）。
- **负载**：`TEST_LOOP(1<<16)`，每轮随机选 4 pattern 之一（8→16/16→32/32→64/64→32），随机 offset 0-7。buffer 栈上 `alignas(64) uint8_t buf[32]`。JIT 生成 4 个函数各 3 指令(store+load+ret)。
- **ARMv8 指令**：有 aarch64 分支（`emit_word` 生成）。func0:`0x39000001`=`strb w1,[x0]`+`0x79400000`=`ldrh w0,[x0]`+ret；func1:`strh`+`ldr w`+ret；func2:`str w`+`ldr x`+ret；func3:`str x`+`ldr w`+ret。
- **检错**：按 pattern 算 expected（保留 old 高位+新 val 低位），`res!=expected`→`report_fail_msg`（带 pattern）。
- **forwarding 关系**：**强相关，核心**。每个 JIT 函数就是"窄 store+紧接宽 load 同址"，store 未落 L1D 前由 store buffer 转发，转发时做部分合并——正是 store→load forwarding 路径。时序窗口最窄（函数内背靠背）。与 179 SDC 的 store→reload 路径直接对应。

### 22. partial_store_forwarding（A 组：forwarding，部分重叠）
- **源文件**：`tests/cpu/misc/partial_store_forwarding.cpp`（83 行）
- **功能**：load 访问 store buffer 条目的部分数据——随机位宽(1/2/4/8B)store 与 load 到同一区，维护 shadow buffer，验证每个 load（尤其是访问最近写入 store buffer 条目部分的 load）返回正确合并的数据。
- **负载**：`TEST_LOOP(1<<16)`，每轮随机 s_off/s_sz/s_val 写 real+shadow，编译屏障 `asm volatile("":::"memory")`，随机 l_off/l_sz 读 real+shadow 比较。buffer 栈上 `real_buf[256]`+`shadow_buf[256]`，per-thread。
- **ARMv8 指令**：**无显式内存内联汇编**——纯 C volatile 指针解引用。`read_mem`/`write_mem` 按 size switch 到 `volatile uint8_t*/uint16_t*/uint32_t*/uint64_t*`。AArch64 上 GCC 生成 `ldrb/ldrh/ldr/ldr xN` 和 `strb/strh/str/str xN`。唯一 asm 是编译屏障。
- **aarch64 分支**：无 `#if`，纯可移植 C。
- **检错**：`report_fail_msg`（带 offset/size/expected/got，无 xor dump）。
- **forwarding 关系**：**是，核心目标**。随机 store 后随机 load 到重叠区，store buffer 须把部分数据与既有内存合并 forward 给 load。压测 partial store forwarding/store buffer 合并逻辑。buffer 256B 完全在 L1D 内。

### 23. mrn_flags（C 组：纯 ALU 标志位）
- **源文件**：`tests/cpu/misc/mrn_flags.cpp`（117 行）
- **功能**：数组做按位取反(MVN)，比较结果是否为 0，若为 0 则用 CSEL 条件选择写魔数 `0xDEADBEEFDEADBEEF`，检测 ALU 标志位生成+条件选择逻辑。
- **负载**：`TEST_LOOP(1<<13)`，每轮 1024 元素。`dst[i]=flip_and_branch(src[i])`。dst 8KB per-thread；src/expected 共享只读。
- **ARMv8 指令**：有 aarch64 分支（内联汇编）。`mvn %0,%0`（按位取反，对应 x86 `notq`）；`cmp %0,#0`（设标志，对应 `testq`）；`csel %0,%1,%0,eq`（条件选择，对应 `cmovz`）。
- **检错**：`memcmp(dst,expected)`+`report_fail_msg`（无 xor dump）。
- **forwarding 关系**：**弱/基本无关**。5 个 mrn 测试中唯一**不走同址 str→ldr forwarding** 的。数据流 `load(src[i])`→ALU(mvn/cmp/csel)→`store(dst[i])`，src 与 dst 异址，无 store 后立即 reload 同址模式。压的是 ALU 标志位+条件分支路径。若在 179 触发 SDC，指向 ALU/标志位路径而非 forwarding 路径。

---

## 三、关键发现

### 1. store→load forwarding 路径覆盖（179 SDC 触发路径）
179 SDC 触发路径是 store→reload（[load-port-downstream-sdc-confirmed]）。22 个测试中：
- **A 组 8 个走该路径**：mrn_rmw/mrn_nuke/mrn_reloaded/mem_disambiguation/partial_store_forwarding/part_store_fwd_jit/atomic_seq_cst（同址紧贴 forwarding）+ mrn_pairs（同址拉开时序）
- **B 组 2 个走但隔屏障**：mfence/mfence_pure（DMB 可能 drain store buffer 改走 L1D 阵列读，路径形态介于两者间）
- **C 组 11 个不走**：mite/mrn_flags/modified_sort/move_elimination×3/movbe/movdq2q/movq2dq/movmskpspd（纯 ALU/寄存器间/向量通路）
- **D 组 3 个 ARM64 不可用**：zero_control_vec_sse/evex/vex_jit（x86 概念，EXIT_SKIP 空跑）

### 2. movbe 原始版 ≠ 触发 179 SDC 的 movbe_dump/movbe_l1d
`movbe.cpp` 原始版热循环**无同址 store→reload→cmp**（写 swapped、读 input 不同址，cmp 用寄存器中的 val 不重读 input）。触发 179 SDC 的是后来改造的 `movbe_dump`/`movbe_l1d`（在热循环做 store→reload→cmp）。**勿混淆**——原始 movbe 在 179 上跑可能 0-fail，因为不走触发路径。

### 3. 检错方式全部是 `report_fail_msg`，无一用 `log_miscompare`/dump xor
22 个测试**全部**用 `report_fail_msg`，无一用 `log_miscompare`/`log_error`/二进制 write dump xor 字节。这意味着：
- 能报 fail 但**不能定位翻转位**（不像 movbe_dump/mrn_rmw_dump 那样冷分支 dump input/golden/actual/xor）
- 按 [sdc-fail-count-unique-blocks] 的统计口径，需确认 `report_fail_msg` 在当前框架是否走 miscompare 通道，否则 fail 计数口径要调整
- 若要复用其路径压 179 抓样本，需仿照 [eigen-dump-binary-log-added] 给冷分支加二进制日志（**切忌改热路径**，参考 [movbe-dump-compiler-dce-root-cause]/[dump-variant-noremove-report-fail-verified] 的教训：连冷分支都不能碰，179 对布局极度敏感）

### 4. ARM64 适用性
- **原生 ARM64（有 aarch64 分支或 ARM-only）**：mrn_rmw/mrn_nuke/mrn_pairs/mrn_reloaded/mrn_flags/mem_disambiguation/movq2dq/movmskpspd/movdq2q(ARM-only)/move_elimination×3/part_store_fwd_jit——共 14 个
- **纯 C 可移植（无 `#if`，编译器生成 ARM64 指令）**：atomic_seq_cst/mfence/mfence_pure/mite(事实 ARM64 专有)/modified_sort/movbe/partial_store_forwarding——共 7 个
- **ARM64 不可用（EXIT_SKIP 空跑）**：zero_control_vec_sse/evex/vex_jit——共 3 个

### 5. JIT 测试的 ARM64 实现
- **有 ARM64 JIT（emit_word 生成机器码字面量）**：move_elimination_jit/8_jit/vec_evex_jit/part_store_fwd_jit——4 个
- **只有 x86 JIT（emit_byte）**：zero_control_vec_sse/evex/vex_jit——3 个
- part_store_fwd_jit 的 `flush_icache` 用 `__builtin___clear_cache`——**此处是对的**（JIT 生成的是指令，要清 icache 让 CPU 看到新指令，**不是逐数据行**；与 cache_stress_aggressor 误用 clear_cache 逐数据行不同）

### 6. buffer 共享性 vs per-thread
- **per-thread（run 内分配隔离）**：mem_disambiguation/partial_store_forwarding/modified_sort/mrn_rmw/mrn_nuke/mrn_pairs/mrn_reloaded/mrn_flags——8 个（避免竞态）
- **共享（init 分配，全核同 test->data）**：atomic_seq_cst/mfence/mfence_pure/mite/movbe/movdq2q/movq2dq/movmskpspd/move_elimination×3/part_store_fwd_jit——14 个
- 按 [movbe-d-positive-control-20260824] 结论"触发=系统级全核并发压力"，共享型更贴合 179 触发形态；per-thread 型即便在 179 跑也可能因缺乏跨核共享压力而不触发（需实测确认）

---

## 四、与 179 SDC 研究的对照建议（含 2026-08-31~09-01 实测结果）

**实测已跑完 22 个测试各 30min 全核 192 含 179 + auto seed**（driver `run_22tests_30min.sh`，结果 `movbe_log/tests_22_30min/`，监控绑核 0 不碰 179，完整 stdout `-o` 落盘）。结果见 `summary.txt`：

### 触发 SDC 的（仅 2 个，全在 thread 179）
| 测试 | 唯一 fail 块 | 含 retry | 率 | 路径 |
|---|---|---|---|---|
| movbe 原始版 | 57 | 69 | ~1.9/min | ldr input(L1D阵列读)+rev+str swapped+rev+cmp |
| mrn_rmw 原始版 | 6 | 11 | ~0.2/min | str→ldr forwarding |

两者所有 fail 的 cpu-mask 都是同一模式（core144-191 段 `...X...`，X 在 179），`- thread: 179` 确认。

### 0-fail 的 20 个（含 3 个 ARM64 不可用秒退）
part_store_fwd_jit / atomic_seq_cst / mfence / mfence_pure / mite / modified_sort / movdq2q / move_elimination_jit / move_elimination_8_jit / move_elimination_vec_evex_jit / zero_control_vec_sse_jit(不可用) / zero_control_vec_evex_jit(不可用) / zero_control_vec_vex_jit(不可用) / movmskpspd / movq2dq / mem_disambiguation / mrn_nuke / mrn_pairs / mrn_reloaded / partial_store_forwarding / mrn_flags

### 关键发现（修正/印证）
1. **仅 2 个触发，全在 179** → 坐实"179 绑定的硅缺陷"，不是普遍 SDC。
2. **movbe 原始版也触发 69 次（~2.3fail/min，高于 movbe_dump 的 1.5fail/min）→ 修正此前判断**：[load-port-downstream-sdc-confirmed] 等记忆说"movbe 原始版与 movbe_dump/movbe_l1d 不同、不走 store→reload"。实测推翻——原始版虽 cmp 用寄存器 val 不重读 input（无同址 store→reload），但仍触发，且率更高。说明触发不只依赖"store→reload→cmp"那一种热循环形态。原始版热循环仍有 `ldr input→rev→str swapped→rev→cmp val`，其中 **input 的 ldr 命中 L1D 阵列读**（input init 后只读驻留 L1D）→ 可能走的是 **L1D 阵列读路径**而非 forwarding，与 [l1d-read-path-sdc-confirmed]（movbe_l1d 走 L1D 阵列读触发）一致。
3. **mrn_rmw 原始版触发 6 次**（比 mrn_rmw_dump 的 2fail/60min 高）→ 与 dump 变体同路径（forwarding），原始版无 dump 冷分支扰动，率更高（印证 [dump-variant-noremove-report-fail-verified]：冷分支会扰动布局降率）。
4. **mem_disambiguation 0-fail**（模式1=同址 forwarding 基线，模式3=重复 store 训练）→ 虽走 forwarding 但**布局未对齐 179 触发窗口**。印证 [movbe-l1d-variants-schedule-sensitivity]：功能等价改写/不同布局会破坏触发。
5. **part_store_fwd_jit 0-fail**（JIT 背靠背 str→ldr 时序最窄）→ 同上，布局未对齐。
6. **mrn_flags 0-fail**（纯 ALU mvn/cmp/csel，不走 forwarding）→ 与"缺陷在 store→reload 路径"结论**一致**（纯 ALU 不触发，反向支撑 forwarding/L1D 路径结论）。这正是第2点预测的结果——0-fail 与"缺陷在 store→reload 路径"一致，已实测坐实。
7. **mrn_nuke / mrn_pairs / mrn_reloaded 0-fail**（都走 forwarding 但布局不同）→ 与 mrn_rmw 同路径但布局不同未触发，再次印证 179 对布局极度敏感。
8. **22 个全用 report_fail_msg 不 dump xor** → 不能定位翻转位。要抓样本需加 dump，但切忌改热路径（[dump-variant-noremove-report-fail-verified]）。

### fail 口径教训
movbe "69 fails"是 `grep -c 'Round-trip failed'`（事件数，含框架 retry:true 重试段）；唯一 fail 块（排除 retry:true）= 57。mrn_rmw 同理 11→6。按 [sdc-fail-count-unique-blocks] 应数唯一 result:fail 块。

### 对照建议（实测后更新）
1. **mem_disambiguation / part_store_fwd_jit / mrn_nuke / mrn_pairs / mrn_reloaded 都是 forwarding 路径但 0-fail** → 不是"走 forwarding 就触发"，**指令布局是触发窗口的关键**。要复现需字节复刻 movbe/mrn_rmw 的热循环布局（参考 [movbe-l1d-variants-schedule-sensitivity] 的教训：变体须字节复刻原始寻址模式）。
2. **movbe 原始版触发率高于 movbe_dump** → 若要抓样本，原始版比 dump 版更高效（但原始版不 dump xor，抓不到位）。权衡：用 dump 版抓样本定位位，用原始版测触发率。
3. **mrn_flags 的 0-fail 是有力反向证据** → 排除"纯 ALU 路径缺陷"，把病灶进一步收窄到 store→load/L1D 路径。
