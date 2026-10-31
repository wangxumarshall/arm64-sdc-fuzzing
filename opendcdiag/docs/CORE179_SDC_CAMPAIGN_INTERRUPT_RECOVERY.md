# CORE179 SDC 长线战役中断与数据恢复记录

> 日期：2026-08-31（记录 2026-08-30 至 08-31 发生的事件）
> 范围：记录一次 11 小时长线战役脚本被系统重启中断、以及如何从幸存 yaml 恢复 fail 数据的全过程。
> 数据来源：`last reboot`、`df /tmp`、仓库根 `opendcdiag-*.yaml`、持久日志 `movbe_log/campaign_resume/`。
> 注：客观事实记录，不含推理。

---

## 一、事件经过

### 1.1 战役启动
- 时间：2026-08-30 14:15 CST
- 脚本：`run_campaign_1shot.sh`（仓库根），用 `nohup setsid` 脱离 shell 后台运行
- 脚本内容：3 阶段串行
  - 阶段1：`mrn_rmw_dump` 跑 1 小时（统计 op 的 ALU-vs-store 分类）
  - 阶段2：9 个"历史 0-fail"的 movbe 变体，每个 30min
  - 阶段3：11 个"历史 0-fail"的 mrn_rmw 变体，每个 30min
- 参数：全核 192 含 179，auto seed，`--ignore-os-error --ignore-timeout`
- 预计总时长：1h + 9×30min + 11×30min = 1h + 10h = **约 11 小时**，预计 8-31 01:15 完成

### 1.2 中断
- 2026-08-31 **00:53 系统重启**（`last reboot` 确认，boot ID 变更；当前 `up 7:05`，boot 时间 00:53）
- 重启时战役正好在阶段3 最后一个变体 `mrn_rmw_diff_64k`（00:45 启动，只跑了约 8 分钟被杀）
- 最近 4 天重启 3 次（8-25、8-26、8-31），非定时任务（root crontab/anacron 无重启项），疑似人工或外部触发

### 1.3 数据丢失情况
- 脚本所有输出指向 `/tmp`：`campaign_summary.txt`、`camp_*.log`、`/tmp/<test>_<pid>.bin`
- **`/tmp` 是 tmpfs**（`df /tmp` 显示 `tmpfs on /tmp`），重启即清空 → 上述文件全部丢失，零残留
- nohup.out 也在 /tmp，丢失

---

## 二、数据恢复：从幸存 yaml 捞回

### 2.1 关键发现
opendcdiag 框架**独立**把每次运行的完整记录写到仓库根目录的 `opendcdiag-<启动UTC>_<pid>.yaml`（不是 /tmp），这些文件活过了重启。这是战役数据的唯一幸存来源。

### 2.2 yaml 的写入规律（实测）
- **文件名是启动时刻（UTC）**，mtime 是结束时刻（CST）
- **只在 `exit: fail` 时写 yaml**；全 pass 的运行不产 yaml。已验证：1s 的 pass 测试不产新 yaml。
- → 这解释了阶段2 的 6 个 movbe 变体（movbe_l2/str_multiload/probe_a/b/d/f/g1/g2）没有 yaml：它们 30min 全 pass，不产 yaml。无法确认是真灭活还是 30min 太短没碰上。

### 2.3 幸存 yaml 时间线与 fail 数（战役窗口 CST 14:15→00:53）

| test | 启动CST | 结束CST(mtime) | fail块 | 时长min | 频率fail/min |
|---|---|---|---|---|---|
| mrn_rmw_dump | 14:15 | 15:15 | 2 | 60 | 0.033 |
| movbe_dump_golden | 15:15 | 15:45 | 45 | 30 | 1.500 |
| (6个 movbe 变体 pass 无 yaml) | ~15:45 | ~19:45 | 0 | 各30 | 0 |
| movbe_dump_probe_xn | 19:45 | 20:15 | 1 | 30 | 0.033 |
| mrn_rmw_diff | 20:45 | 21:15 | 8 | 30 | 0.267 |
| mrn_rmw_nop | 21:45 | 22:15 | 11 | 30 | 0.367 |
| mrn_rmw_nop1 | 22:15 | 22:45 | 1 | 30 | 0.033 |
| mrn_rmw_nop4 | 22:45 | 23:15 | 1 | 30 | 0.033 |
| (阶段3 剩余6个未轮到) | — | — | — | — | — |
| mrn_rmw_diff_64k | 00:45 | 00:53(中断) | 19 | ~8 | 2.375 |

注：mrn_rmw_diff_64k 只跑约 8 分钟被重启中断，2.375/min 是瞬时率，不能直接和 30min 的比。

### 2.4 command-line 交叉验证（确认 yaml 归属战役）
每个 yaml 头部 `command-line:` 字段含 `opendcdiag -e <test> -n 192 -T Xm --ignore-os-error --ignore-timeout`，version 为 `opendcdiag-837c6948deaa-dirty`，与战役脚本参数完全匹配，mtime 在战役窗口内 → 确认这些 yaml 是战役产出。

---

## 三、恢复结果

从幸存 yaml 共恢复 **88 条 fail 记录**：
- mrn_rmw 系列：42 条（dump 2 + diff 8 + nop 11 + nop1 1 + nop4 1 + diff_64k 19）
- movbe 系列：46 条（golden 45 + probe_xn 1）

这些数据的详细 bit 翻转/频率/op 分析见另文 `docs/CORE179_SDC_BITFLIP_AND_PATH_ANALYSIS.md`。

阶段1 mrn_rmw_dump 的 2 条含 recompute 分类（`[ALU-COMPUTE-WRONG][fwd-faithful]`），见 `docs/CORE179_SDC_L1D_EXCLUSION_AND_INSTRUCTION_LOCALIZATION.md` 第二部分。

---

## 四、教训与后续改进

### 4.1 教训：长线脚本输出不能写 /tmp
- `/tmp` 是 tmpfs，重启即清，长线战役（跨越小时/天）的日志/bin/汇总放 /tmp = 必丢
- 昨天战役就是因此丢光了 camp_*.log 和 bin

### 4.2 改进：后续补跑脚本改用持久路径
- 补跑脚本 `run_campaign_resume.sh` 把日志/汇总写到 `movbe_log/campaign_resume/`（仓库内，活过重启）
- yaml 由框架写仓库根目录（已验证活过重启）
- bin 若产生则即时拷贝到持久目录

### 4.3 教训：夜间长跑有重启风险
- 这台机最近 4 天重启 3 次，夜间长跑易被中断
- 补跑定在白天（08:35–11:35），夜里重启不影响

---

## 五、数据源可信度标注

- **可信（有幸存 yaml，活过重启）**：mrn_rmw_dump(2)、movbe_dump_golden(45)、movbe_dump_probe_xn(1)、mrn_rmw_diff(8)、mrn_rmw_nop(11)、mrn_rmw_nop1(1)、mrn_rmw_nop4(1)、mrn_rmw_diff_64k(19)。
- **无 yaml 不可追溯（全 pass 不产 yaml）**：阶段2 的 6 个 movbe 变体（movbe_l2/str_multiload/probe_a/b/d/f/g1/g2），只能确认"30min 内未触发"，不能确认是真灭活。
- **未轮到**：阶段3 剩余 6 个（mrn_rmw_l1d/diff_nop64/nop8/nop16/nop64/diff_1m）战役时未跑，后在 8-31 补跑（见 `movbe_log/campaign_resume/`）。
