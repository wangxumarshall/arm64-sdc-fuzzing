# CORE179 读路径战役 K 轴格批次 2 实现记录(2026-09-13 晚)

配套:设计 `docs/CORE179_READPATH_LOCALIZATION_CAMPAIGN_20260913.md`、首轮结果 `docs/CORE179_READPATH_P0_GPS_FIRST_SIGNATURES_20260913.md`。本批 = P1-P4 全部实验格的实现与集体验证(按用户指示:集体验证后再统一跑)。

## 一、交付物(7 文件,11 测试)

| 测试 | 轴 | 旋钮(相对 GPS 底盘的唯一差异) | 预注册判读 |
|---|---|---|---|
| `k5far` | K5 决定格 | srcA/srcB 并排 → 单缓冲交错(even=A 族,odd=B 族),地址邻居永远是另一族 | 替换源仍 A-only → 跟随缓冲/端口身份;变成地址邻居(另一族)→ 近邻串扰(E6 系);A+B 拼接 → steering |
| `k5inter_rand` | K5 对照 | 交错布局 + 自然随机数据(无标签) | k5far−本格 = 标签效应;本格−父 rowmajor = 布局效应;兼 0.5 阶段 A 轨(有 dump) |
| `k2pureload` | K2 存储几何 | 热循环零 store,str temp/str dst → xor 累加器(v 轮换×4) | 满率同签名 → store 非必要,store_only vs fwd_probe 旧矛盾了结(store 也不必要);率塌 → store 是必要放大器。**设计让渡**:无逐元素 store 则无法定位出错元素,读出=率+哪个 op 类累加器翻转 |
| `k4gap` | K4 消费间距 | load→ALU 间插 8 nop(关 bypass 窗口,迫走寄存器堆) | 远距仍满率同签名 → bypass 非独占路径;率塌 → 缺陷骑在 0 拍 bypass(E1/E2);距离直方图随间距移 → 损伤窗口移动 |
| `k4bgap` | K4b ALU→store 间距 | ALU→str 间插 8 nop | 同率同签名 → E3 非 注入点(与 E1/E2 收窄一致);率/签名变 → E3 参与 |
| `k7p_zero/one/rand/hiham` | K7 pattern 电池 | 4 档填充:全 0/全 1/GPS 打标随机/0x55AA 高汉明 | zero/one≈0 而 rand/hiham 触发 → pattern 门控确认;全档相似 → 2×64b 路径 pattern 门控弱,4×32b=0 需 lane 解释;hiham≫rand → 转换密度相关 |
| `k3res` | K3 驻留 | footprint 4×(4096 元素/缓冲,256 KiB 总) | 率塌 → 64 KiB 常驻足迹是配方一部分;率稳+距离直方图仍紧(全常驻邻居)→ 无驱逐暴露,阴性仍有用;率稳+出现远距(已驱逐)源 → L1D 内选择失宠 |

全部继承 GPS 底盘纪律:同标签编码(magic|byte_off|~byte_off|gen,gen 恒 0)、asm volatile ldr、冷路径 memcmp 门 + 五缓冲 dump 到 `movbe_log/gps_rowmajor/`(文件名带格前缀)、auto seed 不固定、dump 落盘(09-08 教训)。

## 二、集体验证(三步全过,2026-09-13 晚)

1. **构建**:ninja 全通过(仅 CLAUDE.md 登记的 -Wrestrict 已知无害警告)。
2. **objdump 骨架同一性**(最长后向分支区间统计):
   | 格 | 主循环指令数 | ldr q | str q | nop | vALU | 备注 |
   |---|---|---|---|---|---|---|
   | GPS 基准 | 187 | 6 | 6 | 0 | 8 | |
   | K5 交错(两格同构) | 215 | 7 | 8 | 0 | 8 | 多出的 ldr/str = 交错索引计算被编译器向量化 |
   | K2 纯 load | 218 | 13 | 8 | 0 | 11 | str=累加器落地(冷路径)+xor 累加 vALU;热循环内零源数据 store ✓ |
   | K4 间距 | 202 | 6 | 6 | **16** | 8 | 8 nop×2 展开 |
   | K4b 间距 | 197 | 6 | 4 | **16** | 8 | |
   | K3 驻留 | 186 | 6 | 6 | 0 | 8 | 与基准逐指令同构(仅循环边界常数 0x400→0x1000) |
   | K7 电池(公共函数) | 192 | 6 | 6 | 0 | 8 | add.2d×2 + eor/and/orr.16b 各 2,与基准同形 |
3. **阶段 1 框架冒烟**:179 hotplug 下线,191 核 60s,10 测试名(11 测试实例)→ **55 pass / 0 fail / 0 miscompare / 0 dump**,三法交叉干净。

## 三、事故记录(meson.build 误还原,已完全恢复)

批量写之前的清理中 `git checkout tests/cpu/meson.build` 误将约 185 行未提交本地注册还原(全部 movbe/mrn/neon_rot 家族)。恢复:以 `builddir/.ninja_log` 编译对象清单为地面真值,精确重建 70 个丢失注册(66 misc + 2 cache + 1 eigen_gemm + 1 memory),对账 70/70 零缺失,构建+冒烟验证通过。教训入记忆:删临时测试永远手删注册行,恢复源是 .ninja_log。

## 四、统一跑排程(待批准执行)

按设计文档 §十三 优先级序,交错标准格(父 rowmajor,自然数据)穿插:

| 序 | 格 | 时长 |
|---|---|---|
| 1 | k5far(P1 决定格) | 30min |
| 2 | 标准格(父 rowmajor 复跑,漂移基线) | 30min |
| 3 | k4gap + k4bgap(可同 run 分先后,亦可两格) | 各 30min |
| 4 | k2pureload | 30min |
| 5 | k5inter_rand + k7p_rand(A 轨口径) | 各 30min |
| 6 | k7p_zero / one / hiham(pattern 梯度) | 各 30min |
| 7 | k3res | 30min |
| 全程 | IPMI 温度每格记录;ECC 计数器并行读 | — |

注意:/home 99% 满(15G 余),每格 dump 上界 ~18MB,87 dump≈7MB 量级可承受;跑前清旧非必需 dump。

## 五、待办

- [x] gps_classify.py 升级:field_subst 桶已合入,首轮 87 dump 回归 166/12 与定制脚本完全一致;错位窗搜索原已有
- [ ] dump 文件名建议改用 sched_getcpu()(cpu 形参是 child 内线程号,首轮靠三方互证才闭合)
