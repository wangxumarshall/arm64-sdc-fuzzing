# CORE179 SDC：触发指令序列特征与核内硬件路径归因

> 日期：2026-09-01
> 范围：从 22 测试 30min 实测 + objdump 取证出发，回答两个问题——(1) 哪些指令序列是"好的"（不触发 SDC）、哪些"能触发 SDC"；(2) 从这些指令序列看它们是否经过某些统一的硬件。
> 数据来源：10 个测试的 run 函数完整 objdump（2 触发 + 8 不触发），与主二进制交叉验证一致。可追溯产物 `movbe_log/objdump_7tests/all_7_run_disasm.txt`（810 行，含 7+3 全部）。
> 前序：`docs/CORE179_OBJDUMP_TRIGGER_VS_NOTRIGGER_ANALYSIS.md`（已证伪 forwarding 微操作同构与 load 计数两个假说）。

---

## 一、10 个测试的指令序列分类

按"store 前**数据 ALU** × **紧邻重载**"两个维度分类。定义：
- **数据 ALU** = 操作数含从内存 load 来的值的 ALU 运算（`rev w4,w1` 的 w1 来自 ldr；`eor x2,x0,x3` 的 x0/x3 来自 ldr）。区别于**地址 ALU**（`add x0,base,idx` 结果只用作访存地址，如 mrn_nuke 的 `add x0,x22,x19`）。
- **紧邻重载** = 同一数据/相关地址在几条指令内被第二次访存读取（ldr 同址重读，或 str→ldr 同址 forwarding）。

| 测试 | 内层循环指令序列 | store前数据ALU | 紧邻重载 | 触发? |
|---|---|:---:|:---:|:---:|
| **movbe** | `ldr w1,[input]→rev w4,w1→str w4,[swapped]→ldr w4,[input同址]→cmp` | 有(rev) | 有(L1D同址重读) | **是 1.9/min** |
| **mrn_rmw** | `ldr[srcA]→ldr[srcB]→eor x2,x0,x3→str x2,[temp]→ldr x0,[temp同址]→str[dst]` | 有(eor/and/add/sub) | 有(forwarding重载) | **是 0.2/min** |
| mrn_nuke | `ldr[src]→add x0,base,idx(地址ALU)→str x1,[temp]→ldr x0,[temp同址]→str[dst]` | **无** | 有(forwarding) | 否 0 |
| mem_disambig-m1 | `ldr[off]→ldr[val]→add x6,base,off(地址ALU)→str x5,[buf]→ldr x6,[buf同址]→cmp` | **无** | 有(forwarding) | 否 0 |
| atomic_seq_cst | `ldr[val]→add x1,base,idx(地址ALU)→stlr x4,[addr]→ldar x5,[addr同址]→cmp` | **无** | 有(STLR/LDAR forwarding) | 否 0 |
| mrn_flags | `ldr[src]→mvn x0,x0(数据ALU)→cmp→csel→str x0,[dst异址]` | 有(mvn) | **无** | 否 0 |
| mite | `ldr[input]→add→eor→sub(数据ALU链)→…`（无 str→ldr 同址） | 有(add/eor/sub) | **无** | 否 0 |
| mrn_pairs | 8×str 后 8×ldr（拉开 7 条，非紧邻） | 无 | 弱(时序拉开) | 否 0 |
| mrn_reloaded | `ldr→add(地址)→strb→ldrb同址`（sub-word，地址ALU） | **无** | 有(forwarding) | 否 0 |
| part_store_fwd_jit | `random×2→blr(JIT func内 str+ldr)`（函数调用隔开时序） | 无(间接) | 弱(经blr) | 否 0 |

---

## 二、触发的 2×2 判定矩阵

|  | **有紧邻重载** | **无紧邻重载** |
|---|---|---|
| **store 前有数据 ALU** | movbe ✅触发 / mrn_rmw ✅触发 | mrn_flags ❌ / mite ❌ |
| **store 前仅地址 ALU** | mrn_nuke ❌ / mem_disambig ❌ / atomic_seq_cst ❌ / mrn_reloaded ❌ | （mrn_pairs 弱重载 ❌） |

**观察**：触发全部落在"**数据 ALU + 紧邻重载**"一格；其余三格全部 0-fail。

**这个矩阵的强度分层（诚实标注）**：
- **强证据（forwarding 族内）**：mrn_rmw(触发) vs mrn_nuke/mem_disambig/atomic_seq_cst(不触发)。这四个的 store→load 微操作**字节同构**（`add; str; ldr` 同址同寄存器背靠背），唯一差异是 store 前有数据 ALU（mrn_rmw 的 eor/and/add/sub 操作 load 值）还是仅地址 ALU（其余四个的 add 只算访存地址）。这是受控对比，结论可靠。
- **弱提示（movbe 跨族）**：movbe 也触发且在"数据 ALU + 重载"格，但它的重载是 L1D 同址重读（非 forwarding），且其数据 ALU（rev）的输出存到 swapped，而第二次 ldr 重读的是 input——**rev 的结果与第二次 ldr 无数据依赖**。所以 movbe 归入此格略勉强，它的触发机制可能与 mrn_rmw 不同（更像"对同一 L1D 行紧邻两次 ldr 一致性"，见记忆 `isolated-recross-golden-protocol`）。movbe 只提供"数据 ALU + 紧邻重载也能触发"的**提示**，不提供与 forwarding 族的受控对比。

---

## 三、forwarding 族内强对比（objdump 字节级）

四个 forwarding 测试的 store→load 微操作**逐条同构**，只差 store 前的数据来源：

```
mrn_rmw(触发):     ldr x0,[srcA]; ldr x3,[srcB]; eor x2,x0,x3(数据ALU); add x0,temp,i; str x2,[x0]; ldr x0,[x0]
mrn_nuke(0):       ldr x1,[src];                    add x0,temp,i(地址ALU);             str x1,[x0]; ldr x0,[x0]
mem_disambig-m1(0):ldr x4,[off];ldr x5,[val];       add x6,buf,off(地址ALU);            str x5,[x6]; ldr x6,[x6]
atomic_seq_cst(0): ldr x4,[val];                    add x1,base,idx(地址ALU);           stlr x4,[x1]; ldar x5,[x0]
```

store→load 段（`str/stlr; ldr/ldar` 同址同寄存器）四个**完全同构**。mrn_rmw 多出的只是 store 前对 load 值做了 `eor/and/add/sub`。mrn_nuke 把 load 来的原值**原样**store，mem_disambiguation/atomic_seq_cst 也是原样 store（不加工数据值）。

→ **在 forwarding 族内，"store 的值是否经过数据 ALU 加工"是触发开关**。

---

## 四、触发序列的核内硬件路径追踪

ARMv8.1-A（Kunpeng 920）核内数据通路相关单元：**L1D 阵列(64KB) / Store Buffer(SB) / Load Store Queue(LSQ) / 整数 ALU / Load Port（读出口）/ 寄存器堆**。

### mrn_rmw（触发）的微操作→硬件单元映射
```
ldr x0,[srcA]   → L1D阵列 → Load Port → 寄存器x0
ldr x3,[srcB]   → L1D阵列 → Load Port → 寄存器x3
eor x2,x0,x3    → 整数ALU(操作两个load值) → 寄存器x2
add x0,temp,i   → 地址ALU(算temp地址)
str x2,[x0]     → 寄存器x2 → Store Buffer
ldr x0,[x0]     → Store Buffer(forwarding) → Load Port → 寄存器x0   ← 第二次访存,经forwarding
str x0,[dst]    → 寄存器x0 → Store Buffer
```
**关键**：第二个 ldr 的数据来源是 **Store Buffer forwarding**（不经 L1D 阵列），经 Load Port 回到寄存器。store 的值是**整数 ALU 加工 load 值的输出**。

### movbe（触发）的微操作→硬件单元映射
```
ldr w1,[input]  → L1D阵列 → Load Port → 寄存器w1
rev w4,w1       → 整数ALU(操作load值) → 寄存器w4
str w4,[swapped]→ 寄存器w4 → Store Buffer(→最终L1D swapped)
ldr w4,[input]  → L1D阵列(同址重读) → Load Port → 寄存器w4   ← 第二次访存,经L1D阵列
cmp w4,w1       → 比较两次读input的结果
```
**关键**：第二个 ldr 的数据来源是 **L1D 阵列同址重读**（不是 forwarding，因为没 store 到 input），经 Load Port。两次 ldr 都从 L1D 阵列读同一行。

### 不触发 forwarding 测试的路径（以 mrn_nuke 为例）
```
ldr x1,[src]    → L1D阵列 → Load Port → 寄存器x1
add x0,temp,i   → 地址ALU
str x1,[x0]     → 寄存器x1(原load值,未加工) → Store Buffer
ldr x0,[x0]     → Store Buffer(forwarding) → Load Port → 寄存器x0   ← 与mrn_rmw同路径!
```
**mrn_nuke 的第二个 ldr 走的硬件路径与 mrn_rmw 完全相同**（SB forwarding → Load Port），只是 store 的值未经数据 ALU。

---

## 五、关于"统一硬件"的结论

### 1. forwarding 族内：触发与不触发经过**完全相同**的硬件路径
mrn_rmw（触发）与 mrn_nuke/mem_disambiguation/atomic_seq_cst（不触发）的 store→load 段都走 **Store Buffer → forwarding → Load Port**，硬件单元逐个相同。区别只在 store 的数据来源是否经数据 ALU 加工。

→ **不存在"触发专属的统一硬件单元"**。在 forwarding 族内，触发不取决于"经过哪个硬件单元"，而取决于"**数据值是否经数据 ALU 加工后立即 store 并被 forwarding 紧邻重载**"这个**时序数据依赖模式**是否命中 179 的 marginal 窗口。数据 ALU 在 store 前插入的额外周期/数据依赖，改变了 store buffer 提交与 forwarding 的时序关系。

### 2. movbe 跨族：第二次 ldr 走 L1D 阵列（非 forwarding）也触发
movbe 的第二次 ldr 从 L1D 阵列同址重读（不经 SB forwarding），与 mrn_rmw 的第二次 ldr（SB forwarding）**走的硬件不同**，但都触发。

→ **"第二次访存的数据来源（L1D 阵列 vs SB forwarding）"不是区分因素**。两族都经 **Load Port** 这个最终读出口，但所有 ldr（包括不触发的 mrn_nuke）都经 Load Port，所以"经 Load Port"也不是充分判据。

### 3. 跨两族的弱共性："数据 ALU + 紧邻重载"的时序模式
movbe（L1D 重读族）与 mrn_rmw（forwarding 族）都触发，且都在"数据 ALU + 紧邻重载"格。提示：**窄时序窗内，一个经数据 ALU 加工的值被紧邻重载**，可能是跨族共性。但 movbe 的数据 ALU（rev）输出与第二次 ldr 无数据依赖（rev 结果存 swapped，第二次读 input），故此共性较弱，不能确认两族同机制。

### 4. 与"路径↔时序绑死"教训的呼应
记忆 `intervention-decoupling-impossible-use-pmu` 指出：在 179 上，干预式实验路径与时序物理绑死，不能干净归因到单一硬件单元。本次 objdump 静态分析**印证**：
- 能**确认**"不是哪个硬件单元"（forwarding 族触发与不触发走相同单元）；
- **不能确认**"是哪个硬件单元"（数据 ALU 改的是时序数据依赖模式，不是"经过不同硬件"）。
- 即触发因素是"数据流经硬件单元的**时序模式**"，而非"硬件单元本身"。这与根因=179 绑定硬件故障（`sdc-rootcause-is-hardware-not-timing`）、激活机制=时序 marginality 的分层一致。

---

## 六、对既有记忆的修正/调和

| 记忆 | 原描述 | 本次归因修正 |
|---|---|---|
| `load-port-downstream-sdc-confirmed` | "SDC 在 store→reload 路径" | **收窄**：不是任意 store→reload，是"**经数据 ALU 加工的值 store 后紧邻重载**"。mrn_nuke 的 store→reload（原值未加工）不触发。 |
| `l1d-read-path-sdc-confirmed` | "SDC 源在 L1D 读阵列" | **收窄**：movbe 走 L1D 阵列重读触发，但 mrn_rmw 走 SB forwarding（不经 L1D 阵列）也触发。"仅 L1D 阵列读"不充分。 |
| `sdc-trigger-constant-probability-per-ldr` | "load 次数驱动" | **已证伪**（前序文档）：mrn_nuke load 24576 次/轮 0-fail vs mrn_rmw 3072 次/轮触发。 |
| `sdc-rootcause-is-hardware-not-timing` | "根因=硬件故障，时序是候选激活机制" | **印证**：objdump 显示触发与不触发走相同硬件单元，区分在时序数据依赖模式，与"根因硬件、激活时序"分层一致。 |
| `isolated-recross-golden-protocol` | "movbe 真实错在两次 ldr 读同址不一致" | **印证且精确化**：objdump 68/74 行确为同址(x2,x3,lsl#2)两次 ldr。 |

---

## 七、边界与下一步

### 边界（诚实标注）
1. **样本量小**：触发格只有 movbe + mrn_rmw 两个样本，2×2 每格 1-2 个，统计弱。
2. **"数据 ALU"是事后归纳**：从 objdump 观察归纳，非预先假设。需探针验证因果。
3. **movbe 跨族归类勉强**：movbe 的数据 ALU 输出与第二次 ldr 无数据依赖，归入"数据 ALU + 重载"格略勉强，其触发机制可能与 mrn_rmw 不同。
4. **静态分析局限**：objdump 看的是指令序列，看不到微操作实际调度/时序。确认"数据 ALU 改时序"需动态手段（PMU，但受 `intervention-decoupling-impossible-use-pmu` 限制）。

### 下一步：探针二分定位（受控验证因果）
构造基于 **mrn_nuke 骨架**（0-fail，无数据 ALU 的 forwarding）的探针变体，逐步加数据 ALU，看是否从 0-fail 变触发：
- **变体 A**：mrn_nuke 的 store 前插入一个 `eor x1,x1,x1`(数据 ALU 但结果=0，破坏数据) —— 验证"数据 ALU 存在"是否够。
- **变体 B**：mrn_nuke 的 store 值改为 `eor x1,x1,#imm`(数据 ALU 加工原值) —— 验证"加工后的值被 store+重载"是否触发。
- **变体 C**：mrn_rmw 去掉 eor 改为 `mov x2,x0`(原值搬，无数据加工) —— 反向验证去掉数据 ALU 是否灭活。

若变体 B 触发、C 灭活，则"数据 ALU + 紧邻重载"从相关升级为因果。这需要按 `movbe-l1d-variants-schedule-sensitivity` 教训**字节复刻** mrn_nuke 的寻址模式，避免布局扰动灭活。
