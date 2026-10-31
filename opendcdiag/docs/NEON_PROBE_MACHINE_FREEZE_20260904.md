# NEON 探针机器硬冻结调查报告（2026-09-04 上午）

> 事件：`run_probe_trio.sh`（§5.5 拆分三探针战役）导致机器**硬卡死 3 次**，均需人工重启。
> 性质判定：**与 core-179 SDC 是不同的失效模式** —— 整机静默锁死 vs 数据错；且三次冻结均发生在
> 阶段1（191 线程，**179 核已被排除**），179 根本不在场。
> 状态：战役已暂停，`neon_rot_nop_gap`（第三探针）从未跑到。

---

## 1. 三次冻结时间线（IPMI SEL + 日志交叉确认）

| 次 | SEL 记录的重启时刻 | 冻结时的测试 | 冻结时进度 | 对应日志 |
|---|---|---|---|---|
| 1 | 09:18:41 | `neon_rot_stale_reload` **stage1** (60s) | 第 37 轮，约 41s/60s | `neon_rot_stale_reload_stage1_no179.DEAD_0914.log`（最后写入 09:14:56） |
| 2 | 10:32:17 | `neon_rot_ldr_at_top` **stage1** (60s) | 第 7 轮，约 8s | `neon_rot_ldr_at_top_stage1_no179.DEAD_1027.log`（最后写入 10:27:14） |
| 3 | 11:05:43 | `neon_rot_ldr_at_top` **stage1** 重跑 | 第 2 轮，约 3s | `neon_rot_ldr_at_top_stage1_no179.log`（最后写入 10:59:15） |

SEL 原始记录（`ipmitool sel list`，三次冻结均只有干净的 System Restart，**无任何 MCE / 硬件错误**）：

```
4e6 | 09/04/2026 | 09:18:41 | System Boot Initiated #0x81 | System Restart | Asserted
4e9 | 09/04/2026 | 10:32:17 | System Boot Initiated #0x81 | System Restart | Asserted
4ec | 09/04/2026 | 11:05:43 | System Boot Initiated #0x81 | System Restart | Asserted
```

（SEL 时刻 = BMC 发现系统重启的时刻，比冻结发生时刻晚约 1-3 分钟，与 `.DEAD_` 日志最后写入时间吻合。）

## 2. 证据链清单

- **冻结判定依据**：
  - `last -x reboot`：09:21 / 10:35 / 11:08 三次重启（内核启动时刻）。
  - 两个 `.DEAD_` 标记日志的最后写入时间（09:14、10:27）正对前两次冻结。
  - 第三次冻结对应 11:00 左右重跑的 `neon_rot_ldr_at_top_stage1_no179.log`，停在第 2 轮
    （`grep -c "Loop iteration"` = 2，最后一条 `time-at-start elapsed: 2676ms`）。
- **静默锁死、OS 层面零捕获**：
  - journal 对冻结的 boot 无任何记录（硬锁死时内核连日志都写不出，`journalctl --list-boots` 只剩当前 boot）。
  - pstore 为空（`/sys/fs/pstore/` 无文件）。
  - crashkernel=1024M 已在内核 cmdline 中，但**没有产出 vmcore** —— kdump 服务本身未验证配置。
  - IPMI SEL 无 MCE / 无 CPU / 内存 / 电源类事件。
- **战役脚本**：`run_probe_trio.sh`，阶段1命令为
  `taskset -c 0-178,180-191 $BIN -e $NAME -n 191 -T 60s --ignore-os-error --ignore-timeout -o $LOG -q`
  —— 179 已被排除。阶段2（全核 192 含 179，30min）在三次冻结中**一次都没跑到**。
- **对照组**：昨夜至今晨（09-03 22:35 → 09-04 08:00）同骨架 6 个测试
  （`store_only` / `u8x16` / `1src` / `2src` / `u32x4` / `fwd_probe`）
  各自完成 stage1 + stage2 全核 30min，**无一冻结**。
- 另：09-03 18:34 / 18:41 SEL 还有 2 次重启（在战役开始之前），来历未查（见 §7）。

## 3. 嫌疑排序

1. **`neon_rot_ldr_at_top`（主嫌疑）**：连续两次秒级冻结（第 7 轮、第 2 轮），一次比一次快。
2. **`neon_rot_stale_reload`（次嫌疑）**：第一次冻在第 37 轮；但后来重跑一次完整通过
   （stage1 60s 0fail + stage2 30min 0fail，`RESULTS.txt` 有记录）——
   概率性触发，或第一次冻结另有原因，目前无法区分。
3. `neon_rot_nop_gap`：从未执行，无数据。

## 4. 两个探针的负载与代码

两者都是 NEON 64-bit lane 版配方（`uint64x2_t`，2 源 load + add/eor/and/orr 按 `i%4` 轮换，
1024 元素 × 8192 轮 TEST_LOOP），但各自引入了一个**此前所有测试（含触发组与不触发组）都没出现过的
微架构访问模式**。

### 4.1 `neon_rot_stale_reload`（`tests/cpu/misc/neon_rot_stale_reload.cpp`）

热循环核心（单 asm 块固定顺序，`neon_rot_stale_reload.cpp:117-123`）：

```asm
str %q1, [%2]   // str temp[i] = res        （与 baseline 相同）
ldr %q0, [%3]   // ldr temp[i-1]            ← 唯一变量：读"前一个"元素
str %q0, [%4]   // str dst[i] = loaded      （吃掉 ldr 输出，保 4 步依赖链）
```

- 设计意图：load 与其匹配 store 的时间距离从背靠背拉开到 ~6 条指令，同址性质改为
  "同 cache line 不同字"（`i%4 != 0` 时 `temp[i-1]` 与 `temp[i]` 同 line）。
- **独有模式**：load 命中同一 cache line、但地址与刚 store 的地址不同 —— 走
  **same-line 非 forwarding 的慢速窗口**（store-to-load 不可转发，需等 store 数据可见）。
  此前从未压过这个路径。
- golden：`dst[i] = expected[i-1]`（旋转一位），temp 预填 ALU golden 保证首轮读有效数据。
- **footprint 澄清（2026-09-04 评审时更正）**：stale_reload 热循环实际 footprint 是
  **64KB**（srcA+srcB+temp+dst 各 16KB；`srcref`/`expected` 只在 init 和每轮末尾
  memcmp 被碰，不属热数据）。**首次超 L1D 的只有 ldr_at_top（80KB，多了 scratch）**，
  见 §8.1。

### 4.2 `neon_rot_ldr_at_top`（`tests/cpu/misc/neon_rot_ldr_at_top.cpp`）—— 主嫌疑

热循环（`neon_rot_ldr_at_top.cpp:88-109`）：

```cpp
TEST_LOOP(test, 1 << 13) {
    for (int i = 0; i < NEON_ROT_LDR_AT_TOP_COUNT; i++) {
        uint64x2_t unused_x = load_vec(&data->scratch[i]);   // 第3个ldr在迭代顶部，值丢弃
        (void)unused_x;

        uint64x2_t a = load_vec(&data->srcA[i]);             // asm 固定 ldr
        uint64x2_t b = load_vec(&data->srcB[i]);             // asm 固定 ldr
        uint64x2_t res;

        switch (i % 4) {                                     // ALU 轮换
            case 0: res = vaddq_u64(a, b); break;
            case 1: res = veorq_u64(a, b); break;
            case 2: res = vandq_u64(a, b); break;
            case 3: res = vorrq_u64(a, b); break;
        }

        store_vec(&temp[i], res);   // ┐ 背靠背双 store
        store_vec(&dst[i], res);    // ┘ 同一寄存器写两个目的地
    }
    if (memcmp(dst, data->expected, ...) != 0) report_fail_msg(...);
}
```

指令序列总结：

```
每轮 i (0..1023):
  ldr q,  [scratch[i]]   ← 第3个ldr，迭代顶部，值丢弃
  ldr a,  [srcA[i]]      ← asm 固定
  ldr b,  [srcB[i]]      ← asm 固定
  add/eor/and/orr        ← 按 i%4 轮换
  str res, [temp[i]]     ┐ 背靠背双 store
  str res, [dst[i]]      ┘ 同一寄存器值写两个目的地
```

其中 `load_vec` 用 `__asm__ volatile("ldr %q0, [%1]": "=w"(res) : "r"(addr) : "memory")`
（防 DCE，NEON 探针的既有坑），`store_vec` 用 intrinsic `vst1q_u64`。

**冻结相关的两个新特性**：

1. **背靠背双 store 写同一寄存器到两个不同目的地**（`temp[i]` 与 `dst[i]`）。
   store_only 也是双 store 双目的地，差别在 ldr_at_top 顶部多了 scratch ldr
   —— 3 ldr + 2 str 的 AGU 混合与 fwd_probe 完全相同，唯一变量本应是第 3 个 ldr 的位置。
2. **线程热 footprint 首次超过 L1D（64KB）**：
   scratch 16KB + srcA 16KB + srcB 16KB + temp 16KB + dst 16KB = **80KB > 64KB**。
   此前所有 NEON 变体都是 4 个 buffer（64KB 恰好压线），循环内工作集首次溢出 L1D。
   （注：该特性是 ldr_at_top 独有；"L1D 溢出本身能解释锁死"的说法在 §8.1 被既往数据
   否定——movbe 128KB / eigen MB 级流式都没冻过机器。此处只陈述事实，不作归因。）

## 5. 关键判断

- **这是与 core-179 SDC 不同的失效模式**：SDC = 数据错、需要 179 在场；本次 = 整机静默锁死、
  179 不在场（阶段1 排除 179 时就冻）。两者不能混为一谈。
- 两种解释目前**无法区分**：
  1. 探针的访存模式本身能锁死（正常的）鲲鹏 920 —— 踩中某个 erratum / 微架构边界条件
     （候选：same-line 非 forwarding 慢窗口、超 L1D footprint 下的背靠背双 store、
     3ldr+2str AGU 混合压力）；
  2. 机器边缘性问题超出 179 一核 —— 但昨夜 6 个 30min 全核测试无一冻结，不太支持。
- ldr_at_top 两次冻结一次比一次快（第 7 轮 → 第 2 轮），提示可能有状态累积
  （如目录/一致性状态、电源管理），但样本只有两次，不足以下结论。

## 6. 下一步（重启战役之前必须做的）

1. **这两个探针源码不要原样重跑**，尤其 `neon_rot_ldr_at_top`。
2. **先装"黑匣子"再复现**——现在冻结 3 次却什么都没抓到：
   - 串口 console / netconsole（硬锁死时唯一可能留下痕迹的通道）；
   - 验证 kdump 是否真正配置可用（crashkernel 内存已预留但这次没有 vmcore 产出）。
3. 有黑匣子后，从 ldr_at_top 开始**低强度复现**（`-n 4` 起步逐步加压），
   确认是访问模式问题还是全核并发问题；单变量拆开 80KB footprint（去掉 scratch，改 4 buffer）
   与顶部 ldr 位置两个因素。
4. 查清 09-03 18:34 / 18:41 两次 SEL 重启的来历（§7）。

## 7. 未解问题

- 09-03 18:34 / 18:41 SEL 有 2 次 System Restart（在三探针战役 09:56 开始之前），
  来历未查 —— 若也是类似冻结，问题可能比"新探针"更早就存在。
- journal 无持久历史（`/var/log/journal` 只剩当前 boot 的两个文件），此前的 boot 日志已丢，
  无法回溯 09-03 晚间两次重启时的内核记录。

---

## 8. 外部评审意见与逐条核查（2026-09-04 追加）

收到一份外部分析,定性框架正确——ldr_at_top 已不是 SDC 探针,而是踩出了新失效维度
(整机硬锁死),且"压的是访存子系统而非依赖链时序"的大方向判断认同。但其多个
**因果归因与本机既往战役数据直接冲突**,记录如下,避免重蹈"把候选机制当根因"的覆辙
(参见 sdc-rootcause-is-hardware-not-timing 的方法论教训)。

### 8.1 "首次超 L1D → L2 填充压力 → 锁死" — ❌ 与既往数据冲突

- **movbe 的热 footprint 是 128KB**,全核战役跑了几周,从未冻结机器
  (footprint 64B~128KB 跨 2000 倍都触发 SDC 的那次矩阵,见 footprint-independent-of-l1d-size)。
- eigen GEMM 流式访问 MB 级矩阵、cachebounce 常驻乒乓,全核 30min 都跑过,无一冻结。

→ L1D 溢出 + L2 压力这台机器早已承受过无数次,**单独不构成锁死解释**。

**附带事实更正**:stale_reload 的热循环 footprint 实际是 **64KB 不是 80KB** ——
`srcref`/`expected` 只在 init 和每轮末尾 memcmp 被碰,热循环只触碰
srcA + srcB + temp + dst 四个 buffer。真正 80KB 的只有 ldr_at_top(多了 scratch)。
且 stale_reload 冻结一次后重跑**完整通过**了 30min 全核(1/2),与 ldr_at_top 的
2/2 连冻不是一回事,两者不能归为同一结论。

### 8.2 "3 loads → AGU 过载 → 锁死" — ❌ 与既往数据冲突

- **3src/4src 梯度测试**(2026-09-02,mrn_nuke 骨架,每元素 3/4 个源 load)全核 30min,
  触发 SDC(10/4 fail)但**没有冻结**(见 src-load-gradient-2src-optimal)。
- mrn_nuke 每轮 24576 次 ldr(8× mrn_rmw 的 load 密度),30min 全核,没冻结
  (见 objdump-7tests-trigger-vs-notrigger)。

→ 每元素 3 个 load 这台机器也早就跑过。另外"鲲鹏 920 (TaiShan v110) = 1 个 LS AGU +
1 个 load-only AGU"这个配置说法**无可靠公开出处**,未经 PMU/微基准验证,一律当未证实
候选处理,不写入结论。

### 8.3 ldr_at_top 真正的独一无二之处 — ✅ 这才是干净起点

对照 store_only(跑完 30min 全核、无冻结、14 fail):

```
store_only:  ldrA  ldrB  ALU  str temp  str dst          ← 干净跑完
ldr_at_top:  ldrX  ldrA  ldrB  ALU  str temp  str dst    ← 2/2 冻结
```

差异只有两件事:①顶部多一个读**第 5 个 buffer** 的 ldr;②footprint 64→80KB。
这是最干净的单变量拆分起点,比"AGU 过载"这类大帽子归因有用得多。

### 8.4 "用 timeout 命令保护" — ❌ 无效

硬锁死时内核完全失去响应,用户态 `timeout` 没有执行机会。正确的黑匣子是:

- **kdump** —— 本次 crashkernel=1024M 已在 cmdline 预留却**没有产出 vmcore**,
  kdump 服务本身是否配置好需要先验证;
- **netconsole / 串口 console** —— 硬锁死时唯一可能留下痕迹的通道;
- NMI hard-lockup watchdog、BMC watchdog。

**附带待查点**:`.DEAD_` 最后写入到 SEL 重启记录之间稳定隔 1~3 分钟 —— 需要确认那是
**人工硬重启还是 BMC watchdog 在兜底**。若是后者,说明机器能自恢复,复现代价小很多。

### 8.5 未被解释的现象:冻结一次比一次快

两次 ldr_at_top 冻结:第 7 轮(~8s) → 第 2 轮(~3s)。纯稳态带宽饱和应当时间稳定;
缩短提示可能存在**跨 run 的状态累积**(热/电源/一致性状态)。样本只有 2,不足以下结论,
但复现实验设计时必须记录该现象。

### 8.6 判别实验设计(全部等黑匣子装好后再做)

| 变体 | 改动 | 判别 |
|---|---|---|
| A | 去掉顶部 scratch ldr,srcA/srcB 各扩到 24KB(总 footprint 保持 80KB) | 冻 → footprint 是元凶 |
| B | 保留 3 loads,COUNT 降到 768(5×12KB=60KB ≤ 64KB) | 冻 → load 数量/混合是元凶 |
| C | 原版,从 `-n 4` 起步逐级加压 | 定并发依赖性 |

前提不变:**先装黑匣子,否则再冻三次还是什么都抓不到**。

### 8.7 评审中正确的部分(采纳)

- 定性:ldr_at_top 是"系统稳定性压力测试"而非 SDC 触发测试,失效模式比数据错误更底层;
- "压的是访存子系统极限,而非依赖链时序"的大方向;
- 建议保留该测试作为系统稳定性边界探索方向,但必须在黑匣子保护下;
- SDC 触发配方不受影响,仍以 2 源 load + ALU + 紧时序为正道。

---

*调查方法存档:判"机器卡死"看 `ipmitool sel list` 的 System Restart 时刻 +
`movbe_log/` 里 `.DEAD_` 标记日志的最后写入时间;本报告事实均已交叉核对(SEL / last -x /
.DEAD 日志 / RESULTS.txt / probe_trio_nohup.log)。*

---

## 9. 第 4 次冻结：arm0102_kreg_mask（2026-09-04 22:38，晚间追加）

> 事件：晚间 arm-0102 变体战役（8 个 fma/vector/kreg 变体，`tests/cpu/arm-0102/`）阶段1
> （taskset 0-178,180-191，179 不在场）串行跑到第 3 个 `arm0102_kreg_mask` 时，
> **第 12 轮（22:38:53）后机器硬冻结**，SEL 22:47:07 System Restart，无 MCE、无 soft-off
> 前奏——**与上午 3 次硬冻结完全同签名**。全天累计 4 次。

### 9.1 时间线甄别（SEL 交叉，重要更正）

晚间 21:57 / 22:13 / 22:29 三次断线 **不是硬冻结**——SEL 有 `S4/S5: soft-off` 前奏
（内存 Presence Deasserted → 1 分钟后正常 boot），是软关机/重启。
22:43:50 的重启无 soft-off、无 MCE，与硬冻结同签名 → **对应 kreg_mask 冻结**。
（Bun/Claude Code 崩溃 3 次为用户态段错误，与机器无关，时间上也不重合。）

### 9.2 kreg_mask 与两个冻机探针的结构对比

同构部分（三测试完全一致）：
- 骨架：`TEST_LOOP(1<<13)` × for(1024) × switch(i%4) 轮换 × asm `ldr %q0,[%1]` 固定 load；
- 布局：srcA/srcB/temp/dst 四 16KB buffer（热 footprint 64KB 恰压线，未超 L1D）；
- 校验：init 预计算 golden、循环末 memcmp、report_fail_msg 冷路径。

kreg_mask 独有（其余 arm-0102 变体和其他冻机探针都没有）：
- **比较类负载轮换**：vceqq_s32 / vcgtq_s32 / vceqq_u32 / vtstq_u32 —— 结果是稀疏掩码
  向量（全 0/全 1 lane），与 add/eor/and/orr/fma/ins-ext 等数据类负载的位翻转环境完全不同；
- 32b lane（uint32x4）——但 neon_rot_u32x4（32b lane + 数据类负载）30min 全核没冻，
  说明 32b lane 单独不冻，**嫌疑组合是"比较类负载"维度**。

kreg_mask vs 冻机探针的差异：
- ldr_at_top：3× ldr + 双 str 同值双目的地（80KB 超 L1D）—— kreg_mask 没有；
- stale_reload：读 temp[i-1] 同 line 不同字 —— kreg_mask 读同址 temp[i]（与不冻的
  neon_rot_2src/kreg_logic/ins_ext 的 reload 图案相同）。

### 9.3 当前嫌疑排序（更新）

1. neon_rot_ldr_at_top（2 次冻结）
2. **arm0102_kreg_mask（1 次冻结，新增）** —— 新嫌疑维度：比较类负载产稀疏掩码
3. neon_rot_stale_reload（1 次冻结 + 1 次完整通过，概率性）

同日对照：同骨架的 ins_ext、kreg_logic（数据类负载）同夜各 54 轮阶段1 全 pass 未冻；
上午 6 个 NEON 变体 stage1+stage2 全通过未冻。共 4 buffer、64KB、2 源 load、
str→ldr 同址 reload 本身已被大量跑过不冻 → 冻结必要条件在上述三探针的独有维度里。

### 9.4 待办（并入 §6）

- kreg_mask 与 ldr_at_top 同待遇：**不原样重跑**；kreg_not/kreg_select/swizzle
  （数据类负载）可先行跑阶段1；
- 复现前先装黑匣子（串口/netconsole + kdump 验证），从 `-n 4` 低强度起步；
- 若后续 kreg_select（含 vbsl 位选择，结果也是掩码形）也冻，则"比较/掩码类负载"
  维度坐实。
