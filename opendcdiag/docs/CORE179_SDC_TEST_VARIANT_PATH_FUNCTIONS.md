# CORE179 SDC：mrn_rmw 测试用例变体功能与路径分类记录

> 日期：2026-08-31
> 范围：逐个记录 mrn_rmw 系列测试用例变体的真实功能（热循环走哪条 load 路径），明确哪些"绕过 L1D"、哪些"不绕过"、哪些是"插 nop 拉时序"。
> 同时记录冷分支重算（recompute）方法的局限性——它无法排除 L1D 读/写路径故障。
> 数据来源：源码逐字核对（`tests/cpu/misc/mrn_rmw_*.cpp`）。
> 注：客观事实记录，不含推理。本文档纠正之前把 `mrn_rmw_nop/nop1/nop4` 错归为"绕过 L1D"的错误。

---

## 一、核心纠错：nop 变体没有绕过 L1D

之前的文档把 `mrn_rmw_nop / nop1 / nop4` 归类为"绕过 L1D 阵列读（forwarding）路径"，**这个归类结论对，但措辞容易误导**。准确说法是：

- `mrn_rmw_nop / nop1 / nop4 / nop8 / nop16 / nop64` 的 nop 是**插入数据无关的 ALU 空操作指令**（`mov x9, x9`），作用是**拉长 str→ldr 之间的时序间隔**。
- nop **不碰内存、不碰缓存**，store buffer 未排空，reload **仍走 store-buffer forwarding**（数据还在 store buffer 里，没经过 L1D 阵列读）。
- 源码注释明确（`mrn_rmw_timing_probe.cpp:22-25`）："Pure timing delay: touches NO memory and NO cache, so the reload still goes through store-buffer FORWARDING (the stored line is still in the store buffer; nothing evicted it)."

**所以这些 nop 变体是"forwarding 路径 + 不同时序窗口"，不是"绕过 L1D 的另一种独立路径"——它们和 mrn_rmw_dump/mrn_rmw_fwd 走的是同一条 forwarding 路径，只是时序不同。**

---

## 二、mrn_rmw 变体功能逐个记录（按源码）

### A. forwarding 路径（同址 str→ldr，数据不经 L1D 阵列读）

热循环结构：`store_qword(&temp[i], res); dst[i] = load_qword(&temp[i]);` —— str 和 ldr 同址，reload 由 store buffer 转发。

| 测试用例 | 源码 | str→ldr 间插入 | 功能说明 |
|---|---|---|---|
| mrn_rmw | `mrn_rmw.cpp` | 无 | 原始 RMW 基线，4 指令混合 add/sub/xor/and |
| mrn_rmw_dump | `mrn_rmw_dump.cpp` | 无 | 同 mrn_rmw 布局，加冷分支 recompute + dump |
| mrn_rmw_fwd | `mrn_rmw_fwd_vs_l1d.cpp` | 无 | forwarding 基线（与 mrn_rmw 同结构，单独抽出） |
| mrn_rmw_nop | `mrn_rmw_timing_probe.cpp` | 2 个 `mov x9,x9` | forwarding + ~2 cyc 时序窗口 |
| mrn_rmw_nop1 | 同上 | 1 个 nop | forwarding + ~1 cyc |
| mrn_rmw_nop4 | 同上 | 4 个 nop | forwarding + ~4 cyc |
| mrn_rmw_nop8 | 同上 | 8 个 nop | forwarding + ~8 cyc |
| mrn_rmw_nop16 | 同上 | 16 个 nop | forwarding + ~16 cyc |
| mrn_rmw_nop64 | 同上 | 64 个 nop | forwarding + ~20+ cyc（store 可能已排空，边界模糊） |

**这 9 个变体都走 forwarding 路径**，彼此唯一区别是 str→ldr 的时序间隔（0/1/2/4/8/16/64 cyc）。nop64 是边界情况：64 nop 后 store 可能已排空到 L1D 阵列，reload 可能切到 L1D 阵列读——这是 `mrn_rmw_diff_nop64` 要对照解决的疑问（见 §V6 决策表）。

### B. L1D 阵列读路径（异址，forwarding 不可能）

热循环结构：`store_qword(&tempA[i], res); got = load_qword(&tempB[i]);` —— str 写 tempA，ldr 读 tempB（异址），tempB 自 init 常驻 L1D，forwarding 不能跨地址 → reload 必走 L1D 阵列读。

| 测试用例 | 源码 | 变量 | 功能说明 |
|---|---|---|---|
| mrn_rmw_diff | `mrn_rmw_fwd_vs_diff.cpp` | 异址，tempB 驻 L1D | L1D 阵列读基线 |
| mrn_rmw_diff_64k | `mrn_rmw_diff_footprint.cpp` | 异址 + tempB=64KB（=L1D 容量） | L1D 阵列读，footprint 恰好填满 L1D |
| mrn_rmw_diff_1m | 同上 | 异址 + tempB=1MB（16×L1D） | reload miss L1D，走 L2/L3 |
| mrn_rmw_diff_nop64 | `mrn_rmw_diff_timing_probe.cpp` | 异址 + 64 nop | L1D 阵列读 + 长时序间隔（矩阵另一格） |

**这 4 个变体走 L1D 阵列读路径**，异址保证 forwarding 不可能。`mrn_rmw_diff_nop64` 是 2×2 时序矩阵的"异址+长间隔"格，专门用来区分 `mrn_rmw_nop64` 的 0-fail 是"路径切到 L1D 阵列"还是"时序窗口关闭"。

### C. 强制逐出走 L1D 阵列（同址 + dc civac）

| 测试用例 | 源码 | 功能说明 |
|---|---|---|
| mrn_rmw_l1d | `mrn_rmw_fwd_vs_l1d.cpp` | 同址 str→ldr，但中间插 `dc civac`+`dsb` 逐出刚存的行，reload 走 L1D 阵列/更远 |
| movbe_l1d | `movbe_l1d_vs_l2.cpp` | movbe 的 reload 命中 L1D（对照基线） |
| movbe_l2 | 同上 | movbe + `dc civac` 逐出，reload 走 L2/L3 |

`mrn_rmw_l1d` 的 0-fail（8-31 复测 30min）和 `mrn_rmw_diff` 的 8-fail 摆一起，说明"走 L1D 阵列读"这个粗分类下，逐出后重读（l1d）不触发但异址驻留（diff）触发——细分类变量影响触发。

---

## 三、2×2 时序矩阵（设计意图）

源码（`mrn_rmw_diff_timing_probe.cpp`、`mrn_rmw_timing_probe.cpp`）设计了一个 2×2 矩阵来区分"路径"和"时序"两个变量：

| | 同址（forwarding 可能） | 异址（forwarding 不可能，必走 L1D 阵列） |
|---|---|---|
| **0/少 nop（短间隔）** | mrn_rmw_fwd / mrn_rmw_dump / mrn_rmw_nop1 | mrn_rmw_diff |
| **64 nop（长间隔）** | mrn_rmw_nop64 | mrn_rmw_diff_nop64 |

矩阵用途：如果 `mrn_rmw_nop64`（同址+64nop）0-fail 而 `mrn_rmw_diff_nop64`（异址+64nop）触发，说明 nop64 的 0-fail 不是"路径切到 L1D 阵列"，而是"forwarding 路径的时序窗口关闭"——因为异址那条无论 nop 多少都走 L1D 阵列，它的结果不受路径切换影响。

---

## 四、冷分支重算（recompute）方法的局限性

> 此节记录用户 2026-08-31 的分析。recompute 方法（在 `mrn_rmw_dump.cpp` 冷分支用 inputA/inputB 重算）只能定位错误发生在"存储→转发之前"，**无法排除 L1D 读/写路径故障**。

### 4.1 recompute 方法回顾
冷分支用同一份 `inputA/inputB` 重算 `res_recompute = ALU(a,b)`，与热循环存入 `temp[i]` 的值比较，用 `temp==recompute` 判断 store 是否忠实。判据：
- `golden == recompute` → 正确值确定
- `temp != recompute` → 归为 `[ALU-COMPUTE-WRONG]`
- `temp == dst` → forwarding 忠实

### 4.2 局限性：三种错误源无法区分

recompute 判 `temp != recompute` 就归为 `[ALU-COMPUTE-WRONG]`，但以下三种情况**都会**产生 `temp != recompute 且 temp == dst`，recompute 无法区分：

| 错误源 | 机理 | recompute 表现 |
|---|---|---|
| **输入 load 错（L1D 读错）** | 热循环 `a=srcA[i]`/`b=srcB[i]` 时 L1D 返回错值，ALU 基于错输入算出错 res。冷分支重算时从同址 reload，因时序/缓存状态/间歇性可能读到正确值 | temp(错) != recompute(对) → 误判 ALU-COMPUTE-WRONG |
| **ALU 计算错** | ALU 执行/写回寄存器时算错，store 忠实写入错值 | temp != recompute → ALU-COMPUTE-WRONG（这种情况判对了） |
| **store 写错（L1D 写错）** | ALU 算对，但 `store_qword(&temp[i],res)` 时 L1D 写入错值 | temp(错) != recompute(对) → 误判 ALU-COMPUTE-WRONG |

### 4.2.1 数值例子（用户 2026-08-31 分析）

设某次迭代 `srcA[i]=10`、`srcB[i]=3`、当前操作为 `sub`，正确结果应为 `10-3=7`。三种错误源都产生 `temp=5, recompute=7, temp!=recompute, temp==dst`，全部归为 `[ALU-COMPUTE-WRONG]`：

| 错误源 | 热循环 a/b/res | temp | dst | recompute | temp≠recompute? | 判定 |
|---|---|---|---|---|---|---|
| **输入 load 错**（L1D 读 srcA 返回 8） | a=8, b=3, res=5 | 5 | 5 | 7 | 是 | ALU-COMPUTE-WRONG（误判） |
| **ALU 算错**（输入对，ALU 输出 5） | a=10, b=3, res=5 | 5 | 5 | 7 | 是 | ALU-COMPUTE-WRONG（判对） |
| **store 写错**（ALU 出 7，L1D 写成 5） | a=10, b=3, res=7 | 5 | 5 | 7 | 是 | ALU-COMPUTE-WRONG（误判） |

三种情况在 `temp==dst` 条件下表现**完全一致**，recompute 输出无差别，无法区分。

#### "存储→转发之前"的精确含义

`temp == dst` 成立，证明 **`store` 指令写下的值（无论对错）被 `load` 指令忠实转发到了 `dst`**——即 `temp[i] → dst[i]` 这段 store→forwarding 路径正常。但 `temp[i]` 的值是 `ALU(load(srcA[i]), load(srcB[i])) → 经 store 写入`，若 `temp[i] != recompute`，只能说明**从 ALU 输入到 store 写完之前**的某个环节出错，无法区分是：
- `load(srcA[i])` 读错了
- `load(srcB[i])` 读错了
- ALU 算错了
- `store` 写错了

这四种在 `temp==dst` 下表现完全一致。"存储→转发之前"= ALU 计算 → store 执行（写 L1D）→ store buffer 转发，这段路径正常；错误只能发生在其上游的输入加载/计算/写入环节。

#### 第四种情况（recompute 可部分区分，但 8-30 未出现）

若 `expected[i]`（init 时核 0 算的 golden）本身错了而热循环算对了，则 `temp==recompute==dst==正确值 != golden` → 触发 fail，但 `temp==recompute` 会标 store-faithful，recompute 能区分这种情况。8-30 的 3 条样本均为 `temp != recompute`，不属于这种。

#### srcA/srcB 内存值就错 vs 读时返回错（部分可观察）

recompute 用 `inputA = data->srcA[i]`、`inputB = data->srcB[i]`（`mrn_rmw_dump.cpp:149-150`），是冷分支重新从 srcA/srcB 读的：
- 若错误是 **L1D 读时返回错值（但内存对）**：冷分支重读时序不同，可能读到对的 → `temp != recompute` → 误判 ALU-COMPUTE-WRONG（对应第 1 种）
- 若错误是 **内存里就存了错值**（init 时错或被写坏）：冷分支也读到错值 → `recompute == temp` → 标 store-faithful（这种情况 recompute 能部分区分）

8-30 的 3 条样本都是 `temp != recompute`，属于"L1D 读时返回错值 / ALU 算错 / store 写错"三者之一，recompute 分不开。

### 4.3 结论
recompute 方法**只能定位错误发生在"存储→转发之前"**（即 store+forwarding 这段没问题），但**无法区分**：
- 输入加载错误（L1D 读错）
- ALU 计算错误
- 存储写入错误（L1D 写错）

三者都导致 `temp != recompute 且 temp == dst`，全部归为 `ALU-COMPUTE-WRONG`。

→ **recompute 方法不能排除 L1D 读/写路径故障的嫌疑**。要排除 L1D 故障需要额外手段（如单独验证输入加载的正确性，或对比不同缓存路径的结果），而 recompute 没有提供这种区分能力。

→ 之前文档里 `mrn_rmw_dump` 的 3 条 recompute 样本标为 `[ALU-COMPUTE-WRONG]`，**只表示"错误发生在 store→forwarding 之前"，不表示"排除了 L1D"**——这 3 条完全可能是 L1D 读输入时出错（a 或 b 的 load 路径错）导致 ALU 算出错值，recompute 无法排除这种可能。

---

## 五、当前可追溯实测结果（按正确归类）

| 路径分类 | 测试用例 | fail | 时长 | 数据来源 |
|---|---|---|---|---|
| forwarding（同址，数据不经 L1D 阵列读） | mrn_rmw_dump | 2 | 60min | yaml 061555 |
| forwarding + 时序窗口 | mrn_rmw_nop（2nop） | 11 | 30min | yaml 134536 |
| forwarding + 时序窗口 | mrn_rmw_nop1（1nop） | 1 | 30min | yaml 141535 |
| forwarding + 时序窗口 | mrn_rmw_nop4（4nop） | 1 | 30min | yaml 144535 |
| forwarding（movbe 路径，同址 reload） | movbe_dump_golden | 45 | 30min | yaml 071555 |
| forwarding（movbe 路径） | movbe_dump_probe_xn | 1 | 30min | yaml 114537 |
| L1D 阵列读（异址，tempB 驻 L1D） | mrn_rmw_diff | 8 | 30min | yaml 124537 |
| L1D 阵列读（异址+64K footprint） | mrn_rmw_diff_64k | 19 | ~8min | yaml 164554 |
| dc civac 逐出后走阵列 | mrn_rmw_l1d | 0 | 30min | 8-31 持久日志（grep 摘要，无 yaml 逐 loop） |
| 异址+64nop（矩阵另一格） | mrn_rmw_diff_nop64 | 0 | 30min | 8-31 持久日志（grep 摘要，无 yaml 逐 loop） |
| dc civac 逐出后走 L2/L3（movbe 路径） | movbe_l2 | 0 | 30min | **8-31 完整 stdout 三方法交叉确认（见 §五注）** |

注：movbe_dump_golden/probe_xn 的 reload 是第二次 bswap 被编译器折叠成对 `input[i]` 的 reload（同址，store buffer 未排空时走 forwarding）。

**movbe_l2 数据来源与三方法交叉确认（2026-08-31 12:58–13:28 复跑，全程守候）**：

全核 192 含 179、auto seed、`-T 30m`，12:58:40 启动、13:28:47 完成（rc=0）。这次用 `-o` 落完整 stdout（**不经 grep 管道**，1293 行），三方法交叉确认是**干净的 0-fail**：

| 方法 | 结果 |
|---|---|
| 退出码 | rc=0，stdout 末行 `exit: pass` |
| 完整 stdout 逐 loop | 136 个 `# Loop iteration finished`，**136 个 `result: pass`**，**0 个 `result: fail`**，**0 行 miscompare** |
| yaml | 无（见下：`-o` 时不写 yaml） |

后台监控全程记录 loop 1→136 递增、fails 全程=0、正常退出。

**`-o` 选项时不写 yaml（机制发现）**：用 `-o "$LOG"` 把 stdout 重定向到文件时，框架**不单独写 yaml**（before=33, after=33）。之前 `-T 2s` 短跑产 yaml 是因为没用 `-o`。即 **`-o` 和 yaml 落盘互斥**——框架检测到 stdout 被重定向到文件，结果全写进那个文件，不再写 yaml。这解释了 10:46 那次为何无 yaml（那次也用了 `-o`/重定向，但被 grep 管道过滤成只剩 11 字节 `exit: pass`，丢掉了逐 loop 信息）。**正确做法**：用 `-o` 时完整 stdout 本身就是逐 loop 证据（含 `result: pass`/`miscompare`），等同于 yaml 内容；**不要在 `-o` 后再接 grep 管道**（会把逐 loop 行滤掉）。

**仍不能干净归因（同前）**：movbe_l2 是"dc civac+dsb 逐出 L1D 行 + 拉长时序"的双变量探针，0-fail **不能干净归因"绕过 L1D"**（见 [intervention-decoupling-impossible-use-pmu]）。此条现在坐实了"绕过 L1D 走 L2 路径 30min 不触发"的事实，但归因仍受双变量限制。

---

**mrn_rmw_l1d / mrn_rmw_diff_nop64 的证据强度（仍弱，待重跑）**：

这两条 "0" 仍只来自 `run_campaign_resume.sh` 的 **grep 管道摘要**（只剩 `exit: pass`），**未经三方法交叉确认**。按 §六.5 的判据应标 `0*`。要坐实需按 movbe_l2 的方式重跑（`-o` 落完整 stdout + 数逐 loop `result: pass`）。在此之前，这两条的"0"方向上可信（rc=0）但证据弱。

**复核时清理了两条临时 yaml**（复现跑产生的 `opendcdiag-20260831T044421` / `T044733`，非真实 campaign，已删）。

---

## 六、对之前文档结论的修正

1. **"绕过 L1D 和不绕过 L1D 都触发 SDC"** —— 这个结论本身没错，但之前的措辞把 nop 变体当成"绕过 L1D 的独立路径"是不准确的。准确表述：**forwarding 路径（数据不经 L1D 阵列读，含 nop 时序变体）触发，L1D 阵列读路径（异址）也触发**。nop 变体是 forwarding 路径的时序变化，不是独立绕过路径。

2. **"recompute 证明 ALU sub 算错"** —— 需收窄为：recompute 证明"错误发生在 store→forwarding 之前"，但无法区分是输入 load 错（L1D 读）、ALU 算错、还是 store 写错（L1D 写）。3 条样本标 `[ALU-COMPUTE-WRONG]` 只表示"错误在 store+forwarding 之前"，**不排除 L1D 故障**。

3. **L1D 故障嫌疑未排除** —— recompute 方法和路径对照实验都不能干净排除 L1D 读/写路径故障（recompute 分不开输入 load 错；路径对照受时序变量干扰）。L1D 是否有故障仍是未决问题。

4. **movbe_l2 的 0-fail 已坐实，但不等于"排除 L1D"** —— movbe_l2（dc civac+dsb 逐出后 reload 走 L2/L3）8-31 复跑 30min 全核，三方法交叉确认**干净的 0-fail**（136/136 loop pass，0 miscompare，完整 stdout 落盘，见 §五注）。但 dc civac+dsb 在逐出 L1D 行的同时**也拉长了时序间隔**，属于"路径与时序双变量同动"的探针（见 [intervention-decoupling-impossible-use-pmu]）。其 0-fail 可由"reload 不再命中 L1D"解释，也可由"时序窗口被拉长"解释，**不能干净归因"绕过 L1D 所以不触发"**。此条坐实了"绕过 L1D 走 L2 路径 30min 不触发"的事实，但归因仍受双变量限制，**不构成 L1D 无故障的证据**。

5. **grep 管道摘要的漏检陷阱 + `-o` 时不写 yaml（方法论教训，2026-08-31 复核发现）** —— 两个机制：
   - **grep 管道漏检**：`run_campaign_resume.sh` 的 `| grep -E "result:|miscompare|time-to-fail|exit:"` 管道在 **pass 跑**下只剩 `exit: pass`（框架 pass 时不打逐 loop `result:`，只 fail 时打 `miscompare`）。**单看 grep 摘要无法区分"真 0-fail 跑满时长"和"异常/秒杀但框架仍打 exit:pass"**——这是过去漏检 SDC 的根因之一。mrn_rmw_l1d / mrn_rmw_diff_nop64 两条仍受此限（标 `0*`）。
   - **`-o` 时不写 yaml**：用 `-o "$LOG"` 重定向 stdout 到文件时，框架**不写 yaml**（`-o` 与 yaml 落盘互斥，结果全进 `-o` 指定的文件）。但 `-o` 落的完整 stdout **含逐 loop `result: pass`/`miscompare`**，等同 yaml 内容——**前提是 `-o` 后不接 grep 管道**（接了会把逐 loop 行滤掉，10:46 那次 movbe_l2.log 只剩 11 字节就是这么来的）。
   - **判 0-fail 的三方法交叉确认判据**（movbe_l2 已据此坐实）：(a) `exit: pass`/rc=0，(b) 完整 stdout（`-o` 落盘，无 grep）逐 loop `result: pass` 数 = loop 数，且无 `miscompare`，(c) 若无 `-o` 则用 yaml 逐 loop `result: pass`。三者满足其二即干净 0；仅 (a) 标 `0*`。
