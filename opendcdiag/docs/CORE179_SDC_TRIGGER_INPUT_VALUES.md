# CORE179 SDC：触发 SDC 的输入值记录

> 日期：2026-09-01
> 目的：专门记录触发 179 核 SDC 的**输入数据值**（input/golden/actual/xor），用于分析"什么样的输入值会触发"以及"是否有固定输入模式"。
> 数据来源：movbe_dump / mrn_rmw_dump 变体（dump-on-failure，在冷分支 log_error 打印 input/golden/actual/xor）全核 192 含 179 + auto seed 实跑。
> **这是单独的输入值文档，与指令序列分析分开。**

---

## 一、movbe_dump 触发的输入值（5 轮独立 auto-seed，42 条样本）

> 跑测：5 轮独立 run，每轮 `movbe_dump -n 192 -T 5m --ignore-os-error --ignore-timeout`，全核含 179 + auto seed（每轮生成全新随机 input 数组）。
> 记录格式：input = `data->input[index]`（random32 生成）；golden = `bswap(bswap(input)) = input`（理论应恢复原值）；actual = 第二次 ldr 读 input 后的值；xor = input ^ actual；翻转位数 = xor 中 1 的个数。
> **样本独立性**：5 轮各自独立 auto-seed，input 数组互不相同，构成跨独立数组的样本集（修正同-run 非独立采样硬伤）。

| # | 轮次 | index | input | actual | xor | 翻转位数 |
|---|---|---|---|---|---|---|
| 1 | R1 | 12734 | 0xBDA47585 | 0xD6DD8156 | 0x6B79F4D3 | 20 |
| 2 | R1 | 9423 | 0x1479E68F | 0x5E821972 | 0x4AFBFFFD | 25 |
| 3 | R1 | 4413 | 0x6669F19B | 0xA21EBE39 | 0xC4774FA2 | 17 |
| 4 | R1 | 11567 | 0xEACBB241 | 0xFA69FC77 | 0x10A24E36 | 12 |
| 5 | R1 | 10698 | 0xB475D50B | 0x4CD5D946 | 0xF8A00C4D | 13 |
| 6 | R1 | 10551 | 0x555225B5 | 0x904A9353 | 0xC518B6E6 | 16 |
| 7 | R1 | 15824 | 0xEC9EA70B | 0x09E1DEB4 | 0xE57F79BF | 24 |
| 8 | R1 | 13629 | 0x96A8FC6C | 0xFEE7729B | 0x684F8EF7 | 19 |
| 9 | R1 | 8479 | 0x89E7F67D | 0x9C9B1234 | 0x157CE449 | 15 |
| 10 | R1 | 4454 | 0x4753AEE0 | 0xC6876A61 | 0x81D4C481 | 11 |
| 11 | R1 | 13255 | 0x7F1C4929 | 0xCF57E721 | 0xB04BAE08 | 13 |
| 12 | R2 | 5423 | 0x57023EE7 | 0x4037B9E6 | 0x17358701 | 13 |
| 13 | R2 | 15854 | 0x0F43567B | 0x8481D932 | 0x8BC28F49 | 15 |
| 14 | R2 | 11725 | 0x686C70FC | 0x63B34952 | 0x0BDF39AE | 19 |
| 15 | R2 | 13912 | 0xCEC20D8D | 0x590DFA05 | 0x97CFF788 | 20 |
| 16 | R2 | 7698 | 0x8F11586E | 0xBCAE1AB7 | 0x33BF42D9 | 18 |
| 17 | R2 | 9565 | 0x66492B66 | 0x45EAC9ED | 0x23A3E28B | 15 |
| 18 | R2 | 11768 | 0x22F984A6 | 0xCEAE7FF1 | 0xEC57FB57 | 22 |
| 19 | R2 | 14521 | 0x3667D577 | 0xF25F8B0B | 0xC4385E7C | 16 |
| 20 | R2 | 13592 | 0xF820CF15 | 0xEB4CB02D | 0x136C7F38 | 17 |
| 21 | R2 | 16370 | 0x7180715F | 0x9A936DED | 0xEB131CB2 | 16 |
| 22 | R2 | 12697 | 0x1A45E96F | 0x16C89D2E | 0x0C8D7441 | 12 |
| 23 | R3 | 11567 | 0x17BD8352 | 0x9AA6A5D8 | 0x8D1B268A | 14 |
| 24 | R3 | 13828 | 0xBA0A45A5 | 0x2CC6A2B0 | 0x96CCE715 | 17 |
| 25 | R3 | 11191 | 0xC451110B | 0xE0C7BDAA | 0x2496ACA1 | 13 |
| 26 | R3 | 11577 | 0x8E7529B0 | 0x615C458A | 0xEF296C3A | 18 |
| 27 | R3 | 12764 | 0xC682EF9E | 0xFF1FFEF5 | 0x399D116B | 16 |
| 28 | R3 | 11396 | 0x70B4A5FF | 0xB65FAE1E | 0xC6EB0BE1 | 17 |
| 29 | R3 | 11644 | 0xF8ADD912 | 0x8BD5CF6F | 0x7378167D | 18 |
| 30 | R3 | 4954 | 0xDCECD6D4 | 0x69B79E58 | 0xB55B488C | 15 |
| 31 | R3 | 14708 | 0x3F4EF569 | 0x43E0D7E4 | 0x7CAE228D | 16 |
| 32 | R3 | 9593 | 0x603D5C68 | 0x8DA341BF | 0xED9E1DD7 | 21 |
| 33 | R3 | 14409 | 0x47F6D99E | 0x1CAA9802 | 0x5B5C419C | 15 |
| 34 | R3 | 9348 | 0x65B78B38 | 0x0F993B46 | 0x6A2EB07E | 17 |
| 35 | R3 | 9538 | 0xAB90A689 | 0xE13FCE74 | 0x4AAF68FD | 19 |
| 36 | R3 | 11600 | 0x015840E1 | 0x8BD5CF6F | 0x8A8D8F8E | 16 |
| 37 | R4 | 15892 | 0xC9BF64CE | 0x9D94CE7A | 0x542BAAB4 | 15 |
| 38 | R4 | 6461 | 0xF56CEAC7 | 0x6AB68C1C | 0x9FDA66DB | 21 |
| 39 | R4 | 7910 | 0x245DEB0A | 0xD7966E3E | 0xF3CB8534 | 17 |
| 40 | R4 | 8515 | 0xFAABD2ED | 0xA39292C9 | 0x59394024 | 11 |
| 41 | R5 | 10304 | 0x6DA2FEA0 | 0x63DD5006 | 0x0E7FAEA6 | 19 |
| 42 | R5 | 9412 | 0xC0651956 | 0x348B2BA8 | 0xF4EE32FE | 21 |

### movbe 输入值分析

**关键现象 1：golden == input（全部 42 条）**
每次 `bswap(bswap(input))` 理论恢复 = input，golden 确实 = input。说明第一次 ldr 读 input 是正确的，**第一次读无误**。

**关键现象 2：actual ≠ input（全部 42 条），翻转在第二次 ldr**
actual 是第二次 ldr 读同一 input 地址的结果，它 ≠ input。**翻转发生在第二次 ldr 重读**，印证 `isolated-recross-golden-protocol`（movbe 真实错在两次 ldr 读同址不一致）。

**关键现象 3：翻转位分布散乱（11-25 位翻转，无固定模式）**
- 翻转位数从 11 位到 25 位，跨度大，平均 ~16.8 位
- 不是单 bit 软错误，也不是固定位硬件坏——**是 L1D 读路径的多位随机错**

**关键现象 4：input 值本身无共性（用户核心问题，见第三章独立分析）**
42 条 input 值跨 5 个独立数组，各值无共同位模式。**输入值不决定触发**——见第三章逐 bit constant 分析的干净否定。

**关键现象 5：index 分布（4413-16370）**
input 数组 16384 元素，fail 的 index 分布在 4413~16370，无聚集。**index 不决定触发**（不是 cache 行边界或特定偏移）。

### movbe 翻转位统计（42 条跨 5 轮独立样本）

| 统计项 | 值 |
|---|---|
| 翻转位数范围 | 11-25 位 |
| 平均翻转位数 | 16.8 位 |
| 最频繁翻转位 | bit19（32/42 次） |
| 最少翻转位 | bit8（16/42） |
| 固定坏位 | 无（所有 bit 都有时不翻，无必翻位） |

各 bit 翻转次数分布（42 条中）：
```
bit0:22  bit1:19  bit2:23  bit3:24  bit4:21  bit5:22  bit6:19  bit7:25
bit8:16  bit9:24  bit10:27 bit11:22 bit12:16 bit13:23 bit14:21 bit15:19
bit16:25 bit17:26 bit18:23 bit19:32 bit20:23 bit21:22 bit22:22 bit23:21
bit24:23 bit25:21 bit26:21 bit27:21 bit28:19 bit29:19 bit30:22 bit31:21
```
分布 16~32，无聚集——**不是固定位硬件坏，是读路径多位随机错**。

### movbe 触发机制小结
- **输入值无关**：input 是随机值（0x0158~0xFAAB 各字节无共同模式），任何值都可能触发，输入值不挑食
- **触发由时序决定**：两次 ldr 同址读的时序窗口命中 179 的 marginal 窗口时触发
- **翻转随机多位**：平均 16.8 位翻转，各 bit 翻转 16-32 次无固定坏位，是读路径随机错非固定位坏
- **可稳定触发的指令序列**：`ldr w1,[input,i]; rev; str w4,[swapped,i]; ldr w4,[input,i]; cmp w4,w1`（两次同址 ldr + 中间 ALU/store）
- **可稳定触发的输入**：任意随机 32 位值（覆盖率 ~1.9 fail/min，input 值不决定触发，由时序窗口决定）

---

## 二、mrn_rmw_dump 触发的输入值（2 条样本，64 位）

> 跑测：`mrn_rmw_dump -n 192 -T 30m --ignore-os-error --ignore-timeout`，全核含 179 + auto seed，test-runtime 1020s 抓 2 fail。
> 记录格式：inputA, inputB（两个 64 位输入），op（操作类型），golden（inputA op inputB 理论值），actual（dst=store 后重载值），recompute（用 inputA/B 重算），xor，verdict（[ALU-COMPUTE-WRONG]=ALU 算错 / [fwd-faithful]=forwarding 忠实）。

| # | index | op | inputA | inputB | golden | actual | recompute | xor | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 297 | sub | 0x2431DE6588CF64CB | 0xF4F76C5BB69358AB | 0x2F3A7209D23C0C20 | 0xB25524D2AE393ACB | 0x2F3A7209D23C0C20 | 0x9D6F56DB7C0536EB | ALU sub 算错，fwd 忠实 |
| 2 | 606 | xor | 0x19FAC120674F1949 | 0x7271BAC9F78A194F | 0x6B8B7BE990C50006 | 0x92A7BEDA4A241ACB | 0x6B8B7BE990C50006 | 0xF92CC533DAE11ACD | ALU xor 算错，fwd 忠实 |

### mrn_rmw 输入值分析

**关键现象：recompute == golden ≠ actual（2/2 条）**
- golden 是 inputA op inputB 的理论值；recompute 是用 inputA/B 重算的结果。两者**相等**，说明用同样的输入重算能得到正确值。
- actual（store 后 forwarding 重载值）**≠** golden/recompute，且 temp == dst（forwarding 链忠实）。
- **结论：mrn_rmw 的 SDC 源在 ALU 计算（sub/xor 算错），不在 store/forwarding**。这与 movbe（第二次 ldr 读错）是**不同的触发机制**——印证"两族独立"。

**样本量不足警告**：mrn_rmw 仅 2 条样本（率 ~0.2/min + dump 冷分支降率），**无法做 bit 统计**。需更长时跑测或更密集采样才能分析 inputA/B 的 bit 模式。

---

## 三、"触发 SDC 的 input 是否有固定 bit"分析（用户核心问题）

> 问题：触发 SDC 的 input 值，是否存在某 1 个或几个 bit 固定为 0 或 1？
> 方法：跨 **5 轮独立 auto-seed run**（每轮生成新的随机 input 数组）采样 42 条触发 input，做 (a) 单 bit constant、(b) bit 对恒同值/恒反值、(c) 字节级分布分析。

### 采样设计（修正同-run 非独立采样的方法论硬伤）

初次 15 条 movbe input 来自**同一次 run、同一个 16384 元素随机数组、同一个 seed**，不是独立采样，不能干净做 bit 统计。为干净回答用户问题，跑 5 轮独立 auto-seed run（auto seed 走 random_device 真随机，每轮生成全新 input 数组）：
- Round 1: 11 条样本
- Round 2: 11 条样本
- Round 3: 14 条样本
- Round 4: 4 条样本
- Round 5: 2 条样本
- **合计 42 条跨 5 个独立数组的样本**

### 结果（N=42，均匀期望 ~21，std~3.24）

| 分析维度 | 结果 |
|---|---|
| 单 bit constant（某 bit 在 42 条里恒 0 或恒 1） | **无**（所有 bit ones 计数 17~27，无 0 无 42） |
| 单 bit 最极端显著性 | bit14=27/42, p=0.088，**未达 Bonferroni 阈值 0.00156** |
| bit 对 constant（bitX^bitY 恒定） | **无**（0 对） |
| 字节级唯一值数 | byte0=39/42, byte1=40/42, byte2=40/42, byte3=39/42（高度分散） |

各 bit 的 ones 计数（N=42，均匀期望 ~21，std~3.24）：
```
bit0:24  bit1:22  bit2:24  bit3:24  bit4:17  bit5:22  bit6:22  bit7:21
bit8:24  bit9:18  bit10:23 bit11:19 bit12:21 bit13:23 bit14:27 bit15:25
bit16:22 bit17:17 bit18:21 bit19:20 bit20:19 bit21:23 bit22:23 bit23:19
bit24:18 bit25:21 bit26:26 bit27:20 bit28:19 bit29:23 bit30:25 bit31:20
```
分布 17~27，相对均匀，无聚集，无 constant。

### 结论

**触发 SDC 的 input 值没有任何 bit 固定为 0 或 1，也没有任何几个 bit 的组合恒定。** 跨 5 轮独立 auto-seed 数组的 42 条样本干净否定了"存在 constant bit 触发条件"的假设。**input 值不是触发开关——任意随机 32 位值都可能触发，触发不由 input 的具体值决定，而由指令序列的时序窗口（何时第二次 ldr 读同一地址）命中 179 的 marginal 窗口决定。**

## 四、结论：什么是"可稳定触发 SDC 的输入值"

**输入值本身不是触发开关——movbe/mrn_rmw 的 input 都是 `memset_random` 随机值，每次跑 seed 不同，input 值不同，但都能触发。**

"可稳定触发"依赖的不是某个特定输入值，而是**指令序列**：
- **movbe 族**：`ldr → ALU(rev) → str(异址) → ldr(同址重读) → cmp`（两次同址 ldr，中间隔 ALU+store），触发在**第二次 ldr 读错**
- **mrn_rmw 族**：`ldr srcA → ldr srcB → ALU(sub/xor) → str temp → ldr temp(forwarding重载) → str dst`，触发在**ALU 算错**（recompute==golden≠actual，fwd 忠实）

**两族触发机制不同**：movbe 是读路径错（L1D 同址重读不一致），mrn_rmw 是 ALU 算错。input 值用任意随机值即可触发（覆盖率由时序窗口决定，~1.9/min for movbe, ~0.2/min for mrn_rmw）。

---

## 五、可追溯产物

- `movbe_log/sdc_input_samples/movbe_dump_5min.log`（45 fail 文本日志，含完整 input/actual/xor，提取 15 条）
- `movbe_log/sdc_input_samples/mrn_rmw_dump_30min.log`（2 fail 文本日志，含 inputA/B/golden/actual/recompute/xor）
- `/tmp/movbe_dump_*.bin`（二进制日志，write 未落盘全 0 字节——以文本日志为准）
- `parse_movbe_dump.py`（二进制日志解析脚本，因 .bin 为空未实际使用，文本日志直接提取）
