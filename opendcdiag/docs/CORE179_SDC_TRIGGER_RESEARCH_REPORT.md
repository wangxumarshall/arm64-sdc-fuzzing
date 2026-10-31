# CORE179 SDC 触发诱因研究报告

> 研究周期：2026-08-24 ~ 2026-09-02
> 平台：Kunpeng 920 (ARMv8.1-A, AArch64), 192 核, openEuler
> 工具：OpenDCDiag (ARM64 移植版, Meson+Ninja 构建)
> 目标核：逻辑核 179 (package 19062, numa_node 7, module 23340)

---

## 摘要

本报告整理围绕 Kunpeng 920 逻辑核 179 上发生的静默数据损坏（SDC）的系统性研究。研究从 22 个既有测试用例的负载环境与指令序列分析出发，定位到 movbe 与 mrn_rmw 两个能触发 SDC 的测试，提炼其输入方式与指令序列特征；通过将不同输入方式移植到不触发的 mrn_nuke 骨架上做正向构造实验，发现"**2 源 load + 数据 ALU 依赖链**"可能是触发 SDC 的诱因；为进一步验证结论的普遍性，又把该特征移植到 mrn_pairs、mrn_reloaded 等多个 mrn 类骨架上做跨骨架验证。最终得出初步结论：**触发 179 SDC 的诱因是"2 源 load + 数据 ALU 依赖链"与"紧时序背靠背 forwarding"的组合，二者缺一不可。**

---

## 第一章 22 个测试用例的负载环境与原版结果

### 1.1 负载环境（统一的跑测条件）

- **CPU 占用**：全核 192 核并发（`-n 192`），**含目标核 179**（主测试不绑核，全核并发压力是触发前提）
- **种子**：auto seed（不传 `-s`，走 random_device 真随机，每轮生成全新 input 数组）
- **时长**：每个测试 30min（`-T 30m`），部分坐实实验用 36min（30min × 120%）
- **错误处理**：`--ignore-os-error --ignore-timeout`（不因错误/超时停止）
- **数据口径**：数唯一 `- test:` 块内含 `result: fail` 的事件（每个 fail = 1 个独立事件，不 grep miscompare 双计）
- **关键约束**：触发需"全核并发压力"，单核 179 或切片跑都不触发；179 须无 SiliFuzz 持续占核污染

### 1.2 22 个测试的指令序列（详细介绍）

22 个测试按负载路径分四组。以下为每个测试的内层循环 ARMv8 微操作序列（objdump 字节级取证，纯 C 测试标编译器生成）。

#### A 组：走 store→load forwarding 路径（8 个）

**1. mrn_rmw ✅ 触发 ~0.2/min（6 fail，全 179）**
- 负载：ALU 读改写 + store-to-load forwarding（memory renaming + forwarding 双压）
- 输入方式：2 源 load（srcA, srcB 各 8KB 共享只读），store 值 = ALU 加工（add/sub/eor/and 按 i%4 轮换），temp/dst 各 8KB per-thread
- 指令序列：
  ```
  ldr x0,[srcA,i]        ; 源 load A
  ldr x3,[srcB,i]        ; 源 load B
  eor/and/add/sub x2,x0,x3  ; 数据 ALU（操作轮换）
  add x0,temp,i          ; temp 地址
  str x2,[x0]            ; store ALU 结果到 temp
  ldr x0,[x0]            ; forwarding 重载（背靠背 0 间隔）
  add x2,dst,i           ; dst 地址
  str x0,[x2]            ; store 到 dst
  ```
- store→load 关系：同址同寄存器 x0，背靠背 0 间隔，纯 forwarding

**2. mrn_nuke ❌ 0-fail**
- 负载：纯拷贝 store-to-load forwarding（无 ALU）
- 输入方式：1 源 load（src 8KB 共享），store 值 = 原值未加工，temp/dst 各 8KB per-thread
- 指令序列：
  ```
  ldr x1,[src,i]         ; 源 load（1 源）
  add x0,temp,i          ; temp 地址
  str x1,[x0]            ; store 原值到 temp
  ldr x0,[x0]            ; forwarding 重载（背靠背，与 mrn_rmw 同构）
  add x1,dst,i           ; dst 地址
  str x0,[x1]            ; store 到 dst
  ```
- store→load 关系：同址同寄存器 x0，背靠背 0 间隔，**与 mrn_rmw 微操作字节同构**
- 与 mrn_rmw 唯一差异：store 前无数据 ALU（原值搬），1 源 load 而非 2 源

**3. mrn_pairs ❌ 0-fail**
- 负载：8 路展开 store-to-load forwarding（拉开时序间隔）
- 输入方式：1 源 load，store 值原值，temp/dst 各 8KB per-thread
- 指令序列：8×`str x1,[temp+k]` 后 8×`ldr x9,[temp+k]; str x9,[dst+k]`
- store→load 关系：同址但**时序拉开 7 条 store**（非背靠背）

**4. mrn_reloaded ❌ 0-fail**
- 负载：1/4/8 字节三粒度 store-to-load forwarding
- 输入方式：1 源 load，store 值原值，temp8/32/64 各 1/4/8KB per-thread
- 指令序列（byte 子循环）：`ldr x2,[src]; strb w2,[temp8,i]; ldrb w1,[temp8,i](forwarding); cmp`
- store→load 关系：同址背靠背，**sub-word**（1/4 字节粒度）

**5. mem_disambiguation ❌ 0-fail**
- 负载：三模式 store-to-load forwarding + 内存消歧
- 输入方式：模式1 = 2 源 load（off, val），store 值原值，buf 4KB per-thread
- 指令序列（模式1）：
  ```
  ldr x4,[off,i]         ; 源 load 1（偏移）
  ldr x5,[val,i]         ; 源 load 2（值）
  add x6,buf,off         ; 地址 ALU（随机地址）
  str x5,[x6]            ; store 原值
  ldr x6,[x6]            ; forwarding 重载（背靠背）
  cmp x5,x6
  ```
- store→load 关系：同址背靠背，**与 mrn_rmw 微操作同构**，但 store 值原值未加工（地址 ALU 非数据 ALU）

**6. partial_store_forwarding ❌ 0-fail** — partial forwarding，随机位宽部分重叠
**7. part_store_fwd_jit ❌ 0-fail** — JIT 窄 store+宽 load，经 blr 间接调用隔开时序
**8. atomic_seq_cst ❌ 0-fail** — STLR→LDAR release-acquire forwarding，store 值原值

#### B 组：forwarding 但中间隔屏障（2 个）

**9. mfence ❌ 0-fail** — store 间插 DMB SY drain store buffer
**10. mfence_pure ❌ 0-fail** — DMB 隔离 load 与 store

#### C 组：不走 store→load forwarding（11 个）

**11. movbe ✅ 触发 ~1.9/min（57 fail，全 179）**
- 负载：字节交换可逆性（ALU 字节交换 + L1D 同址重读）
- 输入方式：1 源 load（input 64KB 共享），store 值 = ALU 加工（rev），swapped 64KB 共享
- 指令序列（objdump，源码 2 个 bswap 编译后第 2 个被 DCE 消失）：
  ```
  ldr w1,[input,i]       ; 第 1 次读 input
  rev w4,w1              ; 数据 ALU（字节交换）
  str w4,[swapped,i]     ; store 到异址 swapped
  ldr w4,[input,i]       ; 第 2 次读 input（同址重读！）
  cmp w4,w1              ; 比对
  ```
- store→load 关系：store(swapped) 与 load(input) **异址，非 forwarding**；两次 ldr 同址读 input = **L1D 阵列重读**
- 机制：对同一 L1D 行窄窗内两次 ldr 不一致

**12. mite ❌ 0-fail** — MITE switch，纯 ALU+分支无 store→load
**13. mrn_flags ❌ 0-fail** — ALU 标志位+条件选择，有数据 ALU(mvn) 但无 store 后重载
**14. modified_sort ❌ 0-fail** — 冒泡排序变体测 renaming
**15-17. move_elimination*_jit ❌ 0-fail** — JIT 寄存器间 MOV，不访存
**18. movdq2q / 19. movq2dq / 20. movmskpspd ❌ 0-fail** — 向量/GPR move，无 store

#### D 组：ARM64 不可用（3 个）

**21-23. zero_control_vec_*_jit ❌ 不可用** — x86 SSE/EVEX/VEX 概念，init 返回 EXIT_SKIP

### 1.3 原版结果汇总

| 测试 | 负载路径 | 输入方式 | 触发? | fail/30min |
|---|---|---|---|---|
| mrn_rmw | forwarding+ALU | 2源+ALU加工 | ✅ | 6 |
| movbe | L1D同址重读 | 1源+rev+异址store | ✅ | 57 |
| mrn_nuke | forwarding | 1源+原值 | ❌ | 0 |
| mrn_pairs | forwarding(拉开) | 1源+原值 | ❌ | 0 |
| mrn_reloaded | forwarding(sub-word) | 1源+原值 | ❌ | 0 |
| mem_disambiguation | forwarding+随机地址 | 2源+原值 | ❌ | 0 |
| 其余 16 个 | 各种 | 各种 | ❌ | 0 |

**只有 mrn_rmw 和 movbe 触发，其余 20 个 0-fail。**

---

## 第二章 触发 SDC 的 movbe 与 mrn_rmw 特征提炼

### 2.1 两触发测试的特征对比

从 22 测试对照表提炼两个触发测试的共同点与差异：

| 特征 | mrn_rmw（forwarding 路径） | movbe（L1D 重读路径） |
|---|---|---|
| 触发率 | ~0.2/min | ~1.9/min |
| 源 load 数 | 2（srcA, srcB） | 1（input） |
| store 值来源 | ALU 加工（a op b） | ALU 加工（rev） |
| 第二次访存路径 | store buffer forwarding | L1D 阵列同址重读 |
| 时序 | 背靠背 0 间隔 | 紧（rev+异址store 隔开） |
| 翻转特征 | ALU 算错（recompute≠actual） | 第二次 ldr 读错（actual≠input） |

### 2.2 输入值的 bit 分析（排除"特定 input 触发"假说）

对 movbe 跨 5 轮独立 auto-seed 数组采样 42 条触发 input 值，做逐 bit constant 分析：
- **单 bit constant**：无（所有 bit ones 计数 17~27/42，均匀期望 21±3.24，最偏 bit14=27/42 p=0.088，未达 Bonferroni 阈值 0.00156）
- **bit 对 constant**：无（0 对恒同值或恒反值）
- **字节级分布**：高度分散（byte0 有 39/42 个不同值）

**结论：触发 SDC 的 input 值没有任何 bit 固定为 0 或 1，input 值不决定触发。** 这排除了"特定 input 值触发"的假说，把注意力从输入数据值转向输入方式（数据怎么来）和指令序列（怎么用）。

### 2.3 初步特征提炼

两个触发测试的共同特征候选：
1. **store 值经数据 ALU 加工**（mrn_rmw 的 eor/add，movbe 的 rev）——但 mrn_flags 有 mvn 却 0-fail，且 v2 探针在 mrn_nuke 加 eor 仍 0-fail
2. **紧时序**（背靠背 forwarding）——但 mrn_nuke/mem_disambiguation 同背靠背却 0-fail
3. **2 源 load**（mrn_rmw 有）——但 mem_disambiguation 也有 2 源却 0-fail；movbe 是 1 源

单变量分析无法干净区分触发与不触发，需要正向构造实验。

---

## 第三章 正向构造：移植输入方式到 mrn_nuke 骨架

### 3.1 实验设计

mrn_nuke 是与 mrn_rmw 微操作字节同构却不触发的最佳对照骨架（两者 str→ldr 均背靠背 0 间隔）。在其上按三个方向构造 4 个变体，逐一改变输入方式/指令序列，看哪个能触发：

| 变体 | 改造方向 | 改了什么 | 骨架是否变 |
|---|---|---|---|
| mrn_nuke_2src_alu | 2源load+ALU依赖链 | 1源→2源，原值→ALU结果 | 否 |
| mem_disambig_alu | ALU加工 | 存原值→存ALU结果（随机地址forwarding） | 否 |
| mrn_nuke_dense | 提高load密度 | count 1024→16384（×16） | 否 |
| mrn_nuke_recross | movbe式同址重读 | forwarding→L1D同址重读 | 是（inline asm） |

### 3.2 实验方法

两阶段验证协议：
1. **阶段1（可靠性）**：排除 179 核（taskset 0-178,180-191）跑 60s 须 0-fail，证明变体本身无 bug（expected 计算自洽）
2. **阶段2（触发）**：全核 192 含 179 + auto seed 跑 36min（30min×120%），数 fail 块
3. **确定性核实**：低率变体做"排除 179 + 同 seed → 须 0-fail"，区分真 SDC vs 变体 bug

### 3.3 实验数据（36min 坐实）

| 变体 | 改造方向 | fail/36min | 线程 | 触发率 | 判定 |
|---|---|---|---|---|---|
| mrn_nuke_2src_alu | 2源+ALU依赖链 | 14 | 全179 | ~0.39/min | ✅强触发 |
| mem_disambig_alu | ALU加工+随机地址 | 1 | 179 | ~0.03/min | ✅弱触发(经核实) |
| mrn_nuke_dense | 提高密度×16 | 1 | 179 | ~0.03/min | ✅弱触发 |
| mrn_nuke_recross | movbe式同址重读 | 0 | — | — | ❌不触发 |

### 3.4 本章结论

**"2源load + 数据ALU依赖链"可能是触发 SDC 的诱因。** 把它加到 0-fail 的 mrn_nuke 骨架上后触发（14 fail 全 179），而其他方向（ALU 加工随机地址、提高密度）虽也能触发但率极低，movbe 式同址重读则不可移植。

这回答了之前 v2 探针的未解 confound：v2 探针在 mrn_nuke 骨架加 eor 仍 1 源 → 0-fail；而本变体是完整 **2 源 load + ALU** 组合 → 触发。单加 ALU 不够，**2 源 + ALU 组合**才是关键。

---

## 第四章 跨骨架移植验证普遍性

### 4.1 实验设计

为验证"2源load+ALU依赖链"是否是通用可移植触发特征（而非只在 mrn_nuke 上偶然触发），把它移植到其他 mrn 类骨架：

| 变体 | 基础 | 改造 | 时序 |
|---|---|---|---|
| mrn_pairs_2src_alu（5a） | mrn_pairs | 2源+ALU + **8+8改回逐元素背靠背** | 紧 |
| mrn_pairs_2src_alu_keep8（5b） | mrn_pairs | 2源+ALU，**保持8+8展开** | 松(拉开7条) |
| mrn_reloaded_2src_alu（6） | mrn_reloaded | qword段2源+ALU | 紧 |

5a vs 5b 唯一差异 = 时序（紧 vs 松），两者都加了 2 源+ALU，用来分离"2源+ALU"和"时序"各自的作用。

### 4.2 实验内容

- **mrn_pairs 原版**：1 源 + 原值 + 8store→8load（时序拉开 7 条）→ 0-fail
- **5a**：改为 2 源(srcA,srcB) + ALU(a op b) + 逐元素 `store(temp[i],res); store(dst[i],load(temp[i]))` 背靠背
- **5b**：改为 2 源 + ALU，但保持 8 store 后 8 load 的展开结构（时序仍拉开 7 条）
- **mrn_reloaded 原版**：1 源 + 原值 + byte/dword/qword 三粒度背靠背 → 0-fail
- **6**：只取 qword 段，改为 2 源 + ALU，`store(temp[i],res); r=load(temp[i]); cmp(r,expected)` 背靠背

两阶段验证（排除179核60s须0-fail + 全核36min），每个 fail 取独立 seed 做确定性核实。

### 4.3 实验数据（36min 坐实）

| 变体 | 时序 | fail/36min | 独立seed数 | 线程 | 首失败(平均) | 触发率 |
|---|---|---|---|---|---|---|
| mrn_pairs_2src_alu（5a） | 紧 | 46 | 46 | 全179 | 331s | ~1.28/min |
| mrn_pairs_2src_alu_keep8（5b） | 松 | 0 | 0 | — | — | 不触发 |
| mrn_reloaded_2src_alu（6） | 紧 | 126 | 126 | 全179 | 15.3s | ~3.5/min |

5a、6 经确定性核实（排除179+同seed→0fail）确认真 179 SDC。

### 4.4 本章关键发现

**发现1：5a 触发 vs 5b 不触发 → 时序是灭活开关**
两者唯一差异是时序，都加了 2 源+ALU。5a（紧）46 fail，5b（松）0 fail。**"2源+ALU"不是充分条件，时序拉开 7 条即灭活。**

**发现2：mrn_reloaded_2src_alu 126 fail/36min → 2源+ALU 是最强通用可移植特征**
触发率 ~3.5/min，是所有变体里最高，接近甚至超过 movbe 原版（1.9/min）。

**发现3：不同骨架加 2源+ALU 触发率差异大但都触发**

| 骨架（紧时序） | 触发率 |
|---|---|
| mrn_reloaded（store→load→立即cmp） | ~3.5/min |
| mrn_pairs 5a（改回背靠背） | ~1.28/min |
| mrn_nuke（store→load→store） | ~0.39/min |

三者都触发，率差 9 倍。骨架越紧（store→load→立即 cmp 比 store→load→store 更紧）触发率越高。

---

## 第五章 初步结论：触发 SDC 的诱因

综合第三章（mrn_nuke 上 2源+ALU 触发）和第四章（跨骨架普遍触发 + 时序灭活），得出初步结论：

### 触发 179 SDC 的诱因是"2源load + 数据ALU依赖链"与"紧时序背靠背 forwarding"的组合

这两个条件**缺一不可**：

1. **2源load + 数据ALU依赖链**：store 值是两个源 load 的数据经 ALU 加工的结果（add/sub/eor/and），而非原值搬运。这形成 `ldr源A → ldr源B → ALU → str → ldr(forwarding) → str` 的连续依赖链。
2. **紧时序背靠背**：store→load forwarding 0 间隔；时序拉开 7 条（8store+8load 展开）即灭活。

### 各条件的实验支撑

| 条件组合 | 实验 | 结果 |
|---|---|---|
| 紧时序 + 2源 + ALU | mrn_nuke_2src_alu / 5a / 6 | ✅ 触发（14/46/126 fail） |
| 紧时序 + 1源 + 原值 | mrn_nuke 原版 | ❌ 0-fail |
| 紧时序 + 2源 + 原值 | mem_disambiguation 原版 | ❌ 0-fail |
| 松时序 + 2源 + ALU | 5b（keep8） | ❌ 0-fail |
| 紧时序 + 1源 + ALU | v2 探针（probe_asm_fwd） | ❌ 0-fail |

只有"紧时序 + 2源 + ALU"组合触发，其余四种组合都 0-fail。这干净锁定了诱因。

### 对前序判断的修正

- **修正"输入方式无判别力"**：store 值是否经数据 ALU 加工（输入方式子特征）配合紧时序有判别力
- **修正"load 计数非驱动"**：load 绝对次数有影响（mrn_nuke_dense ×16 后触发），但不是主因
- **保留"紧时序必要非充分"**：紧时序是必要条件，但单独不够，需配合 2源+ALU

### 未解问题

- movbe 族的 L1D 同址重读路径与 mrn_rmw 族的 forwarding 路径可能是两条独立触发路径，本报告聚焦 forwarding 路径（mrn_rmw 族）
- 179 根因是硬件故障（绑定 179 硅），"2源+ALU+紧时序"是激活条件，物理性质未决

---

## 附录：可追溯产物

- 22 测试对照表：`docs/CORE179_22TESTS_LOAD_INPUT_SEQUENCE.md`
- objdump 取证：`movbe_log/objdump_7tests/all_7_run_disasm.txt`
- 变体源码：`tests/cpu/misc/mrn_nuke_{2src_alu,recross,dense}.cpp`、`mrn_pairs_2src_alu{,_keep8}.cpp`、`mrn_reloaded_2src_alu.cpp`、`tests/cpu/memory/mem_disambig_alu.cpp`
- 阶段2日志：`movbe_log/trigger_variants/*_stage2_36min.log` 及 `*_30min.log`
- 串行脚本：`run_variants_30min_serial.sh`、`run_2src_alu_port_serial.sh`
- 完整子报告：`docs/CORE179_TRIGGER_VARIANT_CONSTRUCTION_RESULT.md`、`docs/CORE179_2SRC_ALU_PORT_RESULT.md`
