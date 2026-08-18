# Copyright 2022 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0
#
# arithmetic_arm: 测试用例调用第三方优化库 (GMP / Arm Optimized Routines /
# Arm Compute Library / compiler-rt), 用于在 ARM64 (Kunpeng) 平台上抓
# 整数/浮点/内存子系统的静默数据损坏 (SDC).
#
# 这些依赖统一安装在 third_party/arm-opt-install 下 (GMP 走系统路径).
# 顶层 tests/cpu/meson.build 已构造好 *_dep 变量 (gmp_dep, aor_dep, acl_dep,
# crt_builtins_lib), 本目录只负责把源文件按库分组挂到静态库.

arm_cpp_flags = [
    '-march=armv8.1-a+crc+crypto',
]

arithmetic_arm_sources = files(
    'gmp_bignum.cpp',
    'gmp_bigadd.cpp',
    'aor_math.cpp',
    'aor_string.cpp',
    'acl_gemm.cpp',
    'crt_builtins.cpp',
    'adcx_arm.cpp',
    'adcxlong_arm.cpp',
    'adcx_adox_interleaved_arm.cpp',
    'adox_arm.cpp',
    'bigint_mulx_arm.cpp',
    'cbw_arm.cpp',
    'fisttp_arm.cpp',
)

tests_arithmetic_arm_lib = static_library(
    'tests_arithmetic_arm',
    arithmetic_arm_sources,
    build_by_default: false,
    include_directories: [
        framework_incdir,
        tests_common_incdirs,
    ],
    dependencies: [
        boost_dep,
        gmp_dep,            # GMP (系统包, -lgmp)
        aor_dep,            # Arm Optimized Routines (math/string/fp)
        acl_dep,            # Arm Compute Library (libarm_compute)
        # compiler-rt builtins: -Wl,--whole-archive 防止软浮点符号 (__addsf3 等)
        # 被链接器当作"未使用"剔除. crt_builtins_lib 在顶层已用 whole-archive 包装.
        crt_builtins_lib,
    ],
    cpp_args: [
        debug_c_flags,
        default_cpp_flags,
        default_cpp_warn,
        march_generic_flags,
        arm_cpp_flags,
    ],
)

sandstone_tests += [
    tests_arithmetic_arm_lib,
]
