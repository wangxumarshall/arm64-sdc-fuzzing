# spinlock 探针 179 阳性对照 · 第一轮结果与修正（2026-10-30 18:31-19:46）

## 一、三阶段结果

| 阶段 | 结果 | 有效性 |
|---|---|---|
| 1. spinlock_stale_read（CAS 臂）30m | 0 fail / 0 遥测 | **exposure-invalid**（自旋被饿死，见 §二） |
| 2. spinlock_stale_read_xchg（xchg 臂）30m | 0 fail / 0 遥测 | **exposure-invalid**（同上） |
| 3. neon_rot_ldr_at_top_rowmajor 15m（基线 a05c1763） | **148 fail = 9.87/min，148/148 logical 179** | **有效——179 今晚活跃** |

## 二、自旋饿死事故（CPU 占用率常设规则上岗 50 分钟后当场抓获）

- **定量证据**：CPU 占用采样（19:22 起，/proc/stat 分插槽）——阶段 2 期 CPU4 平均 **5%**，对照阶段 3 rowmajor **avg 39% / max 95%**；CPU4 温度全程钉 48°C（空载水平）
- **阻塞点**：主进程 D 状态，wchan=`jbd2_log_wait_commit`，内核栈 `fdatasync → ext4_sync_file → jbd2_complete_transaction`
- **根因**：框架**每次** `test_time_condition()` 调用都把日志块 fdatasync 到 -o 文件；探针原设计**每圈自旋调一次** → 在 ext4 上每圈等一次日志提交 → 占空比塌至 ~0.3-5%，**暴露量≈设计的 10⁻⁷**
- **冒烟为何漏检**：冒烟日志写 /tmp = tmpfs（内存盘），无同步开销——**教训：冒烟必须与正式 run 同文件系统**
- **修复**：自旋改 2²⁵ 圈（~0.5s）批次才碰一次框架调用（`SPIN_BATCH`），两文件已改、重建通过
- **排除项**：内存 753GB 空闲、无 swap 活动；dmesg 无 I/O 错误；dmesg 中 CPU179 kill/boot 事件锚定为当日三轮冒烟（13:36-13:39），无第三方动 179

## 三、电压/CPU 占用（全程记录）

- N_VDDAVS_CPU4：0.960V×516 / 0.970V×22；Power 666-768W 均值 693W——**无异常**
- CPU 占用率：阶段 2 avg 5%（饿死证据）vs 阶段 3 avg 39% / max 95%（真实负载）——新常设规则的首轮实战数据

## 四、重跑（probe_run2.sh）

批次修复版探针、两臂各 30m、同掩码同种子策略、`scripts/sdc_env_logger.sh` 从 t0 记电压+CPU 占用。**179 活跃已由阶段 3 确认（9.87/min）**——重跑若零检出即为"满暴露量下的有意义阴性"（179 的 L1D 错值模式不走锁字原子/普通读路径）；若检出即阳性对照成立。

数据：本目录 `summary.csv` / `runs/` / `monitor.log` / `voltage.log` / `cpu_util.log`（19:22 起）。

## 五、RUN2 终局（批次修复版，19:51:47-20:51:12）

| 阶段 | 结果 | 占空比证据 |
|---|---|---|
| spinlock_stale_read（CAS 臂）30m | **0 fail / 0 遥测**，rc=0 | **CPU4 平均 93%**（495 样本，354 个 ≥90%） |
| spinlock_stale_read_xchg（xchg 臂）30m | **0 fail / 0 遥测**，rc=0 | 同窗口满载，温度 50-51°C |

- 电压/功率全窗：N_VDDAVS_CPU4 0.960V×393 / 0.970V×13；Power 678-720W 均值 698W——无异常
- 遥测良性基线（满速工况）：两臂均 0 行 @ floor 128

**终局判决：满暴露量下的有意义阴性。** 179 活跃当晚（同晚 rowmajor 148f/9.87/min 全 logical 179 确证）、探针满占空比（93%）跑满两臂各 30min，三判据（锁字值损坏 ∉{0,1} / 连续陈旧自旋 ≥4096 / 丢失更新）零触发。**179 的 L1D 错值缺陷不经由锁字的原子 RMW 读路径或普通 LDR 读路径表达**——其触发需要 ≥2 源 load + ALU 轮换 + 紧时序的 footprint 结构（触发配方），单 cache line 锁字的访问模式不复现。差分臂（CAS vs SWPAL）双阴，无从分离亦无需分离。

**探针的实战定位**：针对"多核自旋于空闲锁"症状（它机报障）的检测能力完好——该症状若为真·陈旧读/原子路径故障，判据 ①②③ 会抓；对 179 类 L1D footprint 缺陷则不敏感（本实验定量了这个边界）。
