# 179/180 号核对照观察实验记录 — 全核双测试 + 排除 180 号核

日期: 2026-09-08
关联: docs/CORE179_KERNEL_SDC_LOADTYPE_AND_PROCESSES_20260907.md (负载类型与出错进程清单)
关联: docs/CORE179_PANIC_EVIDENCE_CHAIN_20260907.md (证据链总报告)
数据: /home/sdc/obs179_20260908/ (trace.log 1.1G, census179/180_final.txt)

## 一、实验目的

回答: **运行双测试时, 被满载调度器推上 179 (故障核) 的究竟是哪些进程?**
用户要求以 180 号核作为健康对照: 排除 180 的测试线程, 让 180 以"全机最闲的核"
的身份接待守护进程, 记录其访客, 与 179 对照。

方法学修正 (相对用户原方案):
1. 179+180 同时进 ftrace cpumask — 179 的访客时间线是第一手数据 (vmcore 只能
   告诉你最后一个受害者, trace 告诉你全部访客序列); 对两核 tracepoint 开销
   对称, 不破坏对照。
2. trace_pipe 持续引流 + 每秒 sync -f — panic 会吞掉未落盘的 ftrace 缓冲区,
   最多只丢最后 1 秒。
3. dmesg -w 旁路实时抓内核错误 (spurious/Oops/paging request), 与 trace
   时间戳可交叉。
4. 观察器 taskset 绑 CPU 0 — 不污染 180 的"闲核吸引守护进程"属性。
5. 独立 ftrace instance (obs179) — 不污染全局 tracing。

## 二、实验配置

- opendcdiag: `-e neon_rot_ldr_at_top -e arm0102_kreg_mask -n 191 --cpuset '!180'
  --ignore-os-error --ignore-timeout -T forever` (13:16 启动)
- 179 在线 (实验前从昨晚 hotplug 下线状态恢复), 180 排除测试线程但保持在线
- ftrace instance obs179: cpumask=179,180, sched:sched_switch, trace_pipe 引流
- 观察时长: 13:16 ~ 16:16, 共 3 小时 (远超 30 分钟判据)

## 三、结果

### 3.1 内核态: 零错误 (判据通过)

- kernel_err.log: **0 行** (无 spurious fault / Oops / panic)
- 机器无重启 (同 一开机周期)
- 历史死亡窗口为 run 启动后 1~16 分钟 (7 次 panic); 本次 179 在线满载 3 小时
  零内核错误。

### 3.2 用户态: 113 fail, 全部 thread 179 (触发配方生效)

全部为 neon_rot_ldr_at_top miscompare, cpu-mask X 位指向 179。
说明: 113 fail ≈ 0.63/min, 与历史 179 用户态 SDC 率 (~0.24~1.1/min 量级) 相符。

### 3.3 访客普查 (sched_switch next_comm 统计, 全 3 小时)

**CPU 179 (故障核, 带测试线程):**

| 访客 | 调度次数 | 角色 |
|---|---|---|
| swapper/179 (idle) | 44,374 | — |
| arm0102_kreg_mask | 20,217 | 测试线程 |
| kworker/179:2 | 20,017 | 内核工作队列 |
| neon_rot_ldr_at_top | 19,238 | 测试线程 |
| control | 11,466 | opendcdiag 控制线程 |
| migration/179 | 10,181 | 内核迁移线程 |
| **rcu_sched** | **2,397** | RCU 内核线程 |
| **HeapHelper** | **2,030** | 内存巡检 helper (历史 panic 受害者) |
| claude | 719 | 本观察工具 |
| **mi-scavenger** | **492** | 内存巡检守护 (历史 panic 受害者) |
| pmcd | 231 | PCP 收集器 |
| python3 | 190 | — |
| **NetworkManager** | **110** | 网络管理 (历史 panic 受害者) |
| ksoftirqd/179 | 93 | 软中断 |
| kworker/u384:2 | 29 | unbound 工作队列 |
| **pmdalinux** | **27** | PCP daemon (历史 spurious fault 受害者) |
| jbd2/dm-2-8 | 26 | ext4 journal |
| sshd | 23 | — |
| kworker/179:1H | 22 | 高优先级工作队列 |
| Bun | 21 | — |

**CPU 180 (健康对照, 无测试线程):**

| 访客 | 调度次数 |
|---|---|
| swapper/180 (idle) | 2,107,445 |
| rcu_sched | 839,442 |
| claude | 762,837 |
| HeapHelper | 604,055 |
| mi-scavenger | 567,353 |
| NetworkManager | 388,134 |
| jbd2/dm-2-8 | 91,273 |
| kworker/180:1H | 58,589 |
| ksoftirqd/180 | 44,303 |
| pmdalinux | 24,426 |
| sshd | 17,195 |

### 3.4 关键对照结论

1. **历史 panic/spurious-fault 受害者进程本次全部到访过 179**: mi-scavenger
   (492 次), HeapHelper (2030 次), NetworkManager (110 次), rcu_sched (2397 次),
   pmdalinux (27 次), kworker (20017 次) — 但本次 3 小时**零内核错误**。
   这些进程上 179 不必然出错; 错误是否发生与负载时长、进程在 179 上的
   执行内容有关 (概率事件)。
2. **180 承受了高 2~4 个数量级的守护进程流量而零错误** — 同样的守护进程
   在健康核上高频运行不出错, 支持因果归因: 错误在核 (179), 不在进程。
   例: HeapHelper 在 180 上 60 万次调度无错, 在 179 上 2030 次调度, 历史
   panic 时致命。同样的代码, 不同的核, 不同的结果。
3. **用户态 SDC 与内核态错误是两个独立表现**: 本次用户态 113 fail (全 179)
   的同时内核态零错误。179 的用户态错误率稳定 (~0.63/min), 内核态错误
   是更稀有的事件 (历史 7 panic / 多天满载)。
4. **"满载不必然死, 死时必然满载"**: 本次 3 小时满载 + 179 在线 + 守护进程
   全部到访, 未发生内核错误。与 09-04/09-07 的"死时必然满载"不矛盾 —
   内核态致命错误是低概率事件, 单次 3 小时跑不必然复现。

## 四、数据文件

- `/home/sdc/obs179_20260908/trace.log` — 599.7 万行 sched_switch 原始记录
  (压缩件 trace.log.zst); 其中 [179] 事件 132,129 条, [180] 事件 5,865,268 条;
  观察窗口 13:15:57 ~ 16:17:08
- census179_final.txt / census180_final.txt — 全量访客普查
- builddir/run_excl180_obs.log — opendcdiag run 日志 (113 fail, 全 thread 179)

## 五、对记录方法的完善 (已固化到 obs179.sh)

1. trace_pipe 持续引流 + 每秒 sync -f: panic 只能吞最后 1 秒
2. 179+180 双核 cpumask: 第一手访客时间线 + 健康对照
3. dmesg 旁路 + trace 时间戳交叉
4. 观察器绑 CPU 0, 不污染 180 的闲核属性
5. 独立 ftrace instance, 用后即删
