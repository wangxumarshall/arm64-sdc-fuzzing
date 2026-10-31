# CORE179 有效 SDC 测试用例登记册(2026-09-14)

> **注（2026-09-23）**：本册仅登记 K-cells 战役判定的 7 个 rowmajor 家族用例，
> 是完整总登记册的子集。全部 57 个有效用例（含 movbe 系 7、mrn_rmw 系 8、
> eigen 系 9、第二代构造/移植 12、ldr_at_top 家族 14 等）见
> `docs/CORE179_ALL_VALID_SDC_TESTCASES_20260923.md`。

依据:2026-09-13 20:30 → 09-14 01:45 K-cells 战役(11 格 × 30min)+
09-14 15:16-15:46 k3res 补跑(30min 跑满)。
判定标准:三法交叉(唯一 `result: fail` 块计数 + `exit:` 行 + miscompare 行),
fail 全部锁定物理核 179(cpu-mask X 位 / thread 字段核verify)。

## 一、有效测试用例清单(7 个,均触发 SDC)

| # | 注册测试名(-e 参数) | 源文件 | fail/30min | 首跑时段(本地) |
|---|---|---|---|---|
| 1 | `neon_rot_ldr_at_top_rowmajor` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor.cpp` | 58 | 09-13 21:00–21:30 |
| 2 | `neon_rot_ldr_at_top_rowmajor_k5far` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k5far.cpp` | 37 | 09-13 20:30–21:00 |
| 3 | `neon_rot_ldr_at_top_rowmajor_k5inter_rand` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k5inter_rand.cpp` | 72 | 09-13 23:00–23:30 |
| 4 | `neon_rot_ldr_at_top_rowmajor_k7p_rand` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k7pattern.cpp` | 78 | 09-13 23:30–00:00 |
| 5 | `neon_rot_ldr_at_top_rowmajor_k7p_one` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k7pattern.cpp` | 42 | 09-13 00:30–01:00 |
| 6 | `neon_rot_ldr_at_top_rowmajor_k7p_hiham` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k7pattern.cpp` | 44 | 09-13 01:00–01:30 |
| 7 | `neon_rot_ldr_at_top_rowmajor_k3res` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_k3res.cpp` | 58† | 09-14 15:16–15:46(补跑) |

† k3res 两轮数据:09-13 01:30–01:45 被第 12 次 179 内核 panic 打断,
15min 内 114 fail(突发期);09-14 补跑完整 30min = 58 fail。
有效计数以补跑为准(率 1.93/min,与基线持平;
"4×footprint 提升触发率"未在完整轮复现,归因为突发期膨胀)。

注:k7p_rand / k7p_one / k7p_hiham 三个测试共用同一源文件
`k7pattern.cpp`,经 `k7p_init_common()` 的 P_RAND_GPS / P_ONE / P_HIHAM
枚举区分填充模式,`DECLARE_TEST` 各自独立注册。

## 二、测试负载环境(两轮战役共同配置)

### 硬件 / 系统
- 主机:Kunpeng 920(ARMv8.1-A),192 逻辑核(nproc=192),openEuler / aarch64
- **核 179 在线并参与负载**(触发战役的目的即抓 179 的 SDC;
  运行前后 `cat /sys/devices/system/cpu/cpu179/online` = 1 核verify)
- 全部 fail 锁定 179,其余 191 核零错误

### 运行配置(战役脚本 `scripts/kcells_campaign.sh`)
```console
taskset -c 0-191 ./builddir/opendcdiag -T 30m -n 192 \
    -e <test_name> -o <log> -q
```
- `-n 192`:全核(含 179),taskset 掩码 0-191 交叉验证(防亲和性继承事故)
- **auto seed**:不传 `-s`,LCG 每迭代自动换 seed(日志逐迭代可见
  `seed: 'LCG:...'`;既定方法论:永不固定 seed)
- `-T 30m`:每格 30 分钟,TEST_LOOP 上限 `1<<13` 外层迭代
- 日志落盘:`builddir/campaign_p0/runs/<cell>.log`(吸取 /tmp 丢失教训)
- dump 落盘:`movbe_log/gps_rowmajor/<cell>_fail_cpu<N>_sweep<M>.bin`
  (文件名中 cpu N 为 child 内线程号,非物理核;物理核以日志 thread 字段为准)
- 监控:taskset 绑核 178(避开 179),每 5min 采样进程/温度

### 家族共同热循环骨架(7 个有效用例共享)
1. **顶部第 3 条 ldr**:`unused_x = load_vec(&scratch[i])`(结果仅 `(void)` 消费,
   防 DCE,须 asm 级确认 reload)
2. **双源 load**:`a = src[...]`、`b = src[...]`(2 源,触发配方必要条件)
3. **轮换 ALU**(触发配方必要条件):`switch (i % 4)` 逐元素轮换
   `vaddq_u64 / veorq_u64 / vandq_u64 / vorrq_u64`,lane 形状 **v0.2d(2×64b)**
4. **背靠背双 store**:`temp[i]` + `dst[i]` 紧邻两条 str
5. 扫描序:偶数轮升序 / 奇数轮降序交替(rowmajor 家族骨架)
6. 校验:热循环后 `memcmp` 冷分支比对,dump 只进冷分支(多进程多 seed 抓样本,
   冷热分离纪律)

### 各用例差异化参数(唯一变量)

| 用例 | 元素数/缓冲 | 总 footprint | 数据填充 | 布局 |
|---|---|---|---|---|
| rowmajor(基线) | 1024 (uint64x2_t) | 64 KiB(4×16 KiB) | memset_random | srcA/srcB 两平行缓冲 |
| k5far | 1024 | 64 KiB(交错单缓冲 2048 elems) | GPS 标签(A/B 族 magic) | **交错** src[2i]/src[2i+1] |
| k5inter_rand | 1024 | 64 KiB(交错) | memset_random | 交错 |
| k7p_rand | 1024 | 64 KiB(4×16 KiB) | GPS 标签随机 | 平行 |
| k7p_one | 1024 | 64 KiB | 全 1(常量 golden) | 平行 |
| k7p_hiham | 1024 | 64 KiB | 0x55/0xAA 交替(最高翻转密度) | 平行 |
| k3res | **4096(4×)** | **256 KiB** | GPS 标签 | 平行 |

## 三、对照:灭活格(4 个,0 fail,非有效用例)

`k2pureload`(零 store)、`k4gap`(load→ALU 间 8nop)、
`k4bgap`(ALU→str 间 8nop)、`k7p_zero`(全 0 数据)——
与有效用例的差异即触发配方的必要条件侧写:
**零 store 灭活 / 拆紧时序灭活(双向)/ 全 0 数据灭活**。
`k7p_one` 触发而 `k7p_zero` 灭活 → 数据激活面非对称(非"常量即灭活")。

## 四、可追溯性

- 逐格日志:`builddir/campaign_p0/runs/*.log`(时间戳 09-13 20:30 → 09-14 01:45;
  k3res 补跑 `k3res_rerun.log` 09-14 15:46)
- dump 样本:`movbe_log/gps_rowmajor/`(k3res 累计 170 个:k7p 系/rand 系各自前缀)
- fail 签名(batch2 已归档):跨字段搬运 `got = exp ± X*(2^32-2^16)` 100% 符合,
  eor 零例;GPS 主族 93% = srcA 近邻字段替换(见
  `docs/CORE179_READPATH_K_CELLS_BATCH2_RESULTS_20260914.md`)
- 战役设计:`docs/CORE179_READPATH_LOCALIZATION_CAMPAIGN_20260913.md`
