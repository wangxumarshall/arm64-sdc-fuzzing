# FARRON —— 在线 CPU SDC 健康管理系统

针对本机（长江计算 R240K V2，四路 Kunpeng 920，192 逻辑核，已知缺陷核 **179**）的在线 SDC 检测与处置系统。
设计规格见 `DESIGN.md`；完整技术流程见 `docs/CORE179_FARRON_SDC_DETECTION_WORKFLOW_20261026.md`。

**验证状态（2026-10-27）**：三形态全部通过——
检出 **12/12 轮 100%**（全锁 179，零误报）；生产节奏下应用吞吐损失 **1.815%**、FARRON 消耗 **0.88%**；端到端首检 ~2 分钟。

---

## 一、目录结构

| 文件 | 作用 |
|---|---|
| `deploy_prod6h.sh` | ⭐ **一键部署**：6h 生产节奏验证（含 stub 自检/基线/看门狗，全自动） |
| `prod_sweep.sh` | ⭐ **生产节奏扫描器**：每 30min 一轮逐插槽独占扫描（已验证的检出通道） |
| `deploy_prod6h_lat.sh` / `prod_sweep_lat.sh` | 时延版（含唤醒延迟探针迁移；设计完成尚未跑） |
| `latency_probe.py` | 唤醒延迟探针（50ms 睡眠超期，每秒聚合） |
| `farron.py` | 全系统主控 v1.0：温度控制器 + 三级用例池 + 深测 + 屏蔽/退役裁决 |
| `log_scanner.py` | 被动通道：journal 内核指纹预筛（≥3 条/核 → 直送可疑队列） |
| `testcase_pool.json` / `TESTCASE_POOL.md` | 用例池（57 活跃 P0-P4 / 83 基础 / 8 排除） |
| `cpu_total_sampler.sh` / `app_cpu_sampler.sh` | 全机 / 应用 CPU 采样（15s） |
| `temp_monitor_5s.sh` / `watchdog_cont.sh` | 温度监控（5s，绑核 0）/ 98°C×2 看门狗 |
| `eval_sweep.sh` | 背靠背极限评估形态（3h/5h 役用） |
| `per_core_sweep.sh` | 逐核原型（已被门控实验否定，仅留档） |
| `state/` | 运行数据：`state.json`、`farron.log`、`sweep/<各战役原始数据>` |

## 二、快速开始（三个入口）

### ① 一键验证部署（最常用）

```bash
bash /home/sdc/root/arm64-sdc-fuzzing/opendcdiag/farron/deploy_prod6h.sh
```

全自动流水线：残留清理 → stub 自检（~4min，新逻辑硬门禁，异常即中止）→ 空闲基线 60s →
拉起 stress-ng 191 worker → 每 30min 一轮扫描 6h → 双 CPU 采样 + 温度监控 + 看门狗。
结果落 `farron/state/sweep/prod6h/`。所有子进程 nohup，不依赖会话存活。

### ② 长期生产节奏（自定时长/周期）

```bash
bash farron/prod_sweep.sh <总秒数> <输出目录名> [周期秒，默认 1800]
# 例：连跑 30 天
nohup bash farron/prod_sweep.sh 2592000 prod30d 1800 > /dev/null 2>&1 & disown
```

### ③ 全系统主控（farron.py）

```bash
python3 farron/farron.py --selftest   # 规格自检（12/12）
python3 farron/farron.py --dry-run    # 全状态机模拟演示（不跑真负载）
python3 farron/farron.py              # 实机守护运行
python3 farron/farron.py --status     # 查看当前状态（可靠池/屏蔽/可疑队列/温度）
python3 farron/log_scanner.py --json  # 被动日志预筛
```

⚠️ **集成缺口**：`farron.py` 的 RealRunner 仍是"全池分时"形态，尚未接入已验证的插槽独占协议。
**跑真实负载下的检测请用入口 ①/②**；`farron.py` 当前用于温度自适应调度与深测/裁决框架。

## 三、运行时行为（每 30 分钟发生什么）

```
30min 周期
├── FARRON 醒 ~2 分钟（占空 6.65%）：
│     CPU1 窗30s → CPU2 窗30s → CPU3 窗30s → CPU4 窗30s（含179）
│     每窗：应用整插槽迁出(144核可用) → 48核独占跑检测器 → 迁回
└── 睡 ~28 分钟（应用独占全机 191 核）
```

- 检测器：`neon_rot_ldr_at_top_rowmajor`（P0 #1）——3×ldr + 轮换 ALU + 双背靠背 store + memcmp golden
- **为什么整插槽**：三构型对照实验证明单核/分时都测不出，只有插槽独占能让 179 的错显形
- **为什么 30s**：15s 窗首错覆盖率仅 ~42%，30s 是检出可靠性硬底线

## 四、结果解读

| 想知道什么 | 看哪里 |
|---|---|
| 哪轮/哪个插座检出、fail 数、定位核号 | `sweep/<目录>/sweeps.csv`（`fails` 列>0 → `cores` 列即核号；**干净插座必须恒 0**） |
| 检出证据（cpu-mask/种子/线程） | `keep_s<N>_<S>.stdout` |
| 逐 fail 时刻 | `sweep/<目录>/fail_times.csv` |
| 轮节奏与生命周期 | `sweep/<目录>/events.log` |
| 系统状态（全系统模式） | `state/state.json` |

**计数口径（铁律）**：fail 数 = 唯一 `result: fail` 块数（严禁 grep miscompare，双计 2 倍）；
报数须分列"每窗首块（独立检出）"与"重试块"；延迟统计只用首块 time-to-fail（重试块时钟基准异常）。

## 五、性能与开销（2026-10-27 实测）

| 指标 | 生产节奏（30min/轮） | 背靠背极限 |
|---|---|---|
| 应用吞吐损失 | **1.815%** | 24.25% |
| FARRON CPU 消耗 | **0.88%** | 13.3% |
| 每核被占用 | 30s/30min = 1.67%（实算 ~15s，fracture 占空 ~50%） | ~98% |
| 检出率 | **100%**（12/12） | 100% |
| 检测延迟 | 窗内首 fail 中位 17.3s；端到端 ~2min | 同 |

想更低开销：周期 60min → ~0.9%。窗口不能再短（30s 底线）。

## 六、安全须知

1. **看门狗**：任一插槽 ≥98°C 连续 2 次 → 杀 opendcdiag。满载实验必须带上它。
2. **风扇红线**（做温度实验前必读 `docs/CORE179_TEMPERATURE_RESEARCH_20261027.md` §三）：
   F6=40 → CPU1 空载 102°C；F5 压低必须配 F3-4=100（否则 CPU2 冲 98°C）；实验结束**先恢复风扇再收工**。
3. 监控脚本必须 `taskset -c 0` 绑离 179。

## 七、接入真实应用

目前"应用"是 stress-ng。替换为真实应用：
1. 应用主进程 PID 写入 `farron/state/sweep/app.pid`（fork 型 worker 由 `pgrep -P` 自动纳入迁移）
2. `prod_sweep.sh` 的 `ensure_app` 改成你的应用保活方式
3. 应用侧自发现异常可上报：`touch farron/state/anomaly_<core>`（主循环即触即读）
4. 迁移机制（taskset 逐进程改亲和）不用动

## 八、操作坑（实战踩过）

- **绝对路径**：会话/脚本 cwd 常停在子目录，相对路径会 404；`!` 命令和 nohup 一律用绝对路径
- **进程名**：stress-ng 的 worker 叫 `stress-ng-cpu`，`pgrep/pkill -x stress-ng` 只匹配主进程——**用 `-f`**
- **pkill 自匹配**：`pkill -f "xxx"` 会杀掉含该字符串的自身外壳——按 PID kill，或 grep -v 自身
- **换档时刻**：FAN_CHANGE 文件可能滞后实际换档（实测 12min）——以温度/功耗曲线拐点为准
- **Bash sleep ≤600s**：长等待分两段或用后台

## 九、相关文档

| 主题 | 文档 |
|---|---|
| 检测全流程技术手册 | `docs/CORE179_FARRON_SDC_DETECTION_WORKFLOW_20261026.md` |
| 6h 生产验收（本 README 数字来源） | `docs/CORE179_FARRON_6H_PRODUCTION_VALIDATION_20261027.md` |
| 3h/5h 性能基线 | `docs/CORE179_FARRON_3H_STRESSNG_PERF_20261026.md` 等 |
| 温度研究专档（风扇→温度→SDC 率） | `docs/CORE179_TEMPERATURE_RESEARCH_20261027.md` |
| 设计规格 | `farron/DESIGN.md` |
