# CORE179 调度刺激器（sched_storm 家族）阶段2正式跑结果

日期: 2026-09-12 23:04 – 2026-09-13 01:06 (连续 2h2m, 机器未重启)
产物目录: `phase2_sched_storm_run/` (driver.log / progress.txt / verdict.txt / logs/*.log / monitor_*.log)

## 背景与目的

vmcore 证据链 (docs/CORE179_PANIC_ROOT_CAUSE_SCHEDULER_FINDING_20260912.md) 推导:
11 次 179 致命 panic 全崩在 find_busiest_group+0x140, 经 newidle_balance 到达;
受害者是 8 个不同进程, 共同点 = 在 179 上睡眠/退出。该推导要升级为实测复现,
需证明"高频调度活动是 179 崩溃的充分刺激"。

## 测试家族 (tests/cpu/misc/sched_storm_*.cpp, 4 变体)

| 变体 | 调度路径 | 复现的历史案例 |
|---|---|---|
| sched_storm_futex | futex WAIT(1us超时)自醒循环 → 每睡一次=一次 newidle_balance | #3/#4 例 HeapHelper |
| sched_storm_thread | 短命线程 create→exit→join → 每次退出=do_task_dead→newidle | #11 例 (09-12 10:00) |
| sched_storm_hybrid | 两线程绑同核 futex ping-pong → 睡眠+唤醒拉回双路径 | 补充 |
| sched_storm_baseline | 纯寄存器 ALU 自旋, 不睡不退 — **阴性对照** | — |

## 阶段2执行记录 (每变体 30min, 全核192, 179在线)

| 变体 | 时段 | 迭代 | fail块 | exit | vmcore | journal严重错误 | 判定 |
|---|---|---|---|---|---|---|---|
| baseline | 23:04–23:34 | 1592 | 0 | pass | 0 | 0 | clean |
| futex | 23:35–00:04 | 1038 | 0 | pass | 0 | 0 | clean |
| thread | 00:05–00:35 | 152 | 0 | pass | 0 | 0 | clean |
| hybrid | 00:35–01:05 | 742 | 0 | pass | 0 | 0 | clean |

三法交叉验证: (1) 各日志 exit:pass + 0 fail块 + 0 miscompare;
(2) 全窗口 journalctl 直查 (23:04–01:06) spurious/Oops/paging request/panic = **0**;
(3) VPOLL 心跳 243 条连续至 01:05:28 (无硬冻结)。
每变体结束复检 179 在场 (online=1, nproc=192)。kdump 全程武装 (未用上)。

## 刺激强度实测 (perf 计数, 单核 10s, taskset -c 100)

- futex 风暴: **2,621,410 次上下文切换** (262k/s/核)
- baseline 自旋: **114 次**
- 强度差 ~23000×: 刺激变体确实产生了海量 newidle 调度事件, baseline 确实几乎为零。
  **全 clean 不是"没刺激到"——刺激真实送达且量级巨大。**

外推: futex 30min 单核 ~4.7 亿次调度事件; 全核 192 并发下每变体至少 10^9 量级
调度事件落在调度器路径上, 含 179。

## 结果判读 (严格, 不提前下结论)

1. **阴性对照符合预期**: baseline 30min 不崩 — "调度活动是必要条件"未被证伪。
2. **充分性未获复现**: 3 个刺激变体共 90min 定向调度风暴 (10^9 量级事件) 未触发
   179 panic/Oops/任何内核错误。"newidle_balance 调度活动是**充分**刺激"的
   主张停留在推导级, 本轮 30min×3 的剂量未坐实之, 也未证伪之。
3. **与历史数据的张力**: 历史 11 次 panic 死亡窗口 1~16min (泊松), 但都发生在
   "全核 SDC payload 负载 + 179 上调度活动"的**复合**条件下。本实验只有纯调度
   风暴、无数据 payload。两种候选解释并存:
   (a) 30min/变体剂量不足 (泊松尾部, 历史也可能是多小时低率过程);
   (b) 充分条件需要 payload (L1D 域数据负载) + 调度活动叠加, 单独调度活动不够。

## 排障记录 (阶段1冒烟期间, 有独立价值)

- thread 变体 191 核"0迭代卡死"**不是死锁**: 框架只在 TEST_LOOP 迭代间检查 -T;
  全核宽度下 create+join 从单核 20us 膨胀到 ~0.75ms (clone/exit 全宽竞争, 37×),
  N=1<<16 → 49s/迭代 > 时限 → 首迭代永完不成。实测 -T 45s 墙钟 94s 完成 1 迭代
  证伪死锁说。修复: N 降为 1<<13 (全宽 ~11.7s/迭代)。
- 拓扑实测 (create+join 每 op): 单核 20us; 1进程×24线程 0.15ms;
  8进程×24线程(=框架拓扑) ~0.75ms; 1进程×191线程 4ms (glibc 栈缓存 mm 锁串行化)。
- hybrid 首版 bare wake-then-wait 死锁 (唤醒先于对方 wait 到达即永久丢失):
  改 1ms 超时 + futex seq 协议, 构造性免疫。
- baseline 首版被 GCC DCE 折叠成空循环: asm volatile("+r") 挡住, objdump 复核。

## 下一步选项 (未执行, 待定)

- **选项A 延长**: 刺激变体延长至 2h+/变体 (泊松剂量加倍)
- **选项B 叠加**: SDC payload (movbe/neon_rot 类) + 调度风暴并发 — 直接检验
  "复合条件"假说, 与历史崩溃条件最接近
- **选项C 阶段3单核**: 独立二进制 taskset -c 179 vs 180 对照 (最干净归因,
  排除全核并发的干扰变量)
- 机器已恢复空闲常态; /etc/cron.d panic 自动续跑保险已拆除。
