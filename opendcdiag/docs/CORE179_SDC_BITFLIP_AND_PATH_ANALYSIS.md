# CORE179 SDC：bit 翻转、触发频率与路径分析记录

> 日期：2026-08-31
> 范围：对 2026-08-30 战役幸存的 88 条 fail 记录，逐项分析 bit 翻转形态、触发频率、触发路径，回答"绕过 L1D 和不绕过 L1D 是否都出现 fail"。
> 数据来源：仓库幸存 yaml（`opendcdiag-20260830T*.yaml`），全核 192 含 179，auto seed。
> 注：客观事实记录，不含推理。

---

## 一、总量与频率

### 1.1 战役期间（2026-08-30，全核192含179，auto seed）

| 测试用例 | reload 走的路径 | fail块数 | 时长min | 频率 fail/min |
|---|---|---|---|---|
| mrn_rmw_dump | forwarding（带 recompute） | 2 | 60 | 0.033 |
| movbe_dump_golden | movbe 字节交换往返 | 45 | 30 | 1.500 |
| movbe_dump_probe_xn | movbe 字节交换往返 | 1 | 30 | 0.033 |
| mrn_rmw_diff | L1D 阵列读（异址） | 8 | 30 | 0.267 |
| mrn_rmw_nop | forwarding（2 nop） | 11 | 30 | 0.367 |
| mrn_rmw_nop1 | forwarding（1 nop） | 1 | 30 | 0.033 |
| mrn_rmw_nop4 | forwarding（4 nop） | 1 | 30 | 0.033 |
| mrn_rmw_diff_64k | L1D 阵列读（异址+64K足迹） | 19 | ~8* | 2.375 |

*mrn_rmw_diff_64k 只跑约 8min 被重启中断，2.375/min 是瞬时率，不与 30min 的直接对比。

合计 **88 条 fail 记录**（mrn_rmw 42 + movbe 46）。

### 1.2 补跑结果（2026-08-31，同参数）

| 测试用例 | 路径 | 时长 | fail |
|---|---|---|---|
| mrn_rmw_l1d | L1D 阵列读（同址+dc civac 逐出） | 30min | 0 |
| mrn_rmw_diff_nop64 | L1D 阵列读（异址+64nop） | 30min | 0 |
| mrn_rmw_nop8 | forwarding | ~30min | 待整理（8-31 跑过，被停） |

---

## 二、关键结论：两条路径都出现 fail

直接对照"绕过 L1D 阵列读（走 store-buffer forwarding）"与"不绕过（走 L1D 阵列读）"：

| 路径 | 测试用例 | fail |
|---|---|---|
| 绕过 L1D 阵列读（store-buffer forwarding） | mrn_rmw_nop / nop1 / nop4 / dump | 15（11+1+1+2） |
| 不绕过（走 L1D 阵列读） | mrn_rmw_diff / diff_64k | 27（8+19） |

**绕过 L1D 和不绕过 L1D 都出现了 fail。**

边界（如实记录）：同为"走 L1D 阵列读"的路径，mrn_rmw_diff 触发（8/19 fail），但 mrn_rmw_l1d（同址+dc civac 强制走阵列）8-31 复测 30min 为 0 fail。说明"走不走 L1D 阵列"这个粗分类会把机理不同的路径混为一谈，触发与否取决于更细的变量（逐出 vs 常驻、间隔长短、足迹大小）。

---

## 三、bit 翻转形态分析

### 3.1 popcount（翻转位数）统计

| 测试 | 位宽 | 样本数 | popcount 最小 | 最大 | 平均 |
|---|---|---|---|---|---|
| mrn_rmw_dump | 64 | 2 | 31 | 33 | 32.0 |
| mrn_rmw_diff | 64 | 8 | 29 | 40 | 35.0 |
| mrn_rmw_nop | 64 | 11 | 25 | 36 | 30.9 |
| mrn_rmw_diff_64k | 64 | 19 | 26 | 42 | 32.4 |
| mrn_rmw_nop1 | 64 | 1 | 14 | 14 | 14.0 |
| mrn_rmw_nop4 | 64 | 1 | 37 | 37 | 37.0 |
| movbe_dump_golden | 32 | 45 | 11 | 23 | 16.0 |
| movbe_dump_probe_xn | 32 | 1 | 14 | 14 | 14.0 |

### 3.2 翻转特征

- **64-bit mrn_rmw 系列**：翻转 25–42 位，平均约 32 位（64 位的一半）。是大范围多位错，不是单 bit 翻转。
- **32-bit movbe 系列**：翻转 11–23 位，平均 16 位（32 位的一半）。同样是大范围多位错。
- **bit 位分布近均匀**：
  - 64-bit 热力图：翻转最频繁的 bit（52/34/18 位各 27-28 次）与最少 bit（42/7 位各 14-15 次）差异不大，无固定热点位、无单一"坏 bit"。
  - 32-bit movbe：最少 12 次、最多 31 次，也接近均匀。
- **不是单点 bit 损坏**：没有某个 bit 位独占翻转，呈随机性多位翻转形态。

### 3.3 与 eigen 的对照（历史记录）

eigen（FMA GEMM）的 fail 特征不同（来自 `docs/CORE179_SDC_REPORT_CN.md` 历史记录）：
- 翻转集中在 IEEE-754 **尾数位**（85-93% 在 mantissa，符号位免疫）
- SVD 路径单 bit，GEMM 路径多 bit（1-24 bit）
- 与本战役的 mrn_rmw（25-42 位近均匀）/ movbe（11-23 位近均匀）形态不同

---

## 四、op（算术运算）分布

mrn_rmw 系列的 42 条（排除 movbe 的 46 条非算术翻转）：

| op | 条数 |
|---|---|
| sub（减法） | 24 |
| xor（异或） | 13 |
| and（与） | 3 |
| add（加法） | 2 |

- **sub 触发最多（24 条），其次是 xor（13 条）**
- sub/xor/and/add 都中招，不是某一种运算专属
- 其中 mrn_rmw_diff 的 8 条 op 分布：sub 5 + xor 3（无 add/and）

---

## 五、forwarding 路径 vs L1D 阵列读路径的错机理

### 5.1 forwarding 路径的错（mrn_rmw_dump，带 recompute）

2 条样本有 recompute 分类（详见 `docs/CORE179_SDC_L1D_EXCLUSION_AND_INSTRUCTION_LOCALIZATION.md` 第二部分）：
- idx 825, op=sub：golden=0xA741FB701E3DF854，actual=0xD6DD0F23D401BAAE，翻转 33 位。`[ALU-COMPUTE-WRONG]`
- idx 897, op=sub：golden=0xBC30434FD396E4BB，actual=0x57AD41390703CDCB，翻转 31 位。`[ALU-COMPUTE-WRONG]`

两条都是 `golden==recompute`（正确值确定）+ `temp!=recompute`（热循环 sub 算错）+ `temp==dst`（forwarding 忠实）。
→ forwarding 路径的这 2 条，错在 ALU 算错，forwarding 忠实传错值。

### 5.2 L1D 阵列读路径的错（mrn_rmw_diff，无 recompute）

mrn_rmw_diff 的 8 条无 recompute 分类，但源码决定它只能查 load（`mrn_rmw_fwd_vs_diff.cpp:129`：`if (got != expected)`，其中 `got=ldr(tempB)`，ALU 的 res 不参与比较）。
→ 这 8 条 100% 是 ldr(tempB) 读出错，即 L1D 阵列读路径的 load 读出错，与 ALU 无关。
- popcount 29-40 位，平均 35 位
- op 分布：sub 5 + xor 3

### 5.3 两条路径错机理不同

| | forwarding 路径的错 | L1D 阵列读路径的错 |
|---|---|---|
| 代表测试 | mrn_rmw_dump（带 recompute） | mrn_rmw_diff |
| 归因 | ALU 算错（sub），forwarding 忠实 | ldr 读出错，与 ALU 无关 |
| 证据 | temp!=recompute | got=ldr(tempB)!=expected，res 不参与 |
| popcount | 31-33 | 29-40 |

两条路径的错机理不同。是否存在更上游共同根因未明。

---

## 六、数据源可信度

- **可信（有幸存 yaml）**：88 条全部来自 `opendcdiag-20260830T*.yaml`，yaml 头部 command-line 与战役脚本参数匹配，mtime 在战役窗口内。
- **补跑可信（有持久日志）**：mrn_rmw_l1d(0)、mrn_rmw_diff_nop64(0) 来自 `movbe_log/campaign_resume/`。
- **统计方法**：fail 块数用"唯一 result:fail 块"统计（python 按 `- test:` 切块，块内含 result:fail 计 1），避免 grep miscompare 双计（每 fail = 2 行 miscompare，grep 会虚高 2 倍）。
