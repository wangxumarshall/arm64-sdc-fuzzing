# CORE179 SDC：L1D 路径分析与指令定位记录（以当前可追溯实测为准）

> 日期：2026-08-31
> 范围：记录"179 核 SDC 是否与 L1D 相关"以及"如何定位 sub/xor 嫌疑指令"两类实验的测试用例名称、方法、结果。
> 数据原则：**以当前机器可追溯的实测数据为准**（仓库幸存 yaml `opendcdiag-20260830T*.yaml`、8-31 持久日志 `movbe_log/campaign_resume/`）。无可追溯 yaml 的老测试不参与结论，只在末尾附录列出供参考。
> 注：客观事实记录，不含推理。

---

## 第一部分：L1D 路径分析

### 1.1 核心思路

用**路径对照实验**判断 SDC 是否与 L1D 相关：让 load（读）分别走 store-buffer forwarding（绕过 L1D 阵列读）和走 L1D 阵列读（不绕过），看两条路径是否都触发。

判断依据：
- 若只 forwarding 触发、L1D 阵列读不触发 → 缺陷在 forwarding 路径独有。
- 若只 L1D 阵列读触发、forwarding 不触发 → 缺陷在 L1D 阵列读独有。
- **若两条都触发 → 缺陷不在某一条路径独有，而在两者共同下游（load port → 寄存器）。**

### 1.2 用到的测试用例（均为当前可追溯）

#### A. store-buffer forwarding 路径（绕过 L1D 阵列读）
reload 与刚 store 的地址相同，由 store buffer 直接转发，不经过 L1D 阵列读。

| 测试用例 | 源码 | fail | 时长 | 数据来源 |
|---|---|---|---|---|
| mrn_rmw_dump | `tests/cpu/misc/mrn_rmw_dump.cpp` | 2 | 60min | yaml 061555 |
| mrn_rmw_nop（2nop） | `tests/cpu/misc/mrn_rmw_timing_probe.cpp` | 11 | 30min | yaml 134536 |
| mrn_rmw_nop1（1nop） | 同上 | 1 | 30min | yaml 141535 |
| mrn_rmw_nop4（4nop） | 同上 | 1 | 30min | yaml 144535 |
| movbe_dump_golden | `tests/cpu/misc/movbe_dump_golden.cpp` | 45 | 30min | yaml 071555 |
| movbe_dump_probe_xn | `tests/cpu/misc/movbe_dump_probe_xn.cpp` | 1 | 30min | yaml 114537 |

movbe 的热循环（`movbe_dump_golden.cpp:79-83`）：`val=input[i]; bswap; swapped[i]=val; bswap; if(val!=input[i])` —— 第二次 bswap 被 compiler 折叠成对 `input[i]` 的 reload（同址 str 后 ldr），走 forwarding。

→ **forwarding 路径（绕过 L1D 阵列读）：全部触发，合计 61 fail。**

#### B. L1D 阵列读路径（不绕过，异址）
reload 的地址与刚 store 的不同，forwarding 不可能跨地址 → reload 必走 L1D 阵列读。

| 测试用例 | 源码 | fail | 时长 | 数据来源 |
|---|---|---|---|---|
| mrn_rmw_diff | `tests/cpu/misc/mrn_rmw_fwd_vs_diff.cpp` | 8 | 30min | yaml 124537 |
| mrn_rmw_diff_64k | `tests/cpu/misc/mrn_rmw_diff_footprint.cpp` | 19 | ~8min* | yaml 164554 |

mrn_rmw_diff 源码（`mrn_rmw_fwd_vs_diff.cpp:124-129`）：`store_qword(&tempA[i], res); got=load_qword(&tempB[i]); if(got!=expected)` —— str 写 tempA，ldr 读 tempB（异址），tempB 自 init 常驻 L1D。check 只比 ldr 结果，ALU 的 res 不参与比较。

*mrn_rmw_diff_64k 跑约 8min 被重启中断，19 fail 是这 8min 的。

→ **L1D 阵列读路径（异址）：也触发，合计 27 fail。**

#### C. L1D 阵列读路径（同址 + dc civac 逐出后）
reload 前先 `dc civac`+`dsb` 把刚存的行逐出，reload 走 L1D 阵列/更远。

| 测试用例 | 源码 | fail | 时长 | 数据来源 |
|---|---|---|---|---|
| mrn_rmw_l1d | `tests/cpu/misc/mrn_rmw_fwd_vs_l1d.cpp` | 0 | 30min | 8-31 持久日志 |
| mrn_rmw_diff_nop64 | `tests/cpu/misc/mrn_rmw_diff_timing_probe.cpp` | 0 | 30min | 8-31 持久日志 |

→ **dc civac 逐出后走 L1D 阵列：8-31 复测 30min 均 0 fail。**

### 1.3 L1D 分析的结果（以新数据为准）

**绕过 L1D 和不绕过 L1D 都触发了 SDC：**
- 绕过 L1D 阵列读（store-buffer forwarding）：mrn_rmw_nop/nop1/nop4/dump + movbe_dump_golden/probe_xn 全触发（61 fail）
- 不绕过（走 L1D 阵列读，异址）：mrn_rmw_diff/diff_64k 触发（27 fail）

→ **两条路径都触发。缺陷不在某一条路径独有。** forwarding 与 L1D 阵列读在"load port → 寄存器"这一段汇合，两条都错说明问题在这一共同下游段，不是单一路径独有。

**细分边界（如实）：** 同为"走 L1D 阵列读"，异址的 mrn_rmw_diff 触发（8/19 fail），但同址+dc civac 逐出的 mrn_rmw_l1d 8-31 复测 30min 为 0 fail、异址+64nop 的 mrn_rmw_diff_nop64 也 0 fail。说明"走 L1D 阵列读"这个粗分类下，触发与否还取决于更细的变量（逐出方式、地址驻留状态、str→ldr 间隔、footprint 大小）。8-31 的这两个 0 fail 是当前可追溯的，但只各跑 30min，不能反证"绝不触发"。

---

## 第二部分：如何定位 sub/xor 嫌疑指令

### 2.1 测试用例名称

**`mrn_rmw_dump`**（源码：`tests/cpu/misc/mrn_rmw_dump.cpp`）

### 2.2 方法：冷分支重算（recompute）

**热循环**（4 指令混合的 RMW + forwarding）：
```
for (i = 0; i < 1024; i++) {
    a = srcA[i]; b = srcB[i];
    switch (i % 4) { case0:a+b  case1:a-b  case2:a^b  case3:a&b }   // add/sub/xor/and 四种
    str res, temp[i];          // ALU 结果存 temp
    dst[i] = ldr temp[i];      // store-reload forwarding
}
// 冷分支: memcmp(dst, expected) 失败则定位并 dump
```

**要解决的问题**：失败时只记录 `temp[i]`（store 后）和 `dst[i]`（forwarding 后）。`temp==dst` 只能证明 forwarding 忠实，但分不开：ALU 算错了 store 忠实写入错值；还是 ALU 算对了 store 写错。

**recompute 方法**（修复，在冷分支）：用同一份 `inputA/inputB` 重算一次 ALU 结果，与热循环存入 temp 的值比较：
```
// 冷分支,失败才执行,不碰热循环
switch (i % 4) {
    case 0: res_recompute = inputA + inputB; break;
    case 1: res_recompute = inputA - inputB; break;   // sub
    case 2: res_recompute = inputA ^ inputB; break;   // xor
    default: res_recompute = inputA & inputB; break;
}
```

**判据**（三值两两比较）：

| 比较 | 结果 | 含义 |
|---|---|---|
| golden == recompute | 相等 | init 预存的正确值（核0算）与冷分支重算（179）一致 → 正确值确定 |
| temp != recompute | 不等 | 热循环那次 ALU 算的 ≠ 冷分支重算 → **热循环那次 ALU 算错了** |
| temp == dst | 相等 | store→load forwarding 忠实传了错值 → forwarding 正常 |

verdict 字段编码：bit0 = `temp==recompute`（store faithful），bit1 = `temp==dst`（fwd faithful）。文本标注 `[ALU-COMPUTE-WRONG]`/`[store-faithful]` + `[fwd-faithful]`/`[fwd-damaged]`。

### 2.3 实验结果（2026-08-30，全核192含179，auto seed，可追溯 yaml）

抓到 **3 条 recompute 分类样本，全是 op=sub，verdict 全是 `[ALU-COMPUTE-WRONG][fwd-faithful]`**：

| 来源 | idx | op | golden | recompute（冷分支） | temp/dst（热循环） | verdict |
|---|---|---|---|---|---|---|
| 1h 战役 | 825 | sub | 0xA741FB701E3DF854 | 0xA741FB701E3DF854 | 0xD6DD0F23D401BAAE | ALU-COMPUTE-WRONG, fwd-faithful |
| 1h 战役 | 897 | sub | 0xBC30434FD396E4BB | 0xBC30434FD396E4BB | 0x57AD41390703CDCB | ALU-COMPUTE-WRONG, fwd-faithful |
| 10min 样本 | 817 | sub | 0x7161F4A609D7272E | 0x7161F4A609D7272E | 0x979F4D2A35128AD1 | ALU-COMPUTE-WRONG, fwd-faithful |

来源 yaml：`opendcdiag-20260830T061555.854117Z.yaml`（mrn_rmw_dump 1h，2 条）+ 10min 旧样本。

每条都是：`golden == recompute`（正确值确定）+ `temp != recompute`（热循环那次算错）+ `temp == dst`（forwarding 忠实）。

### 2.4 结论与边界

- recompute 版本抓到的 3 条分类样本里，**算错的指令全是 sub（a−b）**，verdict 都是 `ALU-COMPUTE-WRONG`：热循环那次 sub 算错了，store/forwarding 忠实传错值。错误发生在 ALU 执行/写回寄存器阶段。
- **xor 的证据更弱**：更早的一批样本（无 recompute）记录"9 条全 xor"，但那批没有 recompute 分类，分不开 ALU 算错还是 store 错。recompute 版本未抓到带分类的 xor 样本。
- **"锁定 sub/xor 指令有硬件故障"措辞收窄为**：recompute 证明"热循环那次 sub 算错了"，样本 3 条全 sub，但样本量小、且算错也可能源于 ALU 的输入 load 路径错而非执行单元本身。不能由这 3 条断言"sub 指令有硬件故障"。

---

## 第三部分：单指令压力测试（2026-08-31，负向结果）

### 3.1 测试用例
- `tests/cpu/misc/stress_sub.cpp` — 热循环纯 `sub`，测试名 `stress_sub`
- `tests/cpu/misc/stress_xor.cpp` — 热循环纯 `eor`（xor），测试名 `stress_xor`
- `tests/cpu/misc/stress_fma.cpp` — 热循环纯 `fmadd`，测试名 `stress_fma`

布局同 mrn_rmw_dump，但每个测试热循环只用一种纯指令。inline asm：整数用 `"=&r"`，fmadd 用 `"=&w"`+`%d0` 修饰符。objdump 确认热循环核心各只有一条目标指令。

### 3.2 结果（两阶段验证，nproc=192）
- 阶段1（排除179，60s）：三个全 0 fail（用例可靠不误报）。
- 阶段2（全核192含179，各5min）：stress_sub 0 fail、stress_xor 0 fail、stress_fma 0 fail。**三个单指令 5min 均未触发。**

### 3.3 边界
单指令 5min 0 fail 不反证"单指令不触发"——对照 mrn_rmw_dump 1h 才 2 fail（约0.033/min），5min 期望触发次数 < 0.2。要证否需各 1h+。

---

## 第四部分：当前可追溯证据强度总表

| 实验 | 测试用例 | 方法 | 结果（可追溯） | 说明 |
|---|---|---|---|---|
| forwarding 路径 | mrn_rmw_nop/nop1/nop4/dump | 同址 str→ldr | 触发（11/1/1/2 fail） | 绕过 L1D 阵列读 |
| forwarding 路径 | movbe_dump_golden/probe_xn | 同址 str→ldr | 触发（45/1 fail） | 绕过 L1D 阵列读 |
| L1D 阵列读路径 | mrn_rmw_diff / diff_64k | 异址必走阵列 | 触发（8/19 fail） | 不绕过 L1D |
| dc civac 逐出后 | mrn_rmw_l1d / diff_nop64 | 逐出走阵列 | 0 fail/30min（8-31） | 粗分类下不触发 |
| ALU vs store 分离 | mrn_rmw_dump | 冷分支 recompute | 3 条全 sub, ALU-COMPUTE-WRONG | 热循环 sub 算错 |
| 单指令压测 | stress_sub/xor/fma | 纯单指令 | 3×5min 全 0 fail | 未触发（不反证） |

**核心结论（当前数据）**：绕过 L1D 和不绕过 L1D 都触发 SDC → 缺陷不在某一条路径独有，在共同下游（load port → 寄存器）。

**未决（如实）**：
1. 同为"走 L1D 阵列读"，diff 触发但 l1d/diff_nop64（8-31）0 fail，细分变量未定。
2. recompute 只证明"sub 算错"3 条，样本量小，"sub 指令硬件故障"未证明；单指令压测 5min 未触发但不反证。

---

## 附录：无可追溯 yaml 的老测试（不参与以上结论）

以下测试在当前机器无可追溯 yaml，只有 V3–V6 报告文字记载。**本报告结论不依赖这些数据**，仅列出供参考：

- `movbe_l1d`（`movbe_l1d_vs_l2.cpp`）：V5 报告记 3min/17 fail（L1D 路径）。
- `movbe_l2`（同文件）：V5 报告记 30min/0 fail（evict 走 L2/L3）。
- `mrn_rmw_fwd`（`mrn_rmw_fwd_vs_l1d.cpp`）：V6 报告记触发（forwarding 基线）。

> 注：上一版文档曾引用这些老数据 + V5 §V5.3"方法论天花板"给 L1D 结论留尾巴，与当前可追溯实测"两条路径都触发"矛盾。本版以当前可追溯数据为准，删除该依赖老数据的留尾巴表述。如需让这些测试也产生可追溯 yaml，可重跑（测试在二进制内可用 `-e` 调起）。
