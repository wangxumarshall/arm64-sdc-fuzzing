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
        'spinlock_add/spinlock_stale_read.cpp',
        'spinlock_add/spinlock_stale_read_xchg.cpp',
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
        'misc/movbe_dump.cpp',
        'misc/movbe_dump_probe_a.cpp',
        'misc/movbe_dump_probe_b.cpp',
        'misc/movbe_dump_probe_c.cpp',
        'misc/movbe_dump_probe_d.cpp',
        'misc/movbe_dump_probe_e.cpp',
        'misc/movbe_dump_probe_f.cpp',
        'misc/movbe_dump_probe_g1.cpp',
        'misc/movbe_dump_probe_g2.cpp',
        'misc/movbe_dump_probe_h.cpp',
        'misc/movbe_dump_probe_x.cpp',
        'misc/movbe_dump_probe_xn.cpp',
        'misc/partial_store_forwarding.cpp',
        'misc/movmskpspd.cpp',
        'misc/movq2dq.cpp',
        'misc/mrn_nuke.cpp',
        'misc/mrn_pairs.cpp',
        'misc/mrn_reloaded.cpp',
        'misc/mrn_rmw.cpp',
        'misc/mrn_rmw_dump.cpp',
        'misc/mrn_flags.cpp',
        # ---- 2026-09-13 restored registrations (recovered from builddir/.ninja_log;
        # ---- original uncommitted meson.build was destroyed by a mistaken
        # ---- 'git checkout' during probe cleanup. Source of truth: every
        # ---- .o that the last full build actually compiled.)
        'misc/agu_stress_1src.cpp',
        'misc/agu_stress_2src.cpp',
        'misc/agu_stress_store_only.cpp',
        'misc/agu_stress_unaligned.cpp',
        'misc/core179_kernel_sdc_repro.cpp',
        'misc/movbe_dump_golden.cpp',
        'misc/movbe_l1d_variants.cpp',
        'misc/movbe_l1d_vs_l2.cpp',
        'misc/movbe_str_multiload.cpp',
        'misc/mrn_nuke_2src_add.cpp',
        'misc/mrn_nuke_2src_alu.cpp',
        'misc/mrn_nuke_2src_and.cpp',
        'misc/mrn_nuke_2src_eor.cpp',
        'misc/mrn_nuke_2src_sub.cpp',
        'misc/mrn_nuke_3src_alu.cpp',
        'misc/mrn_nuke_4src_alu.cpp',
        'misc/mrn_nuke_dense.cpp',
        'misc/mrn_nuke_recross.cpp',
        'misc/mrn_pairs_2src_alu.cpp',
        'misc/mrn_pairs_2src_alu_keep8.cpp',
        'misc/mrn_reloaded_2src_alu.cpp',
        'misc/mrn_rmw_diff_footprint.cpp',
        'misc/mrn_rmw_diff_timing_probe.cpp',
        'misc/mrn_rmw_fwd_vs_diff.cpp',
        'misc/mrn_rmw_fwd_vs_l1d.cpp',
        'misc/mrn_rmw_timing_probe.cpp',
        'misc/neon_rot_1src.cpp',
        'misc/neon_rot_2src.cpp',
        'misc/neon_rot_fwd_probe.cpp',
        'misc/neon_rot_ldr_at_top.cpp',
        'misc/neon_rot_ldr_at_top_dump.cpp',
        'misc/neon_rot_ldr_at_top_ldr4.cpp',
        'misc/neon_rot_ldr_at_top_ldr5.cpp',
        'misc/neon_rot_ldr_at_top_lsqfill.cpp',
        'misc/neon_rot_ldr_at_top_lsqfill_v2.cpp',
        'misc/neon_rot_ldr_at_top_mla.cpp',
        'misc/neon_rot_ldr_at_top_offdiag.cpp',
        'misc/neon_rot_ldr_at_top_prefetch.cpp',
        'misc/neon_rot_ldr_at_top_priv.cpp',
        'misc/neon_rot_ldr_at_top_rfport.cpp',
        'misc/neon_rot_ldr_at_top_rfport_v2.cpp',
        'misc/neon_rot_ldr_at_top_robfill.cpp',
        'misc/neon_rot_ldr_at_top_robfill_np.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_dump.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_gps.cpp',
        # 2026-09-13 readpath campaign K-axis cells (batch 2):
        # K5 decisive (interleaved far/near dual-source) + layout control,
        # K2 pure-load, K4/K4b far-gap, K7 pattern battery (4 cells),
        # K3 residency (4x-L1D footprint)
        'misc/neon_rot_ldr_at_top_rowmajor_k5far.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k5inter_rand.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k2pureload.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k4gap.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k4bgap.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k7pattern.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_k3res.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_dualcmp.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_scalar64.cpp',
        'misc/neon_rot_ldr_at_top_str3.cpp',
        'misc/neon_rot_ldr_at_top_rowmajor_str3_checkall.cpp',
        'misc/neon_rot_ldr_at_top_str4.cpp',
        'misc/neon_rot_ldr_at_top_str4_checkall.cpp',
        'misc/neon_rot_ldr_at_top_sub.cpp',
        'misc/neon_rot_ldr_at_top_tlbstress.cpp',
        'misc/neon_rot_nop_gap.cpp',
        'misc/neon_rot_stale_reload.cpp',
        'misc/neon_rot_store_only.cpp',
        'misc/neon_rot_u32x4.cpp',
        'misc/neon_rot_u8x16.cpp',
        'misc/probe_alu_fwd.cpp',
        'misc/probe_asm_fwd.cpp',
        'misc/sched_storm_baseline.cpp',
        'misc/sched_storm_futex.cpp',
        'misc/sched_storm_hybrid.cpp',
        'misc/sched_storm_thread.cpp',
        'misc/stress_fma.cpp',
        'misc/stress_sub.cpp',
        'misc/stress_xor.cpp',
        'cache/cache_stress_civac.cpp',
        'cache/cachebounce_sdc.cpp',
        'eigen_gemm/gemm_double_ab_split.cpp',
        'memory/mem_disambig_alu.cpp',
        'jit/move_elimination_8_jit.cpp',
        'jit/move_elimination_jit.cpp',
        'jit/part_store_fwd_jit.cpp',
        'jit/move_elimination_vec_evex_jit.cpp',
        'jit/zero_control_vec_sse_jit.cpp',
        'jit/zero_control_vec_evex_jit.cpp',
        'jit/zero_control_vec_vex_jit.cpp',
        'virtualization/vmx_io_exit.cpp',
        'virtualization/vmx_vmexit_cpuid.cpp',
        'virtualization/vmx_vmexit_from_cr8.cpp',
        'virtualization/vmx_vmexit_invd.cpp',
        'virtualization/vmx_vmexit_pause.cpp',
        'virtualization/vmx_vmexit_to_cr8.cpp',
        'virtualization/vmx_vmexit_to_dr7.cpp',
        'virtualization/vmx_vmexit_vmcall.cpp',
        'virtualization/vmxmsr.cpp',
        'memory/memcpy_variations_dyn.cpp',
        'memory/vmovnt1.cpp',
        'memory/vmovnt1_vex.cpp',
        'memory/vmovnt2.cpp',
        'memory/vmovnt2_vex.cpp',
        'memory/vmovnt3.cpp',
        'memory/vmovnt3_vex.cpp',
        # 算术运算测试（占位，后续填充）
        'arithmetic/adcx.cpp',
        'arithmetic/adcx_adox_interleaved.cpp',
        'arithmetic/adcxlong.cpp',
        'arithmetic/adox.cpp',
        #'arithmetic/bigint_mulx.cpp',
        #'arithmetic/cbw.cpp',
        #'arithmetic/fisttp.cpp',
        #'arithmetic/idiv16.cpp',
        #'arithmetic/idiv16_v2.cpp',
        #'arithmetic/idiv32_v2.cpp',
        #'arithmetic/idiv64.cpp',
        #'arithmetic/idiv8.cpp',
        #'arithmetic/idiv8_v2.cpp',
        #'arithmetic/idiv.cpp',
        #'arithmetic/immed_folding_rand_algo.cpp',
        #'arithmetic/immed_folding_osize.cpp',
        #'arithmetic/immed_folding_pow2count.cpp',
        #'arithmetic/immed_folding_check_each.cpp',
        #'arithmetic/immed_folding_check_after.cpp',
        #'arithmetic/immed_folding_onereg.cpp',
        #'arithmetic/immed_folding_cross.cpp',
        #'arithmetic/immed_folding_mix.cpp',
        #'arithmetic/immfolding.cpp',
        #'arithmetic/ix87.cpp',
        #'arithmetic/mulx.cpp',
        #'arithmetic/mulx32.cpp',
        #'arithmetic/mulx64.cpp',
        #'arithmetic/popcnt.cpp',
        #'arithmetic/rotate.cpp',
        #'arithmetic/shift.cpp',
        #'arithmetic/bmi.cpp',
        #'arithmetic/bit_test.cpp',
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
    # ARM64 dual-arch port: also build the ipsec _avx/_avx512 variants on
    # aarch64. These sources are portable (they call sandstone_ssl.h OpenSSL
    # EVP/HMAC/CMAC wrappers, no x86 intrinsics); their only ARM64 obstacle
    # was the cpu_haswell/cpu_skylake_avx512 symbols, now provided as
    # armv8_crc_crypto aliases via arm64_features.conf. Guarded by aarch64 so
    # x86 builds keep using the skx/hsw sets above unchanged (no duplicate
    # compile). On aarch64 the skx/hsw sets are never applied (see the
    # x86_64-only apply block below), so there is no duplication here either.
    if host_machine.cpu_family() == 'aarch64'
        tests_set_base.add(
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
                'ipsec/aes192_gcm/ipsec_aes192_gcm_avx.cpp',
                'ipsec/aes128_cbc/ipsec_aes128_cbc_aes_cmac_avx.cpp',
                'ipsec/aes128_cbc/ipsec_aes128_cbc_hmac_sha1_avx.cpp',
                'ipsec/aes128_cbc/ipsec_aes128_cbc_sha2_224_avx.cpp'
            )
        )
    endif
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
    local_eigen3_root = join_paths(meson.project_source_root(), '..', 'third_party', 'eigen-5.0.0-install')
    if fs.exists(join_paths(local_eigen3_root, 'include', 'eigen3', 'Eigen', 'Core'))
        eigen3_root = local_eigen3_root
    endif
endif

if eigen3_root != ''
    eigen3_include_dir = join_paths(eigen3_root, 'include', 'eigen3')
    if not fs.exists(join_paths(eigen3_include_dir, 'Eigen', 'Core'))
        error('Configured eigen3_root does not contain include/eigen3/Eigen/Core: ' + eigen3_root)
    endif
    message('Using repo-local Eigen from ' + eigen3_root)
    eigen3_dep = declare_dependency(
        compile_args : ['-isystem', eigen3_include_dir],
    )
else
    eigen3_dep = dependency('eigen3', include_type : 'system', static : dep_static)
endif

tests_set_base.add(
    when : eigen3_dep,
    if_true : files(
        'eigen_gemm/double14.cpp',
        'eigen_gemm/gemm_cdouble_dynamic_square.cpp',
        'eigen_gemm/gemm_cdouble_dynamic_square_dump.cpp',
        'eigen_gemm/gemm_double_dynamic_square.cpp',
        'eigen_gemm/gemm_double_dynamic_square_dump.cpp',
        'eigen_gemm/gemm_float_dynamic_square.cpp',
        'eigen_gemm/gemm_float_dynamic_square_dump.cpp',
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

# ARM64 dual-arch port: build eigen_svd_cdouble on aarch64 too. Upstream
# gates it behind tests_set_skx (AVX-512-only) because its .minimum_cpu =
# cpu_skylake_avx512. On aarch64 that symbol is provided as an
# armv8_crc_crypto alias (arm64_features.conf), and the SVD code itself
# (Eigen BDCSVD on std::complex<double>) is portable and already proven by
# its sibling eigen_svd_cdouble_noavx512 which passes on aarch64. Guarded
# by aarch64 so x86 builds keep using tests_set_skx above unchanged.
if host_machine.cpu_family() == 'aarch64'
    tests_set_base.add(
        when : eigen3_dep,
        if_true : files(
            'eigen_svd/svd_cdouble.cpp',
        )
    )
endif

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
        'crc/zpclmul.cpp',
        'crc/zpclmul_rep.cpp',
    )
)

# 直接查找 libisal 库（不依赖 pkg-config）
# isal 强制静态链入（static : true），把 isa-l CRC 代码打包进 opendcdiag 二进制，
# 不再运行时依赖 libisal.so.2. 这里不跟随 dep_static: 全局 -Ddependency_link=static
# 会让只有 .so 的 libarm_compute 链接失败, 故 isal 单独硬编码静态.
# /usr/lib/libisal.a 自包含（内部成员互引，无外部非标准符号），静态链入不缺符号.
isal_lib = cpp.find_library('isal', required : false, static : true)
# atomic: 提供 __atomic_load_16/__atomic_store_16/__atomic_compare_exchange_16
# 等 128 位原子符号 (cmpxchg16b 测试用). 本机未装 libatomic-static 包
# (无 libatomic.a), 故不强制 static:true — 否则 find_library 返回未找到,
# 链接缺符号. 走动态 libatomic.so.1, 打包时随包附带到 lib/ 即可.
atomic_lib = cpp.find_library('atomic', required : false)
# 如果找到 isal，添加 CRC 测试
#if isal_dep.found()
    #message('Adding CRC tests')   # 添加这一行
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
            'crc/crc32.cpp',                     
            'crc/crc32_fixed.cpp',               
            'crc/crc32_fixed_shuffled.cpp',      
        )
    )
    #endif

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
        zlib_dep,                 # 添加这一行，确保链接时能找到 zlib
    ],
    c_args : [
        tests_common_c_args,
    ],
    cpp_args : [
        tests_common_cpp_args,
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

# ---------------------------------------------------------------------------
# arithmetic_arm: 第三方优化库测试用例 (GMP / Arm Optimized Routines /
# Arm Compute Library / compiler-rt). mathlib/stringlib/arm_compute 走系统包;
# compiler-rt 软浮点 builtins 走系统 compiler-rt. 仅在 aarch64 上启用.
#
# 注: Arm Optimized Routines 的 fplib 是 32 位 ARM 软浮点汇编 (Cortex-M
# armv6-m / A32 at32), 为无硬件浮点的目标设计; aarch64 原生有硬件浮点,
# AOR 也没有 aarch64 fplib 端口, 且无任何测试源码引用 fplib 符号 (软浮点
# 由 crt_builtins.cpp 经 compiler-rt 的 __addsf3 等覆盖). 因此不再链接
# -lfplib. 详见 CLAUDE.md "ARM64 优化库依赖" 一节.
# ---------------------------------------------------------------------------
if host_machine.cpu_family() == 'aarch64'
    arm_opt_prefix = join_paths(meson.project_source_root(), '..', 'third_party', 'arm-opt-install')
    arm_opt_incdir = join_paths(arm_opt_prefix, 'include')
    arm_opt_libdir = join_paths(arm_opt_prefix, 'lib')

    # GMP: 系统包 (/usr/include, /usr/lib64)
    gmp_dep = dependency('gmp', static : dep_static, required : false)
    if not gmp_dep.found()
        gmp_lib = cc.find_library('gmp', required : false, static : dep_static)
        gmp_dep = declare_dependency(
            compile_args : ['-isystem', '/usr/include'],
            dependencies : [gmp_lib],
        )
    endif

    # Arm Optimized Routines: mathlib/stringlib. 强制静态链入 (.a), 消除对
    # 目标机 libmathlib.so/libstringlib.so 的运行时依赖 (它们不在 22.03 SP4
    # 标准仓库里, 随包附带 .so 又会带进 GLIBC_2.38 版本需求). find_library 的
    # static:true 让 meson 直接传 .a 路径而非 -l..., 避免同目录有 .so 时 ld
    # 默认选动态. 不链接 fplib (见上注释).
    aor_mathlib = cpp.find_library('mathlib', required : false,
        static : true, dirs : [arm_opt_libdir, '/usr/lib'])
    aor_stringlib = cpp.find_library('stringlib', required : false,
        static : true, dirs : [arm_opt_libdir, '/usr/lib'])
    aor_dep = declare_dependency(
        compile_args : ['-isystem', arm_opt_incdir],
        dependencies : [aor_mathlib, aor_stringlib],
    )

    # Arm Compute Library: libarm_compute (系统包 /usr/lib64; C++ 张量/算子)
    acl_dep = declare_dependency(
        compile_args : ['-isystem', arm_opt_incdir],
        link_args    : ['-L' + arm_opt_libdir, '-larm_compute'],
    )

    # compiler-rt builtins: 静态库, 软浮点整数实现 (__addsf3 等).
    # 优先 third_party/arm-opt-install/lib/libclang_rt.builtins-aarch64.a;
    # 否则回退系统 compiler-rt (openEuler: /usr/lib/clang/<ver>/lib/<triple>/
    # libclang_rt.builtins.a). -Wl,--whole-archive 防止软浮点符号被剔除.
    crt_builtins_local = join_paths(arm_opt_libdir, 'libclang_rt.builtins-aarch64.a')
    if fs.exists(crt_builtins_local)
        crt_builtins_path = crt_builtins_local
    else
        # 系统 compiler-rt (LLVM 资源目录): 静态软浮点 builtins.
        crt_builtins_path = '/usr/lib/clang/17/lib/aarch64-openEuler-linux-gnu/libclang_rt.builtins.a'
    endif
    crt_builtins_lib = declare_dependency(
        link_args : ['-Wl,--whole-archive',
                      crt_builtins_path,
                      '-Wl,--no-whole-archive'],
    )

    subdir('arithmetic_arm')
endif

subdir('arm64')
