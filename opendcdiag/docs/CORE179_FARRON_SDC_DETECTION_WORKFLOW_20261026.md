# FARRON SDC 查询详细流程（技术参考手册）

**日期**：2026-10-26　**适用版本**：farron/ v1.0（2026-10-25 落成）+ 10-26 生产节奏协议
**读者**：需要理解/操作/审计 FARRON 如何在线查询（检测）CPU SDC 的人
**关联**：`farron/DESIGN.md`（状态机设计）、`docs/CORE179_FARRON_PERF_VALIDATION_20261025.md`（5h 验证）、`docs/CORE179_FARRON_3H_STRESSNG_PERF_20261026.md`（3h 性能实测）
**数据根目录**：`farron/state/`

---

## 0. 一页总览

```
━━━ 入口（三通道）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 [被动] LogScanner        [主动] PeriodicTester          [应用] anomaly_<core>
  journal 内核指纹预筛      每30min一轮逐插槽独占扫描        应用侧异常文件上报
  (WARNING: CPU: N 等      (检测主力, 本手册 §3-§6)        (state/ 下即触即读)
   每核≥3条→直送可疑队列)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                  ▼
                        ┌──────── 可疑状态 ────────┐
                        │ 深度测试(600s/用例,≤8个)  │──复现──→ 裁决:
                        │ 可疑级+活跃级用例钉核深测  │   缺陷核<2 → 屏蔽该核
                        └───────┬─────────────────┘   缺陷核≥2 → 整颗CPU退役
                          未复现 ↓ 返回在线观察
━━━ 全程守护 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 温度控制器(滑动窗口/动态边界/降载) + 98°C看门狗 + 应用保活(ensure_app)
```

**一句话**：FARRON 查询 SDC = 三通道入口 → 整插槽独占的定时memcmp探测 → fail 块定位到逻辑核 → 可疑核深测复核 → 屏蔽/退役裁决，全程温度自适应、应用可存活。

---

## 1. 检测对象：本机 CORE179 的 SDC 特性（决定流程设计）

| 特性 | 事实 | 对流程的约束 |
|---|---|---|
| 根因 | 硬件故障绑定 179 硅（L1D 读路径），非时序/软件 | 检测=找"算错"，不是找"慢" |
| 表现 | 静默数据损坏（用户态 miscompare 为主） | 必须主动 memcmp 类逐字节核对，不能只等报错 |
| 间歇性 | 爆发/潜伏期交替，率 0.45×~4× 跨夜波动 | 单窗结果不判定，多轮累积；率比较须 ≥1h 窗口 |
| 触发本质 | L1D 域 load 低概率随机错（~1e-6/ldr）× 巨量 load | 检测器必须是"大量 L1D 命中 load + 立即消费"的形态 |
| 负载类型门控 | 单核探针/分时构型下触发被关死 | **必须整插槽独占**（§3.1） |
| 温度 | 无正相关（多轮实证） | 温度控制器只为机器安全，不为检出率 |

---

## 2. 三通道入口

### 2.0 机器级前置分级制度（fleet 层筛查，运行 FARRON 之前；2026-10-29 登记自用户口径）

单机 FARRON 之前，先在机房/fleet 层用日志特征给机器分级，决定**谁上 SDC 检测、怎么测**：

| # | 判据 | 效果 |
|---|---|---|
| 1 | 没有硬件报错信息 | （与软错并存的 SDC 静默签名组合条件） |
| 2 | 被 SDC 测试套件标记 | **直接判最高级**（无论是否有 SEL 报错） |
| 3 | ≥2 种应用软件报错，且 60% 以上错误集中在某个物理核 | 概率提升一个量级（注：梅婷有一块类似特征的主板，预计 8 月底到华为） |
| 4 | 30 天内 ≥3 次非计划重启 | 概率提升一个量级 |
| 5 | 多次送修未定位 | 概率提升一个量级（当前不存在多次送修——直接更换主板） |
| 6 | 软件层错误总数最多的前 N 台标记为嫌疑机器（暂定 N=50） | 入围条件 |

**执行规则**：等级 ≥2 → 执行 SDC 检测；符合 1+3 → **重点审核故障节点**；≥2 但不含 3 → 尽可能多核心测试。

**本机（179 机）评估：命中 1/2/3/4/6，等级很高**（证据）：
1. ✓ 15 天 RAS/EDAC/rasdaemon/SEL 错误类报告**全零**（2026-10-29 实测清点，PROCHOT 66 条属保护动作非错误）
2. ✓ SDC 测试套件 8000+ 事件、246/246 窗全检出——直接最高级
3. ✓ 报错 ≥2 种（内核 fault 警告 69 条全 179 / Oops·panic 9 月 15 次 / 用户态 miscompare 8000+）；集中度 **100% 锁物理核 179**（远超 60%）
4. ✓ 9 月任意 30 天窗内非计划重启 ≥3（09-11 单日 5 次；全月 15 次 panic 级）
5. ✗ 无送修史（换板策略）
6. ✓ 软件错误总数顶尖档（嫌疑机器池）

**⚠️ 关键执行口径修正（本机三构型实验结论）**：规则"符合 1+3 → 重点审核故障节点"中的"重点审核"**不可实现为只测嫌疑核单核**——单核独占 330s **零检出**、插槽共享零检出、**整插槽独占每窗必中**（负载门控）。正确实现 = **嫌疑核所在插槽整插槽独占并发深测**（FARRON 生产形态）。`farron.py` v1.0 深测当前为钉单核 `-n 1` 且不迁应用，会踩中此门控——属 §13 已知集成缺口的具体化，接入插槽独占协议时须一并修正。

### 2.1 被动通道：LogScanner（`farron/log_scanner.py`）
- **输入**：`sudo journalctl -k`（全量或 `--since` 增量）
- **模式集**：`WARNING: CPU: N`（kernel_fault_warning）/ spurious fault / Oops / kernel BUG / MCE·SEA·external abort；白名单滤启动噪声（Booted secondary/GICv3/psci 等）
- **裁决**：每核错误计数 ≥3（可配）→ 携首末条证据**直送可疑队列，免主动预筛**
- **实测依据**：当前 boot 67 条 `WARNING: CPU: 179` 100% 聚集于 179，其余 191 核零条
- **诚实边界**：SDC 本质静默——5h 评估 469 次 SDC 中仅 22 次泄漏为内核告警。**被动通道是加速器与先验，不能替代主动测试**

### 2.2 主动通道：PeriodicTester（本手册主体，§3-§6）

### 2.3 应用上报通道
用户应用自发现异常 → `touch farron/state/anomaly_<core>` → 主循环 `poll_anomalies()` 即触即读（文件即消息，读完即删）。池内核上报 → 进可疑状态。

---

## 3. 主动通道执行形态（已验证协议）

### 3.1 前置裁决：为什么必须"整插槽独占"（2026-10-25 三构型对照实验）

| 构型 | 179 上结果 | 结论 |
|---|---|---|
| 单核独占（逐核暂停 15s，原方案） | 330s 零检出 | ❌ 负载类型门控关死 |
| 插座分时（47/48 核与应用共享） | 2×30s 零检出 | ❌ 时序配方被 co-running 负载打断 |
| **整插槽独占（应用整插槽迁出）** | **每窗必检出** | ✅ 生产形态 |

**三条设计修订**：①暂停粒度=插槽；②窗口下限=30s（15s 检出率仅 35%）；③迁移机制=对 fork 型应用逐进程 `taskset -pc` 改亲和。

### 3.2 调度节奏（生产形态）
- **每 30min 一轮**；轮内 CPU1→CPU2→CPU3→CPU4 背靠背，每窗 `-T 30s`
- 轮完成后睡到"启动时刻 + n×1800s"边界，周期严格对齐
- 6h 部署约 12 轮；轮墙钟 ~123s（110-140s）
- 每插座每轮被借用一次 ~30s（fail 窗 19-49s：fail 后重试链拉长、fail 早则整窗提前结束）

### 3.3 单窗执行七步（`farron/prod_sweep.sh`，逐条对应源码）
1. **应用迁出**：`set_app_mask REST[S]` —— 对 stress-ng 主进程+全部 worker 逐个 `taskset -pc`，应用掩码 191 核(0-178,180-191)→144 核（本插槽以外）
2. **独占测试**：`taskset -c SOCK[S] opendcdiag -e neon_rot_ldr_at_top_rowmajor -n 48 -T 30s --ignore-os-error --ignore-timeout -o s<N>_<S>.log`
   - `-n 48` = 每核一线程，线程 i ↔ 插槽第 i 核（CPU4 插槽 thread 35 = logical 179）
3. **等待退出**：干净窗墙钟 29-31s；fail 窗 19-49s
4. **计数**：`grep -c 'result: fail'` = 本窗 fail 块数
5. **fail>0 时**：awk 从 log 提取逐 fail 时刻（elapsed=(time-at-start+time-at-end)/2，ms→s）追加 `fail_times.csv`；stdout 保留为 `keep_s<N>_<S>.stdout`（证据）
6. **应用迁回**：`set_app_mask APP_MASK`（191 核）
7. **记账清理**：删除窗内大文件，写 `sweeps.csv` 一行

### 3.4 应用保活
`ensure_app` 每轮开头检查 `app.pid`；应用死 → 自动以同掩码重启（8h 超时兜底）。

---

## 4. 检测器：测试用例原理与用例池

### 4.1 触发配方三要素（两个月战役的结论，缺一不可）
1. **≥2 源 load**（从内存载入两个源操作数；1 源=0 触发）
2. **轮换/混合 ALU**（add/eor/and/orr 轮换；纯单指令 36min=0）
3. **紧时序**（str→ldr 须 ≤2 周期窗口；nop 间距 ≥8cyc 即灭活）

**本质**：给 179 的 L1D 读路径以海量"命中后立即消费"的 load，让 ~1e-6/ldr 的随机错有机会显形。对照证据链：零 store=0、u8x16 lane 塌缩=0、松时序=0、evict-L2 路径=0——每条灭活对照都在用例池基础级里登记。

### 4.2 主力检测器解剖：`neon_rot_ldr_at_top_rowmajor`（P0 #1，~8.5/min）
源码 `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor.cpp`：
- **init**：srcA/srcB/scratch 各 16KB 随机；`expected` = 同 NEON 单元预计算 golden（i%4 轮换 vadd/veor/vand/vorr）
- **每线程**：temp/dst 各 16KB
- **热循环** `TEST_LOOP(test, 256)`：外层迭代偶数轮升序/奇数轮降序扫 1024 槽（rowmajor 变体的签名判别设计）
- **每槽**：`ldr scratch`(弃用第三load) + `ldr srcA` + `ldr srcB` → 按 i%4 轮换 ALU → `str temp` + `str dst`（背靠背双 store）
- **每 sweep 后**：`memcmp(dst, expected, 16KB)` 不符 → `report_fail_msg("data miscompare")`
- **fail 输出块**：`result: fail` + `fail: {cpu-mask, time-to-fail, seed}` + `threads[].id.logical`

### 4.3 三级用例池（`farron/testcase_pool.json`，权威源 `docs/CORE179_ALL_VALID_SDC_TESTCASES_20260923.md` + 梯队文档）
- **活跃级 57 个**（已证实可检测，fail 全锁 179 且可追溯）：P0×6（≥3/min 主力：rowmajor/sub/mrn_reloaded_2src_alu/str3/movbe/mla）、P1×5、P2×11（K-cells 主战场）、P3×15、P4×20
- **基础级 83 个**（从未检出：灭活对照 70——每条证明一个必要条件；未入账 13）
- **特殊排除 8 个**：`movbe_dump_probe_c`（多核风暴非 179 源）、`neon_rot_ldr_at_top` 原版（**禁跑**：全核硬冻结 2/2）、sched_storm×4（非 SDC 刺激器）等
- **选题优先级**（`farron.py next_case()`）：**可疑级 > 活跃级（P0→P4 轮换）> 基础级**；低热裕量时仅 P3/P4 轻量梯队
- **使用口径**：日常 SDC 门=movbe 或 P0 任一；诊断=mrn_reloaded_2src_alu + K-cells；签名采集=dualcmp + gps

---

## 5. opendcdiag 框架内层机制（一窗之内发生了什么）

### 5.1 TEST_LOOP 与时间片
`TEST_LOOP(test, N=256)`：测试体执行 256 次 → `test_loop_condition` 检查一次（迭代配额/墙钟截止 `-T`）→ 继续/终止。热路径纯忙循环（无 sleep；`inject_idle` 未启用）。

### 5.2 fracture 分段（影响性能，不影响判定）
- 测试**通过**时以分段模式执行：每段 ~40 次迭代（<10ms 完成则配额翻倍），段间主线程做日志/种子推进/温度打印等记账，**48 个测试线程此时在 futex 上等待** → 干净窗测试进程 CPU 占空仅 ~37%（18/48 核）
- **失败后的重试轮显式禁用 fracture**（`current_max_loop_count = -1`）满速跑 → fail 窗占空 ~71%
- 性能含义见 §9；对检出而言 fracture 每段推进随机种子，或有利于覆盖

### 5.3 失败→重试链（`framework/sandstone_run.cpp:1664-1817`）
1. 首次失败：`report_fail_msg` → 该轮 `state != Passed` → 跳出 fracture 循环
2. 重试链：**同种子重试 → 新种子重跑**，每轮都是完整 48 线程 run；仅失败一次时配额×2；受 `MaxRetestCount` 上限
3. 每次失败各产生一个独立 `result: fail` 块（同窗多块的来源）
4. `--ignore-os-error --ignore-timeout`：fail 不中止进程、超时不硬杀——保证一窗内多重采样

### 5.4 time-to-fail 语义（重要口径）
- **首块 ttf = 窗内相对时刻**（检测延迟唯一合法口径；实测分布 min 3.6s/中位 15.9s/p90 36.2s/max 39.2s，≤30s 占 79%，含框架 ≤1 迭代过冲）
- 重试块的 ttf 时钟基准异常（~995s 伪值），**严禁**计入延迟统计

---

## 6. 结果解析、计数与定位

### 6.1 计数口径（铁律）
- **fail 块 = 一个唯一 `result: fail` 块 = 一次真实 miscompare 事件**
- 严禁 `grep -c miscompare`（双计 2 倍陷阱）
- 报数须分列：每窗**首块 = 独立检出**；第 2+ 块 = 重试轮中的再次失败（同为真实事件，但语义不同）

### 6.2 定位（三法交叉，缺一不可）
1. `fail: {cpu-mask: '...X...'}` —— 唯一 X 位
2. `threads[].id.logical: N` —— 失败线程的逻辑核号
3. sweep 脚本 `cores` 列（stdout 提取去重）
→ 三法一致才入账。实测 708/708 次 fail 全部锁定 logical 179。

### 6.3 误报控制（特异性）
- 干净插座（CPU1/2/3）窗口**必须恒 0**：5h 441 窗 + 3h 264 窗零误报
- 同一缺陷核的 fail 核号应高度一致；分散多核的"检出"（如 probe_c 风暴）视为不同源，排除

### 6.4 数据落盘清单（schema）

| 文件 | schema | 写入时机 |
|---|---|---|
| `sweep/<run>/sweeps.csv` | `ts,sweep,socket,fails,cores,dur_s` | 每窗一行 |
| `sweep/<run>/fail_times.csv` | `ts,sweep,socket,failn,elapsed_s` | 每 fail 块一行 |
| `sweep/<run>/keep_s<N>_<S>.stdout` | opendcdiag stdout 全文 | 仅 fail>0 窗保留（证据） |
| `sweep/<run>/events.log` | 生命周期（轮开始/休眠/结束） | 轮级 |
| `state/state.json` | 可靠池/屏蔽/退役/可疑队列/温度/可疑级池 | farron.py 每 persist() |
| `state/farron.log` | 系统日志 | 全程 |
| `state/derate_<socket>.flag` | 内容=降载时刻 | 温度控制器（存在即降载中） |
| `state/anomaly_<core>` | 应用上报（存在即消息） | 应用侧写、FARRON 读后删 |

---

## 7. 温度控制器（`farron.py TempController`，每插槽一路）

- **采样**：5s/次 `ipmitool sensor reading CPU*_TEMP`，滑动窗口 W=12
- **初始边界**：首窗最大值 + 15°C（或配置固定值）
- **边界自适应**：窗口内**超过一半**记录高于当前边界（=应用正常工作温度本就偏高）→ 升界（max 策略：B←窗口最大值；可选 step +2°C），避免频繁降载
- **降载判定**：**只有最新温度（tail）超界**才降载（历史高不触发）；tail 回落界下即解除
- **降载动作**：暂停该插槽全部测试负载 + 落 `derate_<socket>.flag` 供应用侧配合
- **测试时长按热裕量分配**（margin = B − 最新温度）：

| 热裕量 | 分配 |
|---|---|
| ≥10°C | 300s（基础时长） |
| 5~10°C | 120s |
| <5°C | 60s 且仅轻量梯队（P3/P4） |
| 降载中 | 0（该插槽暂停） |

自检 12/12 全过（边界设定/自适应/tail 规则/历史高不触发/拓扑解析/池计数）。

---

## 8. 可疑状态、深度测试与裁决

1. **触发**（三来源）：定期测试在**可靠池内核**上 fail（新错误）／应用上报 anomaly／日志预筛达阈值
   - 已知缺陷核（179，初始标定即排除在池外）的常规触发不算新错误
2. **标记**：该用例针对该核标可疑级，`testcase_pool.json` 立即落盘（`mark_suspicious`）
3. **深测**：取该处理器（插槽）的**可疑级+活跃级**用例，**钉在该核**逐个深测——每用例 600s、上限 8 个、温度门控（降载中等待降温）；一复现即止
4. **裁决**（`verdict()`）：该插槽**累计缺陷核数**（含历史已屏蔽，如 179）**<2 → 仅屏蔽缺陷核**，其余核心返回可靠池；**≥2 → 整颗处理器退役**（插槽全部核心移出池）
5. **未复现** → 返回在线状态保留观察（不误杀）

---

## 9. 性能与开销（实测，3h 背靠背极限 + 生产节奏推算）

| 指标 | 背靠背极限（3h 实测） | 生产节奏 30min/轮 |
|---|---|---|
| FARRON CPU 占总消耗 | **13.3%**（22.27/166.97 核；占空 37%/71% 由 fracture 决定） | **~1%**（推算） |
| 应用吞吐保持率 | 75.75%（损失全来自插槽迁出，纯算术 144/191） | **~98.2%**（推算；6h 实测进行中） |
| 检测延迟（窗内首 fail） | 中位 15.9s，≤15s 46%，≤30s 79%，**100% 最终检出** | 同 |
| 端到端首检 | 118s（首轮扫到缺陷插槽） | 首轮即检（≤2.2min） |
| 单窗应用代价 | 该插槽 48 核让出 ~30s | 同 |

---

## 10. 安全守护

- **温度监控**：5s 采样落盘（temp_5s.log）
- **看门狗**：任一插槽 ≥98°C 连续 2 次采样 → 杀当前 opendcdiag 测试进程（`watchdog_cont.sh`）
- **应用保活**：ensure_app 每轮检查 + 8h 超时兜底重启
- **179 暴露量**：仅 CPU4 窗 ~32s/轮（生产节奏下 ~6.4min/6h）——远低于历史上引发 panic 的连续负载强度
- **进程独立性**：全部 nohup+disown，不依赖任何会话存活；数据全程落盘

---

## 11. 验证战绩

| 战役 | 结果 |
|---|---|
| 5h 连续评估（10-25） | 147/147 窗全检出，469 fail 全 179，441 干净窗零误报，端到端 128s |
| 3h stress-ng 环境（10-26） | 87/87 窗全检出，239 fail 全 179，264 干净窗零误报，端到端 118s |
| 被动通道实证 | 当前 boot 67 条 WARNING: CPU: 179，100% 聚集 |
| 跨背景鲁棒性 | stress-ng 满载 146 核背景下照常触发——只需本插槽安静 |
| 温度控制器 | 自检 12/12 + dry-run 全状态机流程通过 |

---

## 12. 已知限制与使用规矩

1. **窗口 ≥30s**：15s 窗检出率仅 35%（5 轮累积 ~90%）；单窗 ≥95% 需 ~60s
2. **潜伏期漏检可能**：率低时（如 2/min）30s 窗检出率降至 ~63%——多轮累积兜底，单窗阴性不下结论
3. **ttf 只取每窗首块**（§5.4）
4. **报 fail 数须分列独立/重试**（§6.1）
5. **率比较须 ≥1h 窗口或多窗口交替**（爆发/潜伏周期主导单窗率；跨夜 0.45×~4× 波动）
6. **复跑前必查**：arm0102 四用例须先注册 meson；`neon_rot_ldr_at_top` 原版禁跑（硬冻结 2/2）
7. **被动通道只是先验**：SDC 静默为主（469 中仅 22 泄漏内核），主动 memcmp 才是兜底

---

## 13. 集成状态与文件地图

| 组件 | 文件 | 状态 |
|---|---|---|
| LogScanner（被动） | `farron/log_scanner.py` | ✅ 独立可用（`--json` 供主程序消费） |
| TestcasePool | `farron/testcase_pool.json`（类在 farron.py） | ✅ |
| TempController | `farron/farron.py` | ✅ 自检 12/12 |
| HealthManager（深测/裁决） | `farron/farron.py` | ✅ dry-run 全流程过 |
| PeriodicTester | `farron/farron.py RealRunner` | ⚠️ v1.0 为全池分时形态；**已验证的整插槽独占+应用迁离协议在 `prod_sweep.sh`（评估形态）**，尚未接回 farron.py 主循环——接线前，跑应用时的新缺陷核可能被分时门控挡住（§3.1） |
| 评估/生产扫描 | `farron/prod_sweep.sh`、`eval_sweep.sh` | ✅ 已验证（本手册 §3） |
| 采样与守护 | `cpu_total_sampler.sh`、`app_cpu_sampler.sh`、`temp_monitor_5s.sh`、`watchdog_cont.sh` | ✅ |
| 逐核原型（已否定，留档） | `farron/per_core_sweep.sh` + `state/sweep/gate179_*` | 历史校准数据 |

**操作速查**：
```bash
python3 farron/farron.py --selftest        # 温度控制器规格自检
python3 farron/farron.py --dry-run         # 全状态机模拟演示
python3 farron/farron.py                   # 实机守护运行
python3 farron/farron.py --status          # 读 state.json 当前状态
python3 farron/log_scanner.py --json       # 被动通道预筛
bash farron/prod_sweep.sh <秒> <目录> [周期秒]   # 生产节奏扫描（评估形态）
# 读结果：sweep/<run>/sweeps.csv（fails>0 → cores 列即定位；干净插座须恒 0）
```
