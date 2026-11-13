# adaptive_mem_sdc 首役——自适应 30 组合扫描，SDC 即停即报（2026-11-13 22:02-22:37）

## 任务（用户批准的 v2 设计）

单测试用例自动完成：探测最宽 SIMD（SVE2>SVE>NEON）→ 按 30 组合优先级序列每组合
30min 墙钟扫描（数据类型>ldr>str>负载）→ SDC 即停并报告组合。掩码 96-189（CPU3+CPU4，
-n 94，179 参测），AUTO 风扇，bin = **4a4d12c8e5d3**（NEON 路径；SVE/SVE2 引擎编译期
就绪，本机 HWCAP 不选）。

## 结果：SDC_CAUGHT——combo#1 上线 2 分 51 秒捕获

| 项 | 值 |
|---|---|
| 命中组合 | **combo#1 [NEON/fp64/ldr2/str3/fp64rot]**（优先级序列第 2 项） |
| 检出时刻 | 2026-11-13 22:37:36（combo 1 于 22:34:45 接管） |
| fail 块 / miscompare | **1 = 1（两法交叉）**——恰好一个 fail 块 |
| 归因（id 行三字段互证） | **logical 179 / numa_node 7 / core 179**，thread 83（=96+83 掩码位一致），cpu-mask X@83 |
| seed | LCG:574738641（auto，未固定） |
| 子进程 time-to-fail | 19.299s |
| 即停 | 看门狗 10s 轮询 → SIGKILL 主进程 868794 + pgrep 验证 → opendcdiag stopped ✓ |

### 组合时间线（covfile 实证）

| 组合 | 窗口 | 子进程 init 数 | 结果 |
|---|---|---|---|
| combo#0 fp64/ldr2/**str2**/fp64rot（冠军配方） | 22:04:45-22:34:45（满 30min） | 1,383,304 | **0 fail——本窗口休眠** |
| combo#1 fp64/ldr2/**str3**/fp64rot | 22:34:45-22:37:36（2m51s） | 143,350 | **捕获 SDC（core 179）** |

**自适应降阶的价值被首轮就证明**：本机历史冠军配方（str2，5.62/min 池化基线）在本窗口
休眠整 30min 零检出，若按旧范式单配方跑只会收获 0；序列第 2 项（str3——整数 str3 历史有效
~3.3/min、FP64 str3 本役首测）2m51s 即中。触发窗口在 str2/str3 之间的漂移本身是新数据点。

## 阶段 1 verify（正式役内）

179 下线 30 组合轮扫 60s：**0 fail!!!（两法交叉）+ 30/30 组合覆盖**，ISA=NEON 唯一标签。

## 实现期关键发现：sNaN 双副本根因（本测试 verify 门 RED→修复）

- **根因**：双 sNaN lane 输入的 fadd/fmul/fmax，GCC 交换律重排使 golden 冷循环与热循环
  两个内联副本排出不同操作数序；AArch64 对双 NaN 返回 "quieted 操作数 1" → 同源码两副本
  位结果分歧（p≈1e-4/调用）。铁证：E.lane0=quiet(A.lane0)、dst.lane0=quiet(B.lane0)。
- **修复**：FP64 段填充 NaN-free（指数全 1 → 清 bit62）；93 线程复现器 ~1e4 轮必现 →
  **3.01e8 轮零失配**；设计文档附录 v2.1 在案。
- **⚠️ 家族父版埋同款雷待立案**：`neon_rot_ldr_at_top_rowmajor_fp64*`（裸 NaN 数据 +
  init/热双副本）至今未炸纯属两副本操作数序碰巧一致，任何重编译可能翻车。

## 工程门（全部通过）

1. 零警告编译（SVE TU 含，armv9-a+sve2 探针回退链在 meson）；30+30 实例化符号
2. objdump：NEON 实例 0 与 fp64 父版编码同构（3 ldr/四槽轮换/背靠背 str 组/共享落点）；
   empty 槽 8 ldr **零 ALU**（DCE 护栏）；FP64 ldr3 零 fmadd；mla 分解式与父版逐槽一致
3. verify：30 组合 × 多 seed golden 全 0!!!（两次独立跑）
4. 运行期分发：本机 isa=NEON 唯一（SVE 引擎链接在场但休眠）
5. 二进制备份 backups/20261113_adaptive_4a4d12c8e5d3/（含三源文件）

## 跨机器就绪度

- 920（本机）：NEON 路径首役验证 ✓
- 920B/950：SVE/SVE2 引擎编译期就绪、objdump 编码门过；运行时验证属后续战役
  （spec §8 原文：本机无 SVE 硬件，无法执行验证）

## 数据文件

`/home/sdc/adaptive_mem_sdc/`：phase1/（verify，STATUS=done）、phase2/（正式役，
STATUS=sdc_caught，run.log/covfile.txt/temp_all.log/env_logger.out/monitor.log）；
`series_summary.txt`；脚本 `docs/20261113/adaptive_mem_sdc/run_adaptive.sh`；
台账 `.superpowers/sdd/2026-11-13-adaptive-mem-sdc/progress.md`（全部裁定在案）。
