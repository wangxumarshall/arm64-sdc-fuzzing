# 179 号核死机根因定位 — 11 次 panic 同指令崩溃 + 调度器 load-balance 读路径（vmcore 证据链）

日期：2026-09-12
证据源：`/home/sdc/vmcore/`（29 份 kdump，2026-08-14 ~ 09-12）+ debug vmlinux
`/usr/lib/debug/usr/lib/modules/6.6.0-145.3.23.154.oe2403sp3.aarch64/vmlinux` 反汇编
关联：
- `docs/CORE179_PANIC_EVIDENCE_CHAIN_20260907.md`（软件层证据链，本文修正其"守护进程被推上 179"的归因粒度）
- `docs/CORE179_179_vs_180_VISITOR_OBSERVATION_20260908.md`（180 访客对照基线）
- `docs/CORE179_KERNEL_SDC_LOADTYPE_AND_PROCESSES_20260907.md`（负载类型与受害者清单）
- 用户态 SDC 系列（movbe/mrn_rmw/neon_rot）：docs/CORE179_SDC_L1D_EXCLUSION_AND_INSTRUCTION_LOCALIZATION.md 等

---

## 一、结论（先答问题）

**11 次致命 panic 全部死在同一条指令上：调度器负载均衡 `find_busiest_group+0x140` 读取
per-CPU runqueue 统计的那条 `ldr`。**

- 崩溃点统一：`find_busiest_group+0x140/0xb60`（11/11 例，跨 6 天、跨 8 种不同受害者进程）
- 出错指令（vmcore `Code:` 行括号内）：`ldr x23, [x27, #0x120]`（机器码 `f9409377`）
- 寄存器交叉验证：x27 + 0x120 精确等于报错地址（例：09-07 15:16，x27=ffdbc44e0c5e97bf +
  0x120 = ffdbc44e0c5e98df = 报错地址 ✓）
- 该指令在访问：per-CPU `runqueues`（`rq->cfs` 的负载统计字段，load-balance 求和路径）

**受害进程的"共性"从来不是它们是什么负载，而是它们恰好在 179 上触发了调度器的
load-balance 路径。** 错误的物理来源仍是 179 的 load 读路径随机错值（与用户态 SDC 同源）；
错值落在 `find_busiest_group` 的 runqueue 统计读上 → 后续解引用坏指针 → level 0/2/3
翻译错误 → Oops → panic。

这把 09-07 报告"全核负载把守护进程推上 179 → 179 上内核态访存错"的归因再下钻一层：
**不是守护进程自己的访存错，而是调度器为它们算负载时读错**。守护进程只是"乘客"，
司机是 `find_busiest_group`。

---

## 二、11 次致命 panic 的统一栈（vmcore 逐一核对）

完整调用栈（11 例逐字相同，仅系统调用入口不同）：

```
find_busiest_group+0x140/0xb60     ← 崩溃点（读 runqueue 统计, ldr x23,[x27,#0x120]）
load_balance+0x108/0x6c0
newidle_balance+0x198/0x510        ← newidle 负载均衡（CPU 即将转空闲时触发）
pick_next_task_fair+0x110/0x718
pick_next_task+0x60/0x398
__schedule+0x1b4/0x8a0
schedule+0x58/0x130
（以下因进程而异：futex_wait_queue / do_task_dead 等睡眠、退出路径）
```

致命案例全表（`Unable to handle kernel paging request` → Oops → kdump）：

| # | 时间 | 致命进程 | FSC | 报错地址尾 | 调度入口 |
|---|---|---|---|---|---|
| 1 | 09-04 11:00 | sftp-server | 0x06 (L2) | 97e0 | — |
| 2 | 09-07 13:51 | mi-scavenger | 0x06 (L2) | 97e0 | — |
| 3 | 09-07 15:16 | HeapHelper | 0x04 (L0) | 98df | futex_wait |
| 4 | 09-07 17:13 | HeapHelper | 0x04 (L0) | 119f | — |
| 5 | 09-07 20:04 | mi-scavenger | 0x07 (L3) | 97e0 | — |
| 6 | 09-11 14:31 | mi-scavenger | 0x04 (L0) | 3c9d | — |
| 7 | 09-11 16:30 | mi-scavenger | 0x04 (L0) | 98df | — |
| 8 | 09-11 17:06 | kworker/179:1 | 0x04 (L0) | 3a20 | — |
| 9 | 09-11 17:58 | mi-scavenger | 0x06 (L2) | 97e0 | — |
| 10 | 09-12 00:09 前后 | （见 WARNING 群） | 0x04 | — | — |
| 11 | **09-12 10:00** | **neon_rot_ldr_at_top 测试线程** | 0x04 (L0) | 66ac | **do_task_dead（线程退出！）** |

（09-04 21:53 / 22:27 / 22:39 三例为同日 WARNING→Oops 链，连同 09-08 17:21、09-12
00:09、10:00 的 WARNING 前奏，见第三节。）

三个跨案例指纹：

1. **同一崩溃点**：`find_busiest_group+0x140`，11/11，无一例外。
2. **同一出错指令**：`Code: f9400782 f879d814 2a1903e0 8b14003b (f9409377)` —
   括号内 `f9409377` = `ldr x23, [x27, #0x120]`，全部样本一致。
3. **报错地址形态**：全部是"介于用户与内核地址范围之间"的非规范地址
   （`ffdbc44e...`、`003fd531...`、`0026bb43...`），内核日志明确标注
   `address between user and kernel address ranges`。这些不是任何真实映射的地址 —
   是**读 runqueue 统计时拿到随机垃圾值再当指针/偏移用**的产物。
   注意地址尾 16bit 反复出现 97e0/98df（4/11 例尾缀 97e0、2/11 例 98df）— 与用户态
   SDC"尾数位主导"的位翻转统计同构（样本量小，记录待查，不下结论）。

## 三、可恢复前奏：__do_kernel_fault WARNING 群（同一根因的温和形态）

与致命栈配对的是大量可恢复 WARNING（`arch/arm64/mm/fault.c:494 __do_kernel_fault`）：

```
__do_kernel_fault+0x130/0x1b8      ← WARNING 点
do_bad_area → do_translation_fault → do_mem_abort → el1_abort → el1h_64_sync
```

受害者：pmdalinux、irqbalance、rcu_sched、ps（全部 CPU 179，与既有 45 例 spurious
fault 清单一致）。语义：翻译错误发生但落在可重试/可忽略区域 → WARN 继续。
09-12 10:00 的 vmcore 完整记录了"前奏→致命"链：pmdalinux 先 WARNING（34323s），
neon_rot 测试线程最终在 do_task_dead→__schedule→newidle_balance 路径上崩掉（34999s）。

**同一错误源的显形谱系**（强度递增）：

| 形态 | 表现 | 错值落点 |
|---|---|---|
| 用户态 SDC | miscompare（result: fail，全 179） | 被测 load 的返回值 |
| spurious fault | `__do_kernel_fault` WARNING，可恢复 | 内核态指针（重试即对） |
| fatal panic | `find_busiest_group+0x140` Oops | load-balance 的统计读 → 坏指针 |

## 四、出错指令在访问什么（vmlinux 反汇编）

`find_busiest_group+0x100~0x150` 反汇编（debug vmlinux，符号已核对：
`__per_cpu_offset = ffff800081f655d0`、`runqueues = ffff800081b696c0`）：

```asm
ffff80008013ae10:  ldr  x0, [sp]                 ; sched_group_cpus 指针
ffff80008013ae18:  ldr  x1, [x19, #56]
ffff80008013ae1c:  ldr  w2, [x21]
ffff80008013ae20:  bl   _find_next_and_bit       ; 遍历组内 CPU 位图
ffff80008013ae24:  mov  x25, x0                  ; x25 = 下一个 CPU 号
...
ffff80008013ae34:  ldp  x0, x1, [sp, #8]         ; x0 = __per_cpu_offset 数组基址
                                                ; x1 = runqueues 偏移
ffff80008013ae38:  ldr  x2, [x28, #8]            ; 局部统计累加器
ffff80008013ae3c:  ldr  x20, [x0, w25, sxtw #3]  ; ★ x20 = __per_cpu_offset[cpu] ← 读错点候选
ffff80008013ae44:  add  x27, x1, x20             ; x27 = &runqueues[cpu]
ffff80008013ae48:  ldr  x23, [x27, #288]         ; ★★ 崩溃点：rq->cfs 负载统计
```

崩溃链：`ldr x20, [x0, w25, sxtw #3]`（读 `__per_cpu_offset[cpu]`，L1D 命中的普通数据
读）**拿到错值** → `add x27` 组装出垃圾地址 → `ldr x23, [x27, #288]` 翻译错误 → Oops。

**关键性质：`__per_cpu_offset[]` 是常驻 L1D 的内核数据数组，这条读是普通的、可被
179 的 load 路径随机错值命中的读** — 与用户态 SDC 的触发形态（L1D 域 load 低概率
随机错）完全同构。179 的用户态故障（load 路径随机错值，尾数位主导）在内核态的投影，
恰好砸在调度器最热的读路径上，就是死机。

## 五、对既有假说的裁决（对照"180 访客基线"排查框架）

09-08 访客普查（180 健康对照）曾给出排查维度，vmcore 证据逐一裁决：

| 假说（基于 180 基线对比框架） | 裁决 | 依据 |
|---|---|---|
| 179 上"多出的任务"导致死机 | **否** | 8 种受害者进程无共性；opendcdiag 线程、守护进程、内核线程都会死 |
| "历史 panic 受害者"进程身份异常活跃 | **否** | mi-scavenger 4 次只是因为它被调度得多；任何进程在 179 上睡眠/退出都可能当"乘客" |
| RCU 停滞 / soft lockup | **否** | 无任何 RCU stall / lockup 栈；rcu_sched 只是 WARNING 受害者 |
| 任务长期占 CPU（死循环） | **否** | 崩溃全部发生在**让出 CPU 的路上**（newidle_balance = CPU 要转空闲） |
| 中断分布异常 | 未发现 | vmcore 无中断风暴痕迹 |

正确的共性维度不是"谁在跑"，而是"**调度器在 179 上为谁算负载**"。

## 六、为什么"满载不必然死，死时必然满载"得到精确解释

`newidle_balance` 的触发条件：CPU 即将进入空闲（prev 睡眠/退出）时主动拉活干。全核
满载时 179 上每秒发生成千上万次线程切换/睡眠/退出，每次都走一遍
`find_busiest_group` 的 per-CPU 统计读 → 179 的错值概率 × 巨大尝试次数 = 概率性命中
关键读 → panic。这解释了：

- 09-08 三小时满载 179 零死机（错值是 ~1e-6 量级低概率事件，3h 未命中而已）
- 死亡窗口 1~16 分钟的巨大方差（泊松过程，与负载强度相关）
- hotplug 下线 179 后 100% 存活（179 不调度 = find_busiest_group 从不在 179 上执行）
- cpuset 排除无效（cpuset 只约束 opendcdiag 线程；守护进程照样在 179 上睡眠/唤醒，
 照样触发 newidle_balance）

**有效刺激器推论**：复现死机不需要特定守护进程负载 — 需要的是 179 上的**调度活动
本身**。高频 sched_yield()/futex 睡眠-唤醒循环、短命线程创建-销毁，就是最直接的
newidle_balance 触发器（opendcdiag 的 fork_each_test + 192 线程模型已无意中验证：
#11 例的致命进程就是测试线程自己，死在 do_task_dead→__schedule 路径上）。

## 七、09-12 10:00 死机的重新归档（本次新发现）

此前记为"关机截断 ldr4 战役"。vmcore 证据：

- 34323s：pmdalinux 在 179 上 `__do_kernel_fault` WARNING（前奏）
- 34999s：**neon_rot_ldr_at_top 测试线程**（PID 741633）在 `do_task_dead →
  __schedule → newidle_balance → find_busiest_group+0x140` 上致命崩溃（FSC 0x04，
  报错地址 003fd531b2dc66ac，非规范地址）
- 即：**ldr4 战役 09:59:46 的截断不是无关关机，而是第 11 次 179 panic**（当时已入账
  29 fail 全 179，数据有效性不受影响；"关机"应改记为 179 panic）

ldr4 战役 24.9min 的数据口径保留（29 fail / 24.9min），但需注明：截断原因 = 179
panic，与 ldr5/str4_checkall 轮的 30min 完整窗口不同口径。

## 八、修复与实验建议

1. **死机复现刺激器（单核、可控）**：`taskset -c 179` 上跑高频调度循环
   （sched_yield / futex wait-wake / pthread create-join），180 对照。
   预期：单核调度风暴即可概率复现 `find_busiest_group` Oops，无需全核满载。
   （比此前计划的"逐守护进程负载刺激器"更接近根因路径。）
2. **既有守护进程负载刺激器计划修正**：/proc 读循环、缺页风暴两类刺激器对
   `find_busiest_group` 路径无特异性 — 它们的价值降级为"用户态/温和内核态错误探针"。
3. **L1D ECC/RAS 判据不变**：零扰动判据仍以硬件 RAS 通道为准（软件层已闭环到
   指令级：`ldr x20, [x0, w25, sxtw #3]` 读 `__per_cpu_offset[]` 错值）。
4. **`crash` + vmcore 内存映像分析**可进一步确认：崩溃瞬间 `__per_cpu_offset[cpu]`
   的实际内存值 vs x20 读到的值（若内存值正确而 x20 错 = 读路径错实锤；若内存值
   本身坏 = 写路径/真实内存坏）。这是用户态 recompute 判据的内核态等价物。
   ——本报告未做此步（需要 crash 工具链），是当前证据链的最后一块开口。

## 九、边界与保留

- "x20 读 `__per_cpu_offset[]` 拿到错值"是从崩溃点 + 寄存器值的**推导**，不是直接
  观测（直接观测需第八节第 4 条的 crash 分析）。替代解释（x25 CPU 号错、x1 偏移错）
  不能完全排除，但都被"报错地址 = 随机垃圾值形态"间接约束。
- 尾缀 97e0/98df 的重复（6/11 例）样本量不足以做位模式结论，仅记录。
- FSC 层级（L0/L2/L3 散布）在"读错值当指针用"模型下自然成立（垃圾值指向任意层级
  未映射区间），与"PTW 各级独立故障"的旧解释二选一，新模型更简约。
