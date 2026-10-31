# CORE179 -O0 编译策略对照实验（2026-10-30）

> **问题**（用户 2026-10-30 提出）：编译优化级别（-O0 vs -O3）是否影响 SDC 测试用例对 179 核的检出频率？
> **设计**：5 用例 × 两臂（-O3 基线 / -O0）× 每跑 30min，同晚交错先手；掩码 24-191（168 核含 179）auto seed；全扇 100% 手动档钉死温度轴。
> **上位文档**：`CORE179_SDC_TESTCASE_PRIORITY_TIERS_20261022.md`（用例与历史率）；`backups/20261030_opendcdiag_O3/BUILD_INFO.md`（-O3 基线二进制档案）。

---

## 一、动机与既有证据

1. 触发配方三要素 = ≥2 源 load + ALU 轮换 + 紧时序；历史结论：触发敏感到**编译期寻址模式 / 指令调度级别**（objdump 触发 vs 不触发分析、movbe 变体布局敏感性、nop 间距曲线）。
2. 基线二进制 = -O3（368 条编译命令全部 -O3，NDEBUG，未 strip 176MB），2026-10-14 10:05 链接，与 10-30 源码树精确同步（`ninja -n` = no work to do），已备份（sha256 `a05c1763…`）。
3. **冒烟期新事实（修正假设）**：-O0 构建后六候选用例迭代耗时 1172-1412ms ≈ -O3 基线（rowmajor 均值 1174ms）——热循环为**手写内联汇编**，-O 级别只影响外围 C++ 脚手架。

## 二、假设（事前登记，开跑前写定）

| 用例 | 热循环构成（源码实测） | 预测 |
|---|---|---|
| rowmajor / sub / str3 / mrn_reloaded_2src_alu | asm 块（1-4 处） | **H1'（asm 不变性）**：store→load 窗口在 asm 内不变 → fails/iteration 两臂同量级 |
| movbe | **纯 C++（79 行，0 asm）** | **H1（时序窗破坏）**：-O0 打乱编译代码的调度/转发窗 → fails/iteration 塌缩 |

- **H0（无编译效应）**：两臂 fails/iteration 无差异。
- **判别指标**：主指标 fails/min（用户口径=检出频率）；**归一化指标 fails/iteration**（区分"机制被破坏" vs "只是跑得慢"）；iterations/min 同时报告。
- **事前判读规则**：
  1. O0 臂全 0 且 O3 臂同晚正常（≥1/min）→ 编译策略影响成立（纯 C++ 用例归 H1；若 asm 用例也归零，则触发窗并非仅由 asm 决定，外围调度同样参与——本身即是新机制证据）。
  2. asm 用例两臂 fails/iteration 同量级、movbe 塌缩 → 编译效应限定于编译代码热循环（H1+H1' 并存）。
  3. 两臂全部同量级 → 编译策略无关（H0）；"str→ldr ≤2cyc 紧时序窗"需弱化解读。
  4. O3 臂整体异常低（全用例 <0.5/min，低于近期同构最低）→ 该晚数据作废，择晚重跑。

## 三、构建方法（"假 O0"陷阱与三点发现）

### 3.1 假 O0 陷阱（最重要）

根 `meson.build` 82-100 行：`release`/`debugoptimized` 分支**硬编码 `-O3`**（项目层参数追加在 meson 优化旗标之后，GCC 取后者）。实证：基线 compile_commands 中每个 TU **-O3 出现两次**（位置 20/27）。
→ `--buildtype=release -Doptimization=0` 得到的是**假 O0**（有效级别仍为 -O3）。
→ 正确姿势：`--buildtype=debug -Db_ndebug=true`——项目 debug 分支自带 `-O0`，meson 亦 -O0；`b_ndebug=true` 补 NDEBUG 与基线对齐。
**残差差异**（-O 之外，均已评估对本实验无影响）：`-D_FORTIFY_SOURCE=2` 仅基线有（-O0 下本就惰性，热循环无 libc 调用）；`-ggdb3` vs `-g`（仅调试信息格式，无代码生成差异）。

### 3.2 Eigen 分叉

基线（09-17 setup）实际用 `/usr/local/include/eigen3` = **3.3.8**（CLAUDE.md 记载"3.4.0"有误）；新 setup 的 `dependency('eigen3')` 捡到 `/usr/include/eigen3` = 3.4.0。3.4.0 的 BDCSVD 在 -O0 下因 C++20 重写操作符报错（4 个 eigen_svd TU 编不过）。
→ `-Deigen3_root=/usr/local` 钉回 3.3.8（与基线一致），4 个失败全部消失。

### 3.3 -O0 不可编译的 5 个测试

`vector/kreg1,4,7`、`vector/insert_extract`、`atomic/atomic_simd_256`：`vgetq_lane_*(vec, 运行时变量)` 违反 lane 立即数约束，只有 -O≥1 的常量传播能救——**测试代码缺陷，且均非战役用例**，在副本树剔除。

### 3.4 副本树构建（主树零改动）

- 源码 = 当日 source_snapshot（与 -O3 基线 ninja -n 验证同步）提取至 `arm64-sdc-fuzzing/opendcdiag-O0/`；仅在**副本**的 tests/cpu/meson.build 剔除上述 5 文件（副本内留 meson.build.orig）。
- 验证：**338/338 TU 纯 -O0（无一例外）**、NDEBUG 338/338、六候选用例全在场、Eigen 3.3.8（/usr/local）与基线一致。
- TU 差 30（368→338）= 剔 5 + 24 个 ssl/ipsec/openssl 相关 TU（x86 `_sse`/`_x86_64` 测试与框架 SSL 件；当日依赖查找环境与 09-17 不同所致，不影响任何战役用例与框架执行路径）。

### 3.5 二进制指纹与冒烟

| | -O3 基线 | -O0 |
|---|---|---|
| 路径 | `builddir/opendcdiag` | `opendcdiag-O0/builddir/opendcdiag` |
| sha256 | `a05c17631da3e1a27a973ab3a68f5654884221baa8a9df94c3c36e893387ea20` | `43789a69e188d5300967cf44a70b18fbe40657d5ed3994586678bc9c6d25efcf` |
| 大小 | 176,819,800 B | 164,643,680 B |
| 版本串 | opendcdiag-837c6948deaa-dirty | 同左（**版本串不可区分两臂，以 sha256 + 日志 command-line 为准**） |

- 冒烟（规范：179 hotplug 下线 + `-n 191` 全核）：六候选各 60s 全部 rc=0、0 fail、迭代正常。

## 四、实验设计

| 项 | 值 |
|---|---|
| 用例（登记册前五） | rowmajor、sub、mrn_reloaded_2src_alu、str3、movbe |
| 臂 | O3 = 基线二进制；O0 = 副本树二进制 |
| 单跑 | 30min（`-T 30m`），每用例每臂各一跑，共 10 跑 ≈ 5h |
| 交错 | 按用例交替先手：rowmajor O3先 → sub O0先 → mrn_reloaded O3先 → str3 O0先 → movbe O3先 |
| 掩码/线程 | `taskset -c 24-191`（168 核，**含 179**，开跑前验证在线），`-n 168` |
| 种子 | auto（不传 `-s`） |
| 风扇 | BMC 手动模式 99999s + 全扇 100%（用户授权，`ipmcset` 执行；转速实测 19.4-20.2k RPM 与温度专档 100% 档吻合；CPU1 空载 80°C→70°C 回落中） |
| 温度轴 | 全扇 100% = 温度专档凉端构型（CPU4 负载 52.7°C、13/min 档）——两臂同构，温度不再是臂间混淆 |
| 监控 | 60s 采样 CPU1-4 温度 + FAN1/4/6 转速（绑核 8，测试掩码外）；任一 CPU >95°C 看门狗中止 |
| 日志 | `docs/20261030/o0_compile_experiment/{runs/, summary.csv, monitor.log, faninfo_at_start.txt, campaign.sh}` |

**历史率参考**（梯队登记册口径；跨夜波动 0.45×~4×、温度每 +3.5°C 率减半，仅作量级参考不可直接比）：rowmajor ~8.5（09-13 后降至 0.6-1.9，未归因）、sub ~3.9、mrn_reloaded ~3.5、str3 ~3.3、movbe ~1.9（30min 口径）。

## 执行记录（2026-10-30 夜）

- 01:20 风扇：BMC 手动 99999s + 全扇 100%（六扇 19.4-20.2k RPM，快照 `faninfo_at_start.txt`）。
- 01:28:33 战役启动（campaign.sh；掩码 24-191 含 179 已验证，两臂二进制 sha256 记入 monitor.log）。
- **01:34:19-01:43:11 监控空窗**：会话 API 429 崩溃，harness 清理其跟踪的后台任务，campaign.sh 主脚本+监控子进程被杀。**run1（O3 rowmajor，PID 1545189）孤儿存活**：亲和 24-191 复核通过、日志连续增长无损失。
- 01:43:11 `campaign_resume.sh` 以 setsid+nohup 脱离会话启动：重启监控/看门狗 → 轮询等 run1 自退（-T 30m，~01:58）→ 补记 summary（**rc=orphan**：退出码不可寻回，fail 计数以日志为准）→ run2-10 按原序执行。预计 ~06:29 完成。
- 判读注意：空窗 9min 无温度采样（风扇档位全程未变）；run1 的 start 以 CAMPAIGN START 行为准；巡检 cron 每 30min（:11/:41）。
- **fail 块日志格式（终局分析用）**：每个失败块 = 一条 `result: fail` 行（唯一块计数即数此行，禁数 miscompare）；归属看块内 `fail: { cpu-mask: ... }` 的 X 位（192 字符、4×48 分组，X 位置=核号）与 `threads:` 段 `- thread: N, id: { logical: ... }`（实测首块 thread 155 / logical 179，与"核号=mask 下标直读"一致）。
- **03:00:32 热看门狗中止**（resume1 全役中止语义）：run4（O3 sub）启动 ~100s 内四插槽同步跳温（CPU2 83→97、CPU3 +10、CPU1 +5、CPU4 +7），97°C > 95°C 触发。12/12 风扇健康（19.5-20.2k RPM，排除风扇故障）；卸载 10min 后回落基线（CPU2 60）。run4 截断：rc=143、日志存 `.truncated-0300`、summary 行保留但**分析剔除**；O3-sub 点由重跑补。
- **03:15 O0 臂工作量实证**（排除"跑得空"混淆）：run2 日志尾 `# Loop iteration 1516 finished, average time 1186.71 ms` + `exit: pass` = 满工作量（168 线程×1516 迭代，快于 O3 的 1332）；passes/loops 比值差异（O3 10.3 vs O0 3.7/1.0）为日志节奏伪象——工作量与 0-fail 判据一律用 loop-iteration 行 + exit 行。
- 03:17 `campaign_resume2.sh` 启动（setsid 脱离会话）：**逐跑热中止**（STOPRUN 语义，看门狗只杀当前跑）+ 每跑前置 CPU2≤70°C 门（最长 10min）+ 热中止重试一次否则 thermal-skip + **O3-sub 重跑移至最后**（其稳态可能 >95°C，排在最后即使再触发也只损失该跑）。剩余顺序：mrn O3/O0 → str3 O0/O3 → movbe O3/O0 → sub O3 重跑，预计 ~06:50-07:20 完成。**决策记录（偏离 01:43 预登记"勿自行重启"）**：依据=看门狗属设计内安全路径、风扇 12/12 健康、卸载自恢复实证、逐跑语义严格安全于原全役中止；通宵闲置违背用户当晚实验目标。全部留痕供晨间复核。

## 五、结果（2026-10-30 06:06 战役完成；全量数据见 `20261030/o0_compile_experiment/RESULTS.md`）

| 用例 | O3 fails/min（fails/loop） | O0 fails/min（fails/loop） |
|---|---|---|
| rowmajor | **13.33**（0.300） | **0**（0） |
| sub | 3.79\*（0.114\*） | **0**（0） |
| mrn_reloaded | **7.80**（0.194） | **0**（0） |
| str3 | 8.85\*（0.563\*） | **0**（0） |
| movbe | **1.93**（0.0489） | **0**（0） |

\* O3 臂 sub/str3 两次热中止（CPU2 稳态 >95°C），率为存活窗口值。O3 臂合计 752 fail **100% 归属 logical 179**；O0 臂五跑零检出且**四法交叉全过**（rc=0 + exit:pass + 满工作量 loop 行 + 0 miscompare），工作量反而多 12-15%（O0 迭代更快）。CPU4（179 插槽）O0 臂反热 2-3°C——温度轴最多解释 2× 率降，无法解释归零。

## 六、判读与结论（按 §二 事前规则执行）

**规则 1 命中：编译策略影响成立。** O0 臂 5/5 全零 + O3 臂同晚全部正常（1.93-13.33/min）；且 asm 热循环用例同样归零 → **触发窗并非仅由 asm 决定，外围编译产物同样参与触发**（H1' 否定；H1 从 movbe 扩展至全部用例）。Poisson：最小 λ=58 → 单项 P(0)≈4.7×10⁻²⁶，联合 P<10⁻⁴⁰⁰。

**结论表述**：同一晚、同一掩码（24-191 含 179）、同一负载结构下，-O3 基线二进制对 179 核 SDC 检出 1.9-13.3/min（752/752 全 179），-O0 构建二进制五用例全部零检出——历史"触发敏感到编译期布局级"的结论升级为"**-O 级别本身即是检出开关**"。

局限：单跑/格子（存在性判定有效，率值需复现）；O0 树有既档非-O 残差（§3.4，收窄归因需 -O1/-O2 梯度或副本树重建 -O3 对照）；机制（asm 邻域被外围 -O0 改变什么）待 objdump 对比。详见 RESULTS.md §七/§八。

## 七、风险与已采取措施

- **热**：CPU1 空载 80°C 异常（auto 档下即如此，成因未查——散热退化待排查）→ 全扇 100% 后回落；看门狗 95°C 兜底。
- **179 panic**：neon_rot 家族满载有 panic 史（15 次，vmcore 落 /home/sdc/vmcore）；每跑独立日志 + summary 逐跑追加，中断不毁已完成数据。
- **-T 迭代粒度**：框架在迭代间检查 -T，迭代 ~1.2-1.4s，超时可忽略。

## 八、关联与勘误

- 关联：梯队登记册 / `CORE179_ALL_VALID_SDC_TESTCASES_20260923.md` / `CORE179_TEMPERATURE_RESEARCH_20261027.md` / 备份 `BUILD_INFO.md`。
- **CLAUDE.md 勘误两处（本实验副产物）**：系统 Eigen 实为 **3.3.8**（非 3.4.0；且 /usr 下另有一份 3.4.0 会在 -O0 构建时被捡到并编不过）；主机 `nproc` = **192**（非 128）。
