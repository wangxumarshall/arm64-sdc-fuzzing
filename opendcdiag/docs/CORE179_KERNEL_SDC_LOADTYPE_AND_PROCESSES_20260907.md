# 179 号核内核态 SDC 负载类型记录 — "全核满载守护进程推进" 触发配方

日期: 2026-09-07
关联: docs/CORE179_PANIC_EVIDENCE_CHAIN_20260907.md (证据链总报告)
关联测试: neon_rot_ldr_at_top (misc/) + arm0102_kreg_mask (arm-0102/) 双测试组合

## 一、负载类型定义 (这是第 4 类被坐实的 179 触发负载)

**负载类型: 全核满载双测试组合 (用户态 SDC 配方) → OS 守护进程被调度上 179 → 内核态取数错误**

之前三类已坐实的 179 SDC 表现:
1. 用户态数据 miscompare (movbe/mrn_rmw/NEON 系列探针, 本仓库主体工作)
2. 内核态 spurious translation fault (WARN, 可恢复)
3. 内核态致命 translation fault → Oops → panic → kdump → 重启 (本负载类型)

本负载类型的新颖点: **触发 179 内核态错误的不是测试线程本身, 而是被满载负载
"推上" 179 的无关 OS 守护进程**。测试提供的是全核压力这个"环境条件", 不是错误现场。

## 二、触发配方 (可复现)

```
./builddir/opendcdiag -e neon_rot_ldr_at_top -e arm0102_kreg_mask \
    -n 191..192 --ignore-os-error --ignore-timeout -T forever -o <log> -q
```

必要条件:
1. **全核 (或近全核) 线程数** — ld1 逼近核数 (sar 实测死前 150~190)。
   满载使调度器把所有 runnable 进程 (含守护进程) 摊到包括 179 在内的所有核。
2. **用户态 SDC 触发配方双测试** — 这两个测试是已验证的 179 用户态触发器
   (neon_rot_ldr_at_top: 3rd-ldr 位置探针; arm0102_kreg_mask: 比较类稀疏掩码),
   但对内核态错误而言, 任何能吃满全核的计算负载理论上等效 —
   未做等效性对照 (是否必须这两个测试、还是任意满载即可, 未验证)。
3. **179 在调度器内** — cpuset 排除无效 (只约束 opendcdiag 线程);
   必须 hotplug 下线 (`echo 0 > /sys/devices/system/cpu/cpu179/online`) 才能阻断。

失败判据 (软件层, 全部无 MCE/RAS 硬件报错):
- `Ignoring spurious kernel translation fault` WARN (前奏, 高频出现)
- `Unable to handle kernel paging request` → `Internal error: Oops` → panic → 重启

时间窗口: run 启动后 1~16 分钟内 (4 次实测: 13:51/15:16/17:13/20:04;
09-04 三次: 09:15/10:27/11:00)。**满载不必然死, 死时必然满载** (概率事件:
守护进程在 179 上暴露时长 ∝ 负载时长, 错误命中致命路径是概率)。

正向控制: hotplug 下线 179 后同样负载 24+ 分钟存活 (超过全部历史死亡窗口)。

## 三、179 上出错的进程完整清单 (kdump vmcore + /var/log/messages 追溯)

### 3.1 致命 panic (Oops → kdump → 重启), 全部 CPU 179

| 时间 | 进程 | 角色 | 错误 | vmcore |
|---|---|---|---|---|
| 09-04 09:15 | kworker/u392:0 | 内核工作队列 | Oops (前奏: rcu_sched spurious) | 2026-09-04-09:15:42 |
| 09-04 10:27 | sftp-server | SFTP 服务 | Oops (前奏: rcu_sched spurious ×2) | 2026-09-04-10:27:58 |
| 09-04 11:00 | sftp-server | SFTP 服务 | Unable to handle kernel paging request | 2026-09-04-11:00:00 |
| 09-04 21:53 | mi-scavenger | 内存巡检守护 | Oops (前奏: pmdalinux spurious ×2) | 2026-09-04-21:53:28 |
| 09-04 22:27 | rcu_sched | RCU 内核线程 | Oops (前奏: irqbalance spurious ×2) | 2026-09-04-22:27:27 |
| 09-04 22:39 | NetworkManager | 网络管理守护 | Oops (前奏: pmdalinux spurious ×2) | 2026-09-04-22:39:38 |
| 09-04 23:37 | systemd-coredum | coredump 服务 | NULL pointer deref (8) | 2026-09-04-23:37:57 |
| 09-07 13:51 | mi-scavenger | 内存巡检守护 | paging request, level 2 (FSC 0x06) | 2026-09-07-13:51:42 |
| 09-07 15:16 | HeapHelper | 内存巡检 helper | paging request (FSC 0x04) | 2026-09-07-15:16:31 |
| 09-07 17:13 | HeapHelper | 内存巡检 helper | paging request (FSC 0x04) | 2026-09-07-17:13:15 |
| 09-07 20:04 | mi-scavenger | 内存巡检守护 | paging request, level 3 (FSC 0x07) | 2026-09-07-20:04:26 |

例外: 09-04 22:09 panic 在 **CPU 168** (systemd-journal, `__list_add_valid_or_report`
链表损坏) — 唯一非 179 案例, 疑 179 脏写污染共享数据外溢, 待 crash 分析。

### 3.2 spurious translation fault WARN (可恢复前奏), 45 例全 CPU 179

| 进程 | 例数 | 路径特征 |
|---|---|---|
| irqbalance | 25 | 读 /proc/interrupts (show_interrupts → seq_printf → __memcpy) |
| pmdalinux | 20 | 读 /proc/interrupts (同上栈) |

时间分布: 09-05 09:01–19:36 共 37 例; 09-07 20:00:59–20:01:26 共 8 例
(后者为 cpuset 排除 179 的 run — 证明 cpuset 拦不住守护进程)。

09-04 vmcore 中另有 (死前同 boot 内): rcu_sched, ps, irqbalance, pmdalinux。

### 3.3 进程共性分析

- **全部是周期性读内核接口的守护进程**: /proc/interrupts (irqbalance/pmdalinux),
  内存巡检扫描 (mi-scavenger/HeapHelper — 深度遍历进程内存, 大量内核态页表操作),
  RCU 回调 (rcu_sched), kworker, 网络事件 (NetworkManager), coredump, sftp IO。
- **无一 opendcdiag 线程**: 测试线程自身报错只会是用户态 miscompare (result: fail),
  从不 panic — panic 的永远是同机守护进程。
- 高频读者 (irqbalance 每 ~10s, pmdalinux 每 ~60s, mi-scavenger 周期巡检)
  = 在 179 上暴露概率最大的进程 = 最常见的致命者。

## 四、写成的测试用例

`tests/cpu/misc/core179_kernel_sdc_repro.cpp` — 测试名 `core179_kernel_sdc_repro`。
设计原则:
- 复刻触发配方的"环境条件"部分: 全核满载的用户态 SDC 双配方负载
  (neon_rot_ldr_at_top 骨架 + arm0102_kreg_mask 比较类负载交替);
- 用户态部分自带 miscompare 检测 (result: fail 报告, 既有检测通道);
- 内核态部分 (spurious fault / panic) 无法在测试内断言 — 由运行者观察
  journalctl/vmcore; 测试的职责是把 179 上的内核态错误"逼出来";
- 文档头注明: 需 179 在线才会触发; 用作诊断时严禁 hotplug 下线 179;
  用作回归时必须先 hotplug 下线 179 (否则会 panic 打断整机测试)。

运行:
```
# 诊断模式 (故意让 179 在线, 复现内核态 SDC/panic):
./builddir/opendcdiag -e core179_kernel_sdc_repro -n 192 -T forever \
    --ignore-os-error --ignore-timeout -o repro.log -q
# 观察软件层: journalctl -k | grep -E 'spurious|Oops|panic'; ls /home/sdc/vmcore/

# 安全模式 (179 已 hotplug 下线, 只测用户态 SDC 部分):
echo 0 > /sys/devices/system/cpu/cpu179/online
./builddiag -e core179_kernel_sdc_repro -n 191 ...
```
