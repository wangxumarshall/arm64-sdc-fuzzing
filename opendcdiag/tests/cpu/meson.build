# Copyright 2022 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0

dep_static = get_option('dependency_link') == 'static'
# 在文件开头或合适位置添加 isal 依赖检测
isal_dep = dependency('libisal', required : false, static : dep_static)

fs = import('fs')
setmod = import('sourceset')

tests_config = configuration_data()
tests_set_base = setmod.source_set()
tests_set_hsw = setmod.source_set()
tests_set_skx = setmod.source_set()

tests_common_c_args = [
    debug_c_flags,
    default_c_warn,
    default_c_flags,
    march_flags,
]

tests_common_cpp_args = [
    debug_c_flags,
    default_cpp_warn,
    default_cpp_flags,
    march_flags,
]

tests_common_incdirs = [
    framework_incdir,
]

if target_machine.cpu_family() != 'x86_64'
    # non-x86 Eigen does not get as much attention so this annoying
    # warning was left behind
    tests_common_cpp_args += '-Wno-deprecated-copy'
endif
if target_machine.system() == 'windows' and get_option('buildtype') == 'debug'
    # Force a little bit of optimization, otherwise we get:
    # Fatal error: tests/libtests_base.a.p/eigen_svd_svd_cdouble_noavx512.cpp.obj: file too big
    tests_common_cpp_args += '-Og'
endif

tests_set_base.add(
    files(
        'ifs/sandstone_ifs.c',
        'ifs/ifs.c',
        'memory/memcpy1.cpp',
        'memory/memcpy0.cpp',                        
        'memory/memcpy_l1d_size.cpp',                 
        'memory/memcpy_l2_cache_size.cpp',           
        'memory/memcpy_l3_cache_size.cpp',
        'memory/memcpy_sem.cpp',           
        'memory/memcpy_shuffle.cpp',       
        'memory/memcpy_shuffle_v2.cpp',
        'memory/mfence_pure.cpp',
        'memory/mfence.cpp',
        'memory/modified_sort.cpp',
        'memory/mem_disambiguation.cpp',    
        'cache/cachebounce.cpp',
        'cache/cache_stress_aggressor.cpp',
        'vector/swizzle.cpp',
        'vector/insert_extract.cpp',
        'vector/kreg1.cpp',
        'vector/kreg2.cpp',
        'vector/kreg3.cpp',
        'vector/kreg4.cpp',
        'vector/kreg5.cpp',
        'vector/kreg6.cpp',
        'vector/kreg7.cpp',
        'vector/kreg8.cpp',
        'vector/kreg9.cpp',
        'atomic/atomic_simd_128.cpp',
        #'atomic/atomic_simd_128_unaligned.cpp',
        'atomic/atomic_simd_256.cpp',
        #'atomic/atomic_simd_256_unaligned.cpp',
        'atomic/atomic_simd_512.cpp',
        'atomic/atomic_seq_cst.cpp',
        'fma/fma.cpp',
        'fma/fma_patterns_avx512_pd.cpp',
        'fma/fma_patterns_avx512_ps.cpp',
        'fma/fma_tail_avx2.cpp',
        'fma/fma_tail_avx512.cpp',
        'fma/fmatail_avx2.cpp',
        'fma/fmatail_avx512.cpp',
        'fma/fmatail_double_nested_avx2.cpp',
        'fma/fmatail_double_nested_avx512.cpp',
        'fma/fmatail_nested_avx2.cpp',
        'fma/fmatail_nested_avx512.cpp',
        'gather/gather_f32.cpp',
        'gather/gather_f64.cpp',
        'gather/gather_i32.cpp',
        'gather/gather_i64.cpp',
        'gather/gatherscatter_f32.cpp',
        'gather/gatherscatter_f64.cpp',
        'gather/gatherscatter_i32.cpp',
        'gather/gatherscatter_i64.cpp',
        'gather/gatherscatterpd.cpp',
        'gather/gatherscatterps.cpp',
        'spinlock/spinlock_array.cpp',
        'spinlock/spinlock_bank.cpp',
        'spinlock/spinlock_cross_socket.cpp',
        'spinlock/spinlock_crosses_cacheline.cpp',
        'spinlock/spinlock_mini.cpp',
        'spinlock/spinlock_randomsweep.cpp',
        'spinlock/spinlock_rmw_cmpxchg.cpp',
        'spinlock/spinlock_rmw_cmpxchg_pause.cpp',
        'spinlock/spinlock_rmw_xchg.cpp',
        'spinlock/spinlock_rmw_xchg_pause.cpp',
        'spinlock/spinlock_same_core.cpp',
        'spinlock/spinlock_stress.cpp',
        'spinlock/spinlock_stress_bts.cpp',
        'spinlock/spinlock_stress_cmpxchg.cpp',
        'spinlock/spinlock_stress_cmpxchg_even_odd.cpp',
        'spinlock/spinlock_stress_cmpxchg16b.cpp',
       # 'spinlock/spinlock_unaligned.cpp',
        'spinlock/spinlock_with_hle.cpp',
        'lock/lock_instr.cpp',
        'lock/lockgen.cpp',
        'lock/lockless_cmpxchg.cpp',
        'lock/lockless_cmpxchg8b.cpp',
        'lock/lockless_cmpxchg16b.cpp',
        'lock/locks.cpp',
        'lock/locks_ccb.cpp',
        'lock/locks_ccb_xch_only.cpp',
        'lock/locks_xch_only.cpp',
        'load_port/load_port.cpp',
        'mesh/mesh_upi_avx_sym.cpp',
        'mesh/mesh_upi_avx2_asymm_distrib_int.cpp',
        'mesh/mesh_upi_avx2_asymm_distrib_write_int.cpp',
        'mesh/mesh_upi_avx2_asymm_int.cpp',
        'mesh/mesh_upi_avx2_asymm_write_int.cpp',
        'mesh/mesh_upi_avx2_read_L3_int.cpp',
        'mesh/mesh_upi_avx2_read_only_int.cpp',
        'mesh/mesh_upi_avx2_symm_int.cpp',
        'mesh/mesh_upi_avx2_write_only_int.cpp',
        'mesh/mesh_upi_avx512_asymm_distrib_int.cpp',
        'mesh/mesh_upi_avx512_asymm_distrib_write_int.cpp',
        'mesh/mesh_upi_avx512_asymm_int.cpp',
        'mesh/mesh_upi_avx512_asymm_read_L3_int.cpp',
        'mesh/mesh_upi_avx512_asymm_read_only_int.cpp',
        'mesh/mesh_upi_avx512_asymm_write_int.cpp',
        'mesh/mesh_upi_avx512_asymm_write_only_int.cpp',
        'mesh/mesh_upi_avx512_sym.cpp',
        'mesh/mesh_upi_avx512_symm_int.cpp',
        'mesh/mesh_upi_sse_asymm_distrib_int.cpp',
        'mesh/mesh_upi_sse_asymm_distrib_write_int.cpp',
        'mesh/mesh_upi_sse_asymm_int.cpp',
        'mesh/mesh_upi_sse_asymm_write_int.cpp',
        'mesh/mesh_upi_sse_read_L3_int.cpp',
        'mesh/mesh_upi_sse_read_only_int.cpp',
        'mesh/mesh_upi_sse_sym.cpp',
        'mesh/mesh_upi_sse_symm_int.cpp',
        'mesh/mesh_upi_sse_write_only_int.cpp',
        'misc/mite.cpp',
        'misc/movdq2q.cpp',
        'misc/movbe.cpp',
        'misc/partial_store_forwarding.cpp',
        'misc/movmskpspd.cpp',
        'misc/movq2dq.cpp',
        'misc/mrn_nuke.cpp',
        'misc/mrn_pairs.cpp',
        'misc/mrn_reloaded.cpp',
        'misc/mrn_rmw.cpp',
        'misc/mrn_flags.cpp',
        'jit/move_elimination_8_jit.cpp',
        'jit/move_elimination_jit.cpp',
        'jit/part_store_fwd_jit.cpp',
        'jit/move_elimination_vec_evex_jit.cpp',
        'jit/zero_control_vec_sse_jit.cpp',
        'jit/zero_control_vec_evex_jit.cpp',
        'jit/zero_control_vec_vex_jit.cpp'
    )
)

if framework_config.get('SANDSTONE_SSL_BUILD') == 1
    tests_set_base.add(
        when : crypto_dep,
        if_true: files(
            # Tests that depends on openssl
            'openssl/openssl_sha.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_aes_cmac_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_aes_xcbc_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha1_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha224_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha256_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha384_x86_64.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha512_x86_64.cpp',
            'ipsec/aes128_cbc/ipsec_aes128_cbc_aes_cmac_sse.cpp',
            'ipsec/aes128_cbc/ipsec_aes128_cbc_hmac_sha1_sse.cpp',
            'ipsec/aes128_cbc/ipsec_aes128_cbc_sha2_224_sse.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_sha2_384_sse.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_sha2_512_sse.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_xcbc_96_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha1_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha224_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha256_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha384_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha512_sse.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_xcbc_sse.cpp',
            'ipsec/aes256_cbc/ipsec_aes256_cbc_hmac_sha1_sse.cpp',
            'ipsec/aes256_cbc/ipsec_aes256_cbc_sha2_224_sse.cpp',
            'ipsec/aes192_gcm/ipsec_aes192_gcm_sse.cpp' 
        )
    )
    tests_set_skx.add(
        when : crypto_dep,
        if_true: files(
            'ipsec/3des_docsis/ipsec_3des_docsis_aes_cmac_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_aes_xcbc_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha1_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha224_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha256_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha384_avx512.cpp',
            'ipsec/3des_docsis/ipsec_3des_docsis_hmac_sha512_avx512.cpp',
            'ipsec/aes192_gcm/ipsec_aes192_gcm_avx512.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_sha2_384_avx.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_sha2_512_avx.cpp',
            'ipsec/aes192_cbc/ipsec_aes192_cbc_xcbc_96_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha1_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha224_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha256_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha384_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_hmac_sha512_avx.cpp',
            'ipsec/aes192_ctr/ipsec_aes192_ctr_xcbc_avx.cpp',
            'ipsec/aes256_cbc/ipsec_aes256_cbc_hmac_sha1_avx.cpp',
            'ipsec/aes256_cbc/ipsec_aes256_cbc_sha2_224_avx.cpp',
            'ipsec/aes256_cbc/ipsec_aes256_cbc_sha2_256_avx.cpp',
            'ipsec/aes192_gcm/ipsec_aes192_gcm_avx.cpp'
        )
    )
    tests_set_hsw.add(
        when : crypto_dep,
        if_true: files(
            'ipsec/aes128_cbc/ipsec_aes128_cbc_aes_cmac_avx.cpp',
            'ipsec/aes128_cbc/ipsec_aes128_cbc_hmac_sha1_avx.cpp',
            'ipsec/aes128_cbc/ipsec_aes128_cbc_sha2_224_avx.cpp'
        )
    )
elif target_machine.system() == 'windows'
    tests_set_base.add(
        files(
            # Print skip in windows
            'openssl/openssl_sha.cpp',
        )
    )
    # TODO: Windows add ipsec
endif

eigen3_root = get_option('eigen3_root')
if eigen3_root == ''
    # Vendored Eigen 5.0.1 source tree (flat layout: third-part/Eigen/Core).
    # Relative paths resolve against this meson.build's directory (tests/cpu/),
    # so '../../third-part' = opendcdiag/third-part.
    local_eigen3_root = '../../third-part'
    if fs.exists(join_paths(local_eigen3_root, 'Eigen', 'Core'))
        eigen3_root = local_eigen3_root
    endif
endif

if eigen3_root != ''
    # Source-tree layout: headers live directly under <root>/Eigen.
    if not fs.exists(join_paths(eigen3_root, 'Eigen', 'Core'))
        error('Configured eigen3_root does not contain Eigen/Core: ' + eigen3_root)
    endif
    message('Using repo-local Eigen from ' + eigen3_root)
    eigen3_dep = declare_dependency(
        include_directories : include_directories(eigen3_root),
    )
else
    eigen3_dep = dependency('eigen3', version : '>=5.0', include_type : 'system', static : dep_static, required : false)
    if not eigen3_dep.found()
        error('No Eigen found: neither vendored third-part/Eigen/Core nor a system eigen3 >= 5.0. ' +
              'The vendored tree should be present; if missing, restore third-part/ from the repo.')
    endif
endif

tests_set_base.add(
    when : eigen3_dep,
    if_true : files(
        'eigen_gemm/double14.cpp',
        'eigen_gemm/gemm_cdouble_dynamic_square.cpp',
        'eigen_gemm/gemm_double_dynamic_square.cpp',
        'eigen_gemm/gemm_float_dynamic_square.cpp',
        'eigen_sparse/eigen_sparse.cpp',
        'eigen_svd/svd.cpp',
        'eigen_svd/svd_cdouble_noavx512.cpp',
        'eigen_svd/svd_double.cpp',
        'eigen_svd/svd_fvectors.cpp',
        'eigen_svd_jacobi/svd.cpp',
        'eigen_svd_jacobi/svd_cdouble.cpp',
        'eigen_svd_jacobi/svd_double.cpp',
        'eigen_svd_jacobi/svd_fvectors.cpp',
    )
)

tests_set_skx.add(
    when : eigen3_dep,
    if_true : files(
        'eigen_svd/svd_cdouble.cpp',
    )
)

zstd_dep = dependency('libzstd', static : dep_static)
tests_set_base.add(
    when : zstd_dep,
    if_true : files(
        'zstd/test.c',
    )
)

zlib_dep = dependency('zlib', static : dep_static)
tests_set_base.add(
    when : zlib_dep,
    if_true : files(
        'zlib/fuzz.c',
        'zlib/test.c',
    )
)

# 直接查找 libisal 库（不依赖 pkg-config）
isal_lib = cpp.find_library('isal', required : false)
atomic_lib = cpp.find_library('atomic', required : false)
# Pure-software CRC tests (no libisal dependency) — always built.
tests_set_base.add(
    files(
        'crc/crc32.cpp',
        'crc/crc32_fixed.cpp',
        'crc/crc32_fixed_shuffled.cpp',
    )
)
# libisal-backed CRC tests — only when libisal is available, otherwise the
# <isa-l/crc.h> includes would fail to compile.
if isal_lib.found() or isal_dep.found()
    message('Adding libisal CRC tests')
    tests_set_base.add(
        files(
            'crc/isal_crc64_ecma182_norm.cpp',
            'crc/isal_crc64_ecma182_refl.cpp',
            'crc/isal_crc32_gzip.cpp',
            'crc/isal_crc_ieee.cpp',
            'crc/isal_crc_iscsi.cpp',
            'crc/isal_crc64_iso_norm.cpp',
            'crc/isal_crc64_iso_refl.cpp',
            'crc/isal_crc64_jones_norm.cpp',
            'crc/isal_crc64_jones_refl.cpp',
            'crc/isal_crc_t10dif.cpp',
        ),
        dependencies : isal_lib,
    )
endif

tests_config_base = tests_set_base.apply(tests_config)

tests_base_a = static_library(
    'tests_base',
    sources : tests_config_base.sources(),
    build_by_default: false,
    include_directories : [
        tests_common_incdirs,
    ],
    dependencies: [
        tests_config_base.dependencies(),
        boost_dep,
        isal_lib,   # 添加这一行
        atomic_lib, # 添加这一行
    ],
    c_args : [
        tests_common_c_args,
    ],
    cpp_args : [
        tests_common_cpp_args,
        '-O2',   # 强制优化
    ],
)

sandstone_tests += [
    tests_base_a,
]

if host_machine.cpu_family() == 'x86_64'
    march_hsw = [
        '-march=haswell',
        '-mtune=skylake',
    ]
    march_skx = [
        '-march=skylake-avx512',
        '-mtune=skylake-avx512',
    ]

    # Check if march_base has a higher CPU target, in which case
    # we should not downgrade
    if cc.has_define('__AVX512F__', args: tests_common_c_args)
        # We're already targetting AVX512
        march_skx = []
        march_hsw = []
    elif cc.has_define('__AVX2__', args: tests_common_c_args)
        march_hsw = []
    endif

    tests_config_hsw = tests_set_hsw.apply(tests_config)

    tests_hsw_a = static_library(
        'tests_hsw',
        sources : tests_config_hsw.sources(),
        dependencies : tests_config_hsw.dependencies(),
        build_by_default: false,
        include_directories : [
            tests_common_incdirs,
        ],
        c_args : [
            tests_common_c_args,
            march_hsw,
        ],
        cpp_args : [
            tests_common_cpp_args,
            march_hsw,
            '-DEigen=EigenAVX2',
        ],
    )

    tests_config_skx = tests_set_skx.apply(tests_config)

    tests_skx_a = static_library(
        'tests_skx',
        sources : tests_config_skx.sources(),
        build_by_default: false,
        include_directories : [
            tests_common_incdirs,
        ],
        dependencies: [
            tests_config_skx.dependencies(),
            boost_dep,
        ],
        c_args : [
            tests_common_c_args,
            march_skx,
        ],
        cpp_args : [
            tests_common_cpp_args,
            march_skx,
            '-DEigen=EigenAVX512',
        ],
    )

    sandstone_tests += [
        tests_hsw_a,
        tests_skx_a,
    ]

    unittests_sources += files(
        'ifs/unit/ifs_unit_utils.cpp',
        'ifs/unit/ifs_unittests.cpp',
        )
endif

subdir('arm64')
