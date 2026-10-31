# 09-08 第二次宕机: dump 捕获 run 期间的 179 panic (vmcore 铁证)

日期: 2026-09-08
数据来源:
- `/home/sdc/vmcore/127.0.0.1-2026-09-08-17:21:33/vmcore-dmesg.txt` (本次 kdump)
- `builddir/run_dump_capture.log` (run 1, 16:48–17:06)
- `builddir/run_dump_capture2.log` (run 2, 17:06–17:20, 死于 panic)
- `/home/sdc/dump_capture_20260908/` (run 1 幸存的 55 条 dump 记录)
状态: 宕机因果闭环 (与 09-07 证据链同构); run 2 的 26 fail dump 记录丢失 (tmpfs)

## 一、事件概述

为回答"179 算错了什么", 当天制作了两个 dump 变体测试
(`neon_rot_ldr_at_top_dump` / `arm0102_kreg_mask_dump`, 模式沿用 movbe_dump:
热循环字节一致 + dump 只进冷分支), 并启动全核捕获 campaign。
**campaign 进行中 (run 2 启动后 ~15 分钟) 机器再次 panic 重启** —— 第 5 次
kdump 铁证的 179 宕机, 也是首次带有完整前置 WARNING 链的一次。

## 二、时间线 (墙钟, 由 uptime 换算, boot=09-07 20:09:45)

| 时间 | 事件 | CPU | 进程 | 后果 |
|---|---|---|---|---|
| 16:48:07 | run 1 启动 (双 dump 测试, -n 192, forever) | — | opendcdiag | — |
| 16:48:28 | WARNING #1 `__do_kernel_fault` | **179** | pmdalinux | 存活 |
| 16:56:21 | WARNING #2 `__do_kernel_fault` | **179** | irqbalance | 存活 |
| 17:06:42 | run 2 重启 (cpu 字段修正后的二进制) | — | opendcdiag | — |
| 17:08:28 | WARNING #3 + spurious fault | **179** | pmdalinux | 存活 |
| **17:20:59** | **Oops: kernel paging request** | **179** | mi-scavenger | **panic → kdump** |
| 17:21:33 | kdump vmcore 落盘 | — | — | — |
| 17:25 | SSH 断连 (观察端) | — | — | — |
| 17:27:09 | 系统重启完成 | — | — | 179 恢复在线 |

关键对齐: WARNING #1 出现在 run 1 启动后 **21 秒**; Oops 出现在 run 2 日志
最后一条 (17:20:47, iteration 338) 后 **12 秒**。负载窗口与内核错误窗口完全重合。

## 三、Oops 本体 (vmcore-dmesg 76274s)

```
Unable to handle kernel paging request at virtual address d3eafc3c10eb97df
  [d3eafc3c10eb97df] address between user and kernel address ranges
Internal error: Oops: 0000000096000004 [#1] SMP
CPU: 179  PID: 2795884  Comm: mi-scavenger
pc : find_busiest_group+0x140/0xb60     ← 调度器负载均衡
lr : find_busiest_group+0x11c/0xb60
x27: d3eafc3c10eb96bf                    ← 被 deref 的坏指针
x20: d3eb5026e000ffff                    ← 高位损坏值
Call trace: find_busiest_group → load_balance → newidle_balance
            → pick_next_task_fair → __schedule → futex_wait (mi-scavenger 睡醒被调度)
```

- 坏地址 `d3eafc3c10eb97df` 是非规范垃圾指针 (介于用户/内核区间之间),
  来自 179 上内核态数据损坏 —— 与 09-07 四次 panic 同一性质。
- 受害者又是无关守护进程 (mi-scavenger, futex 睡醒后恰被调度上 179)。
- 注意 x20 = `d3eb5026e000ffff`: 与三次 WARNING 现场的 x3 = `ffffd3eb50934000`
  共享 `d3eb...` 高位模式 —— 四次事件损坏值指纹一致, 指向同一错误源。

## 四、前置 WARNING 链 (三次, 全 179)

| # | 墙钟 | 进程 | 栈 | 性质 |
|---|---|---|---|---|
| 1 | 16:48:28 | pmdalinux | show_interrupts → seq_printf → __memcpy | 内核态读 /proc/interrupts 翻译错 |
| 2 | 16:56:21 | irqbalance | show_interrupts → seq_printf → __memcpy | 同上 |
| 3 | 17:08:28 | pmdalinux | 同 #1, 前一条为 spurious fault (`ffff604005ce6450`) | 同上, 且紧跟"重译成功"案例 |

与 09-07 存档的 45 例 spurious fault 完全同构: 全 179、全 /proc/interrupts
读者、同一 show_interrupts→__memcpy 栈。**本次新观察: 三次 WARNING 与最终
Oops 相隔 8~32 分钟, 构成"重试可恢复 → 不可恢复"的完整 escalation 链。**

## 五、捕获 run 的得失

### 5.1 得: run 1 的 55 条错值记录 (幸存, 已存档)

run 1 (16:48–17:06, ~18 min) 产出 41 个 fail、55 条二进制 dump 记录。
`dump_capture_20260908/` 下解析结果:

- **55/55 记录 golden 与"重读源重算"一致** —— srcA/srcB 数据本身从未坏,
  golden 从未坏, **坏的是热循环里实际算出的 act (0/55 等于重算值)**。
  即: 错误不在 init 侧, 不在源数据, 就在热循环执行中。
- op 分布: add 26 / eor 17 / and 7 / orr 5 (与 i%4 均匀轮换的期望比例一致,
  四种 ALU 全中招, 非单一指令特异)。
- index 分布: idx 0 (23 次) + idx 1 (13 次) 占 36/55, 其余 19 条散布在
  全 1024 范围 —— 偏向前两个 index 但不限于 (与 09-01 "22测试 load 序列"
  观察到的首 index 偏好一致)。
- 无一发生在首轮迭代 (iter 最小 277) —— 需要热身/压力积累后才触发。
- xor 模式 (与 op 强相关):
  - **add (n=26)**: xor 高位密度显著 (hi popcount 平均 31.2/64),
    低位有连续干净字节 (13 例 0 字节干净, 其余 1–3 字节干净) ——
    **进位链低位开始坏、高位雪崩** 的形态;
  - **eor (n=17)**: xor popcount 低得多 (lo 13.7 / hi 7.1), 低位无一字节干净
    (17/17 低字节即脏) —— 少量位翻转形态;
  - and/orr: 中等 popcount, 接近随机损坏形态。

### 5.2 失: run 2 的 26 fail 记录 (tmpfs, 重启清空)

run 2 (17:06–17:20) 26 个 fail (cpu-mask X 位置全 179), dump 写在 `/tmp`
(tmpfs) —— **panic 重启后全部丢失**。run 2 的价值只剩 run_dump_capture2.log
的 fail 计数与日志行。

**教训: dump 落盘路径必须改到磁盘持久目录** (如 `/home/sdc/dump_capture/`),
/tmp 在每次宕机时都是归零风险 —— 而 dump campaign 恰恰是会把机器跑崩的实验。

## 六、与既有结论的关系

1. 第 5 次 panic 铁证, 依然全 179, 依然是无关守护进程受害, 依然无 MCE ——
   完全落在 [[core179-panic-evidence-chain-20260907]] 的因果框架内:
   全核压力 → 守护进程被推上 179 → 179 内核态取错数据 → panic。
2. 新增两点:
   - 完整 escalation 链 (3×WARNING → Oops, 32 分钟跨度) 首次被单一 vmcore 记录;
   - 四次事件损坏值共享 `d3eb...` 高位指纹 (x20/x3), 提示损坏数据可能
     源自同一物理存储位置 (待 crash 工具分析 vmcore 确认)。
3. dump 变体的触发率未掉 (run 1 ~2.3 fail/min, 与父测试同量级) ——
   "热循环字节一致 + dump 只进冷分支"设计再次经受实测检验。

## 七、未闭环 / 下一步

- [ ] **dump 路径改盘**: 两个 dump 变体的 open() 路径从 `/tmp/...` 改为
      `/home/sdc/dump_capture/...` (需 mkdir + 权限), 防下次 panic 再丢数据。
- [ ] **179 hotplug 下线后再跑捕获 campaign** —— 但注意: 179 下线后
      neon_rot_ldr_at_top 系不再产生 SDC (错误绑定 179), dump 变体的
      捕获只能在线 179 时进行。两难: 捕获 vs 存活。折中方案:
      接受"跑一次抓一批、崩了重启再跑"的节奏, 每轮 run 前把 /tmp 数据
      挪走没用 (panic 不给你机会), 必须 open 时就写盘上。
- [ ] crash 工具分析 17:21:33 vmcore: x20/x3 的 `d3eb...` 值的物理来源,
      find_busiest_group 读的 sched_group 指针链在哪坏。
- [ ] 55 条样本的 xor 模式 (add 高位雪崩 / eor 低位少翻转) 需扩样本验证
      (目标 100+), 机制解释候选: add 进位链 vs eor 纯组合逻辑的
      时序路径差异 —— 目前只记录现象, 不下机制结论
      ([[no-premature-conclusions-no-midtask-pushback]])。
