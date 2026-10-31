# CORE179 稳定性战役:neon_rot_ldr_at_top 三变体 3 轮复测(2026-09-09)

## 战役概况

- **目的**:检验 `neon_rot_ldr_at_top` 家族三变体触发 SDC 的稳定性(跨轮可复现性),并对比扫描顺序(rowmajor vs sub)与 dump 分支对触发率的影响。
- **时间**:2026-09-09 09:02:44 – 13:32:39 CST,共 4.5h。
- **命令**:`timeout 2100 taskset -c 0-191 ./builddir/opendcdiag -e <test> -n 192 -T 30m --ignore-os-error --ignore-timeout -o <log> -q`
- **布局**:3 变体 × 30min 串行为一轮,共 3 轮,全程全核 192 线程(0–191),auto seed(不固定 LCG seed)。
- **日志**:`builddir/campaign_20260909_stability/r{1,2,3}_<variant>.log`(共 9 份)。

## 主结果表

唯一 `result: fail` 块计数(计数规范见记忆 sdc-fail-count-unique-blocks,非 grep miscompare):

| 变体 | r1 | r2 | r3 | 合计 | 轮均值 |
|---|---|---|---|---|---|
| `neon_rot_ldr_at_top_rowmajor` | 276 | 244 | 149 | **669** | 223.0 |
| `neon_rot_ldr_at_top_rowmajor_dump` | 7 | 12 | 3 | **22** | 7.3 |
| `neon_rot_ldr_at_top_sub` | 122 | 90 | 116 | **328** | 109.3 |

## 核号分布

**9/9 份日志,所有 1019 个 fail 块,失败线程全部且仅有 thread 179。** 无一例其他核。

## 时间分布

- fails 在 30min 窗口内**均匀分布**,不是"前段爆发后沉默"形态。例(rowmajor r1,每 5min 桶):48/38/51/42/50/47;sub r3:28/23/17/19/17/12。
- dump 变体的 22 个 fail 的 time-to-fail 散布于 9s–805s 全窗口,同样无聚集形态(排除"只在开局热身段错"的解释)。
- fail 块间 seed 多样(LCG:2037548229、LCG:2080998949 等),与既有结论一致:触发对 seed 不敏感、非单一 seed 特异。

## 三点观察(事实层)

1. **rowmajor > sub,三轮方向一致**:r1 276>122、r2 244>90、r3 149>116,比值 1.3–2.3×。扫描顺序(rowmajor 交替扫描 vs sub 顺序扫描)稳定影响触发强度。
2. **dump 抑制效应跨三轮稳固**:rowmajor_dump 合计 22 vs rowmajor 669,约 **30×**。与 movbe/mrn_rmw 系列的"加 dump 冷分支就抑制"现象同构(见记忆 movbe-dump-compiler-dce-root-cause、dump-variant-noremove-report-fail-verified)。
3. **rowmajor 逐轮走低(276→244→149)但 sub 平稳(122→90→116)**:全场性衰减不成立(否则 sub 也该降);单变体趋势,本轮数据不足以归因,记录待查。

## 待办衔接

- 本战役的 rowmajor vs sub 对比部分覆盖了"预取器/替换模式"盲区(见记忆 untested-microarch-units-todo),但非干净单变量(两变体除扫描顺序外数据地址流亦不同),尚不能归因预取器。
- 其余盲区(MMU/TLB、LSQ 队列压力、RF 端口、ROB)未测。
