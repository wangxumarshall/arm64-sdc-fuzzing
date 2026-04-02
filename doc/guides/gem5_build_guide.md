# gem5 ARM64 编译与仿真执行指南

本文档详细说明如何在macOS环境下编译ARM64架构的gem5，并使用microprobe生成的测试用例进行SDC（静默数据破坏）仿真测试。

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU核心数 | 4核 | 8核+ |
| 内存 | 16GB | 32GB+ |
| 磁盘空间 | 50GB | 100GB+ |
| 操作系统 | macOS 12+ | macOS 14+ |

**当前系统状态**：
- CPU: 10核
- 内存: 32GB
- 磁盘: 659GB可用
- Python: 3.13.3
- 编译器: Apple Clang 17.0.0

## 第一步：安装依赖

### 1.1 使用Homebrew安装系统依赖

```bash
# 安装Homebrew（如果尚未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装gem5编译依赖
brew install scons swig protobuf

# 可选：安装其他有用工具
brew install cmake ninja
```

### 1.2 安装Python依赖

```bash
pip3 install six protobuf numpy
```

### 1.3 验证依赖安装

```bash
# 检查scons
scons --version

# 检查swig
swig -version

# 检查protobuf
protoc --version
```

## 第二步：编译gem5

### 2.1 快速编译（推荐）

使用提供的编译脚本：

```bash
cd /Users/wangxu/1-project/sdc-fuzzing
./scripts/build_gem5.sh ARM opt 8
```

参数说明：
- `ARM`: 目标架构（ARM64）
- `opt`: 编译类型（优化版本）
  - `debug`: 调试版本，包含完整调试信息，编译慢，运行慢
  - `opt`: 优化版本，包含部分调试信息，推荐日常使用
  - `fast`: 快速版本，无调试信息，运行最快
- `8`: 并行编译任务数（建议设置为CPU核心数的80%）

### 2.2 手动编译

```bash
cd /Users/wangxu/1-project/sdc-fuzzing/gem5

# 编译ARM架构的gem5
scons -j 8 build/ARM/gem5.opt

# 编译完成后验证
./build/ARM/gem5.opt --help
```

### 2.3 编译时间估计

| 编译类型 | 首次编译 | 增量编译 |
|---------|---------|---------|
| debug | 2-3小时 | 5-15分钟 |
| opt | 1-2小时 | 3-10分钟 |
| fast | 1-2小时 | 3-10分钟 |

### 2.4 常见编译问题

**问题1：内存不足**
```bash
# 减少并行任务数
scons -j 4 build/ARM/gem5.opt
```

**问题2：找不到Python.h**
```bash
# 设置Python路径
export PYTHONPATH=/opt/homebrew/lib/python3.13/site-packages
```

**问题3：protobuf版本不匹配**
```bash
# 重新安装protobuf
brew reinstall protobuf
pip3 install --upgrade protobuf
```

## 第三步：安装ARM64交叉编译工具链

### 3.1 使用Homebrew安装

```bash
# 安装ARM64交叉编译器
brew install --cask gcc-aarch64-embedded

# 或者使用官方工具链
# 下载地址：https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a
```

### 3.2 安装QEMU用户模式

```bash
# 安装QEMU
brew install qemu

# 验证安装
qemu-aarch64 --version
```

### 3.3 验证工具链

```bash
# 检查编译器
aarch64-linux-gnu-gcc --version

# 检查QEMU
qemu-aarch64 --version
```

## 第四步：生成测试用例

### 4.1 使用microprobe生成测试用例

```bash
cd /Users/wangxu/1-project/sdc-fuzzing

# 设置Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)/microprobe/src"

# 生成SDC测试用例
python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py \
    --target armv8-common-cortex-a53-aarch64_linux_gcc \
    --policy sdc_fuzzing \
    --output-dir ./artifacts/testcases \
    --num-testcases 10
```

### 4.2 测试用例结构

生成的测试用例包含：
- `test_<id>.c`: C源文件，包含汇编注入和状态哈希打印
- `test_<id>.asm`: 原始汇编代码
- `test_<id>.metadata.json`: 元数据（ACE分数、IBR分数等）

## 第五步：运行差分测试

### 5.1 单个测试用例运行

```bash
cd /Users/wangxu/1-project/sdc-fuzzing

# 运行差分测试
python3 tools/run_sdc_differential.py \
    artifacts/testcases/test_001.c \
    --compiler aarch64-linux-gnu-gcc \
    --qemu-binary qemu-aarch64 \
    --gem5-binary gem5/build/ARM/gem5.opt \
    --gem5-config gem5/configs/example/arm/sdc_kunpeng920_se.py \
    --fault-model bit-flip \
    --fault-target register \
    --fault-bit 0 \
    --fault-tick 1000000 \
    --timeout 300
```

### 5.2 批量测试运行

```bash
# 使用campaign runner运行批量测试
python3 tools/sdc_campaign.py \
    --db artifacts/sdc_vault.sqlite3 \
    --limit 10 \
    --fault-model bit-flip
```

### 5.3 输出结果

测试结果包含：
- `status`: 测试状态（matched/sdc_found/gem5_timeout等）
- `golden_digest`: QEMU输出的哈希值（金标准）
- `faulted_digest`: gem5输出的哈希值（故障注入后）
- `mcpat`: McPAT功耗分析结果

## 第六步：分析结果

### 6.1 查看测试结果

```bash
# 查看vault中的测试结果
python3 tools/sdc_scheduler.py rank --db artifacts/sdc_vault.sqlite3

# 查看特定测试的详细结果
cat artifacts/results/test_001_result.json
```

### 6.2 SDC判定逻辑

```
if gem5_return_code == 0 and gem5_hash != golden_hash:
    status = "sdc_found"  # 发现SDC
elif gem5_return_code != 0:
    status = "gem5_failed"  # gem5崩溃
elif gem5_hash == golden_hash:
    status = "matched"  # 正常匹配
```

## 附录A：gem5配置文件说明

### sdc_kunpeng920_se.py

这是为Kunpeng920微架构定制的gem5 SE模式配置：

```python
# 缓存配置（模拟Kunpeng920）
--l1i-size 64KiB
--l1d-size 64KiB
--l2-size 512KiB

# 内存配置
--mem-size 4GiB
--mem-channels 2

# CPU配置
--cpu-type o3  # 乱序执行CPU
--clk-freq 2.6GHz
```

### 故障注入参数

| 参数 | 说明 | 示例值 |
|------|------|--------|
| --fault-model | 故障模型 | bit-flip, stuck-at |
| --fault-target | 故障目标 | register, memory |
| --fault-bit | 位索引 | 0-63 |
| --fault-tick | 注入时刻 | 1000000 |

## 附录B：故障模型说明

### bit-flip（位翻转）
单比特翻转，模拟软错误。

### stuck-at（固定故障）
比特固定为0或1。

### burst（突发故障）
连续多位同时翻转。

## 附录C：性能优化建议

### 编译优化
```bash
# 使用ccache加速重编译
brew install ccache
export CC="ccache clang"
export CXX="ccache clang++"
```

### 运行优化
```bash
# 使用fast版本获得最佳性能
scons -j 8 build/ARM/gem5.fast

# 减少输出详细程度
./build/ARM/gem5.fast --quiet ...
```

### 内存优化
```bash
# 限制gem5内存使用
./build/ARM/gem5.opt --mem-size 2GiB ...
```

## 附录D：故障排除

### QEMU运行失败
```bash
# 检查动态库依赖
otool -L $(which qemu-aarch64)

# 设置库路径
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
```

### gem5运行失败
```bash
# 检查gem5输出
cat m5out-sdc/simout
cat m5out-sdc/simerr

# 检查guest输出
cat m5out-sdc/guest.stdout
cat m5out-sdc/guest.stderr
```

### McPAT运行失败
```bash
# 检查McPAT二进制
file mcpat/mcpat/mcpat

# 检查输入文件
cat m5out-sdc/mcpat_input.xml
```

## 附录E：参考资源

- gem5官方文档: https://www.gem5.org/documentation/
- ARM架构参考手册: https://developer.arm.com/documentation/
- Microprobe文档: 项目内 `microprobe/README.md`
- Kunpeng920架构: 项目内 `doc/kunpeng920.md`
