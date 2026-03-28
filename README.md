# ARM64 SDC Fuzzing - Quick Start Guide

本项目用于ARM64架构的静默数据破坏（SDC）自动化Fuzzing测试。

## 快速开始

### 1. 环境检查

```bash
# 检查当前环境状态
python3 sdc_preflight.py --verbose
```

### 2. 安装依赖

```bash
# 自动安装所有依赖（macOS）
./setup_environment.sh

# 或手动安装
brew install scons swig protobuf qemu
brew install --cask gcc-aarch64-embedded
pip3 install six protobuf numpy
```

### 3. 编译gem5

```bash
# 使用编译脚本（推荐）
./build_gem5.sh ARM opt 8

# 或手动编译
cd gem5
scons -j 8 build/ARM/gem5.opt
```

编译时间估计：1-2小时（取决于系统配置）

### 4. 验证安装

```bash
# 测试gem5构建
python3 test_gem5_build.py

# 再次运行环境检查
python3 sdc_preflight.py --verbose
```

### 5. 生成测试用例

```bash
# 设置Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)/microprobe/src"

# 生成SDC测试用例
python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py \
    --target armv8-common-cortex-a53-aarch64_linux_gcc \
    --policy sdc_fuzzing \
    --output-dir ./artifacts/testcases \
    --num-testcases 10
```

### 6. 运行差分测试

```bash
# 单个测试用例
python3 run_sdc_differential.py \
    artifacts/testcases/test_001.c \
    --compiler aarch64-linux-gnu-gcc \
    --qemu-binary qemu-aarch64 \
    --gem5-binary gem5/build/ARM/gem5.opt \
    --fault-model bit-flip \
    --fault-target register \
    --timeout 300

# 批量测试
python3 sdc_campaign.py run \
    --vault-path artifacts/sdc_vault.sqlite3 \
    --batch-size 10
```

## 项目结构

```
sdc-fuzzing/
├── gem5/                          # gem5仿真器源码
│   ├── build/ARM/gem5.opt        # 编译后的ARM64 gem5二进制
│   └── configs/example/arm/      # ARM配置文件
│       └── sdc_kunpeng920_se.py  # SDC专用SE模式配置
├── microprobe/                    # Microprobe测试生成框架
│   └── targets/generic/tools/
│       └── mp_sdc_offline_gen.py # 离线测试用例生成器
├── mcpat/                         # McPAT功耗分析工具
├── artifacts/                     # 生成的测试用例和结果
│   ├── testcases/                # 测试用例目录
│   ├── results/                  # 测试结果目录
│   └── sdc_vault.sqlite3         # 测试用例数据库
├── build_gem5.sh                  # gem5编译脚本
├── setup_environment.sh           # 环境配置脚本
├── sdc_preflight.py               # 环境检查工具
├── test_gem5_build.py             # gem5构建测试工具
├── run_sdc_differential.py        # 差分测试执行器
├── sdc_campaign.py                # 批量测试运行器
├── sdc_scheduler.py               # 测试调度器
├── sdc_vault.py                   # 测试用例数据库管理
└── GEM5_BUILD_GUIDE.md            # 详细编译指南

```

## 核心组件说明

### 1. 差分测试流程

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Microprobe  │────▶│   QEMU       │────▶│  Golden     │
│ 生成测试用例 │     │ (ISA金标准)  │     │   Hash      │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │    gem5      │
                    │ (故障注入)   │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Faulted     │
                    │    Hash      │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  SDC判定     │
                    │ Hash != Hash │
                    └──────────────┘
```

### 2. SDC判定逻辑

- **matched**: gem5输出与QEMU一致（正常）
- **sdc_found**: gem5正常退出但输出不一致（发现SDC）
- **gem5_failed**: gem5崩溃（非SDC）
- **gem5_timeout**: gem5超时（非SDC）

### 3. 故障注入参数

| 参数 | 说明 | 示例值 |
|------|------|--------|
| --fault-model | 故障模型 | bit-flip, stuck-at |
| --fault-target | 故障目标 | register, memory |
| --fault-bit | 位索引 | 0-63 |
| --fault-tick | 注入时刻 | 1000000 |

## 常见问题

### Q: gem5编译失败怎么办？

A: 检查以下几点：
1. 确保所有依赖已安装：`brew install scons swig protobuf`
2. 减少并行编译任务数：`scons -j 4 build/ARM/gem5.opt`
3. 查看详细错误：`scons -j 8 build/ARM/gem5.opt --verbose`

### Q: 找不到aarch64-linux-gnu-gcc怎么办？

A: 安装ARM64交叉编译器：
```bash
brew install --cask gcc-aarch64-embedded
```

或从ARM官网下载：https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a

### Q: QEMU运行失败怎么办？

A: 检查QEMU安装：
```bash
brew install qemu
qemu-aarch64 --version
```

### Q: 测试用例生成失败怎么办？

A: 确保Python路径正确：
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/microprobe/src"
```

## 参考文档

- [gem5编译详细指南](GEM5_BUILD_GUIDE.md)
- [项目架构设计](AGENTS.md)
- [Kunpeng920微架构说明](doc/kunpeng920.md)
- [ARMv8指令集文档](doc/armv8-isa/)

## 许可证

本项目遵循Apache License 2.0。
