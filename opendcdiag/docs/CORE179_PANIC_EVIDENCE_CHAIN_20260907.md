# 179 号核心宕机证据链 — 为什么跑测试就会关机

日期: 2026-09-07
数据来源: /var/log/messages, /home/sdc/vmcore/*/vmcore-dmesg.txt (kdump), /var/log/sa/sa07 (sar)
状态: 软件层证据链闭环; 指令级机制未定 (需 crash 分析 vmcore 内存映像)

## 一、结论 (先答问题)

**不是测试用例发出了什么"关机指令", 而是全核负载把 OS 守护进程推上了 179 这个坏核,
任何进程在 179 上跑内核态路径都有概率取到错误数据, 错误落在页表遍历/内核数据上就是
kernel panic → kdump → 重启。**

逻辑链条:

1. `neon_rot_ldr_at_top` + `arm0102_kreg_mask` 以 `-n 191/192` 全核运行, 系统负载逼近核数
   (sar: 死前 ld1 一律在 150~190)。
2. 全核满载时调度器会把**所有** runnable 进程摊到所有核上——包括与测试无关的
   `pmdalinux` / `irqbalance` / `HeapHelper` / `mi-scavenger` / `rcu_sched` / kworker。
3. `--cpuset` 只约束 opendcdiag 自己的线程, **拦不住 OS 把守护进程调度上 179**。
   (20:00 的 run 明明排除了 179, 20:00:59 pmdalinux 照样在 179 上报错。)
4. 179 是已坐实的坏硅 ([[sdc-rootcause-is-hardware-not-timing]], SDC 全部绑定 179)。
   它的故障不限于用户态数据: **179 上内核态访存也会错**——
   页表遍历(PTW)随机返回"未映射", 内核数据结构读出脏值。
5. 错误落在内核路径上的两种结局:
   - 重试翻译成功 → `Ignoring spurious kernel translation fault` WARN, 继续跑 (45 例存档);
   - 翻译仍失败 → `Unable to handle kernel paging request` → Oops → panic → kdump → 重启。
6. 所以"跑测试 → 关机"的真正因果是: **测试提供全核压力 → 压力把无辜进程推上 179 →
   179 的硬件错误命中内核路径 → panic**。负载越高、跑得越久, 守护进程在 179 上
   停留的总时间越长, 命中概率越大。这就是为什么死得很"随机"——取决于守护进程
   何时被调度上 179 以及错误是否落在致命路径上。

## 二、直接证据

### 2.1 今天 4 次宕机全部 panic 在 CPU 179 (kdump vmcore-dmesg)

| 宕机时间 | 致命进程 | 错误 | FSC |
|---|---|---|---|
| 13:51:42 | mi-scavenger | Unable to handle kernel paging request (level 2) | 0x06 |
| 15:16:31 | HeapHelper | Unable to handle kernel paging request | 0x04 |
| 17:13:15 | HeapHelper | Unable to handle kernel paging request | 0x04 |
| 20:04:26 | mi-scavenger | Unable to handle kernel paging request (level 3) | 0x07 |

共同特征:
- 全部 `CPU: 179`, 无一例外。
- 致命进程全是 OS/监控守护进程, 无一是 opendcdiag 线程。
- 死前数十秒~数分钟内同一核上已有 spurious fault WARN 密集出现
  (如 20:00:59–20:01:26 共 8 次, pmdalinux/irqbalance 交替)。

### 2.2 spurious fault 全部来自 179, 跨 10 天

`/var/log/messages` 中 45 例 `Ignoring spurious kernel translation fault`:
- **45/45 全部 `CPU: 179`**。
- 进程分布: irqbalance 25, pmdalinux 20 (都是 /proc/interrupts 读者)。
- 时间分布: 09-05 09:01–19:36 (37 例, 上次长 boot), 09-07 20:00–20:01 (8 例)。
- 语义: 内核态访存触发 translation fault, 但内核用 `at s1e1r` 重译同一地址
  **又成功了** → 页表本身是好的, 是 179 的取数/翻译路径返回了假"未映射"。

### 2.3 09-04 三次"硬冻结"vmcore 复盘 — 其实也是 179 panic

当时判为"静默锁死无 MCE", 实际 kdump 全部抓到了 (memory 里有 SEL 判断问题, 但 vmcore 在):

| 宕机时间 | 致命进程 | 错误 |
|---|---|---|
| 09-04 09:15 | kworker/u392:0 (CPU 179) | Oops (前奏: rcu_sched 在 179 报 spurious) |
| 09-04 10:27 | sftp-server (CPU 179) | Oops (前奏: rcu_sched 在 179 报 spurious ×2) |
| 09-04 11:00 | sftp-server (CPU 179) | Unable to handle kernel paging request |

**09-04 的三次冻结与今天的四次宕机是同一故障**: 坏核 179 上的内核态数据错误。
当时"静默冻结"的印象来自串口/kdump 落盘流程不可见, 不是真的无迹可寻。

例外: 09-04 22:09 那次 panic 在 **CPU 168** (systemd-journal, 链表损坏
`__list_add_valid_or_report`) —— 对应 arm0102_kreg_mask 第 4 次冻结时段。
这是唯一一次非 179 的宕机, 是 168 还是共享结构被 179 的脏写污染, 待查
(链表损坏的写入方可能不在报错核上)。

### 2.4 sar 负载对齐: 每次重启前都有满载尖峰

| sar 记录 (sa07) | 重启前负载 | 对应 |
|---|---|---|
| 15:21 LINUX RESTART | 15:10 ld1=20.5→37 爬升 (run 启动中) | 15:16 panic |
| 17:17 LINUX RESTART | 16:50 ld1=152 | 17:13 panic |
| 20:09 LINUX RESTART | ~20:00 run 启动 | 20:04 panic |
| 20:40 ld1=183.67 **无重启** | **179 已 hotplug 下线** | 存活 |

03:50 ld1=189、05:50 ld1=152 时段机器未死——**满载不必然死, 但死时必然满载**。
符合"概率事件": 守护进程在 179 上的暴露时间 ∝ 负载时长。

### 2.5 hotplug 实验证实因果 (正向控制)

20:30 起: `echo 0 > /sys/devices/system/cpu/cpu179/online` 后 191 核全开跑同样双测试:
- 12+ 分钟存活 (超过此前全部 4 次的死亡窗口: 均在 run 启动后 ~1–16 分钟内 panic);
- 0 fail, 0 内核错误, sar 20:40 ld1=183.67 无重启。

对照: cpuset 排除 179 的 run (20:00) 依然 panic——因为 cpuset 管不住 OS 守护进程。
**hotplug 是唯一把 179 从调度器里彻底拿掉的手段。**

## 三、179 留下的全部软件层证据清单

1. 用户态 SDC: 8-24 以来的全部 miscompare, 唯一故障核 (既有结论, 本报告不重复)。
2. 内核态 spurious translation fault: 45 例, 全 179, 全在 /proc/interrupts 读者
   (show_interrupts → seq_printf → __memcpy 栈, 页表遍历返回假"未映射")。
3. 内核态致命 Oops → panic: 今天 4 次 + 09-04 至少 3 次, 全 179
   (mi-scavenger/HeapHelper/sftp-server/kworker/rcu_sched 前奏)。
4. 副作用可能外溢: 09-04 22:09 CPU 168 的链表损坏 panic (唯一非 179 案例, 待查)。
5. 无 MCE / 无硬件 RAS 报错 —— 与 SDC 行为一致: 179 的错误是"静默错值",
   不触发机器检查, 只能靠软件层比对/崩溃现场捕获。

## 四、未闭环 / 下一步

- [ ] 指令级机制: 179 究竟是哪条路径错 (L1D 数据 / TLB / PTW / cache 一致性),
      需 `crash` 分析 vmcore 内存映像 + 对照 20:04 现场 (HeapHelper WARN →
      mi-scavenger panic 相隔 0.6s, 同核, 疑同一错误源两次命中)。
- [ ] 09-04 22:09 CPU 168 panic 与 179 的关系 (脏写污染共享数据?)。
- [ ] hotplug run 长跑过夜验证 (若不再宕机则因果最终闭环)。
- [ ] 建议对所有后续实验**默认 hotplug 下线 179**, 而非 cpuset 排除;
      SDC 检测实验按既有协议仍用"排除 179 的核 + auto seed"。
