/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b neon_rot_ldr_at_top_rowmajor_fp64
 * @parblock
 * Consumer-unit-axis variant of neon_rot_ldr_at_top_rowmajor (2026-11-06).
 *
 * Single-variable swap: the rotating ALU consumer is changed from the
 * integer ops (vaddq_u64/veorq_u64/vandq_u64/vorrq_u64) to double-precision
 * FP ops (vaddq_f64/vsubq_f64/vmulq_f64/vmaxq_f64), slot order preserved.
 * Everything else is byte-identical to the parent: the 3rd ldr at top
 * (scratch), the 2-src loads (srcA/srcB via inline-asm `ldr %q0` with
 * "=w"), the back-to-back str/str pair, the ascending/descending sweep
 * order, and the per-sweep cold-path memcmp. Buffers stay uint64x2_t and
 * are filled with raw random bits; values are reinterpreted to float64x2_t
 * only for the ALU op (vreinterpretq is a compile-time register-class
 * no-op, so the load/store instructions and the memory-side layout are
 * unchanged).
 *
 * Purpose: the core-179 trigger recipe is established for INTEGER ALU
 * rotation (mrn_nuke_2src_alu scalar family; neon_rot rowmajor SIMD
 * family, ~8.5-16.6 fail/min) but the FP side was never tested under
 * rotation. The only FP datapoints are: stress_fma (single fmadd, no
 * rotation, 5min 0-fail - uninformative since single-INTEGER-instruction
 * variants also fail to trigger) and eigen float/double (triggers, but
 * through an uncontrolled compiler-inlined schedule - not attributable
 * to "FP vs integer"). This variant answers: does FP64 rotation land
 * inside the same 179 trigger window when the load/store structure is
 * held fixed?
 *
 * FP-specific determinism argument (golden recomputed in init with the
 * SAME intrinsics on the SAME random bits): NEON FP ops are
 * non-trapping; denormals/NaN/Inf propagate deterministically; FMAX
 * NaN semantics ("if one operand is NaN return the other") are
 * architecturally specified. No fmul+fadd adjacency exists inside a
 * switch branch, so -ffp-contract=fast has nothing to fuse. Any bit
 * mismatch between hot-loop result and golden is therefore a real SDC,
 * not a precision artifact. Inputs are raw random bit patterns - as
 * doubles they include NaN/Inf/denormals, mirroring the parent's
 * "random bits" input axis on the integer side.
 * @endparblock
 */

#include "sandstone.h"
#include <cstdint>
#include <cstring>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#define NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT 1024

struct NeonRotLdrAtTopRowMajorFp64Data {
    uint64x2_t *srcA;
    uint64x2_t *srcB;
    uint64x2_t *scratch;
    uint64x2_t *expected;
};

#if defined(__aarch64__)

static inline void store_vec(void *addr, uint64x2_t val) {
    vst1q_u64(static_cast<uint64_t *>(addr), val);
}

static inline uint64x2_t load_vec(const void *addr) {
    uint64x2_t res;
    __asm__ volatile ("ldr %q0, [%1]" : "=w"(res) : "r"(addr) : "memory");
    return res;
}

/* FP64 rotation, slot order mirrors the integer parent: 0=fadd 1=fsub
 * 2=fmul 3=fmax. Reinterpretations are compile-time no-ops. */
static inline uint64x2_t fp64_rot(int slot, uint64x2_t a, uint64x2_t b) {
    const float64x2_t fa = vreinterpretq_f64_u64(a);
    const float64x2_t fb = vreinterpretq_f64_u64(b);
    float64x2_t fres;
    switch (slot) {
        case 0: fres = vaddq_f64(fa, fb); break;
        case 1: fres = vsubq_f64(fa, fb); break;
        case 2: fres = vmulq_f64(fa, fb); break;
        default: fres = vmaxq_f64(fa, fb); break;
    }
    return vreinterpretq_u64_f64(fres);
}

#endif

static int neon_rot_ldr_at_top_rowmajor_fp64_init(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Data *>(malloc(sizeof(NeonRotLdrAtTopRowMajorFp64Data)));
    data->srcA = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));
    data->srcB = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));
    data->scratch = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));
    data->expected = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));

    memset_random(data->srcA, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t));
    memset_random(data->srcB, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t));
    memset_random(data->scratch, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t));

    /* NaN-free inputs (2026-11-13 root-cause fix; spec appendix v2.1 in
     * docs/ADAPTIVE_MEM_SDC_DESIGN_20261113.md): GCC reorders operands of
     * the commutative FP ops between the two inlined copies of the rotation
     * (this golden loop vs the hot loop), and for a BOTH-sNaN lane AArch64
     * returns the quieted *first* operand — operand-order dependent, so the
     * copies can diverge bit-exactly (false positive on healthy cores;
     * confirmed live in build 33f2edb0df13: init fmul(A,B) vs hot
     * fmul(B,A)).  Clearing the all-ones exponent at fill time removes the
     * NaN/Inf payload ambiguity; finite arithmetic is bit-deterministic
     * under operand reordering.  Touches ~0.1% of words. */
    {
        auto sanitize = [](uint64x2_t *buf, int n) {
            auto *w = reinterpret_cast<uint64_t *>(buf);
            for (int k = 0; k < n * 2; k++)
                if ((w[k] >> 52 & 0x7ff) == 0x7ff)
                    w[k] &= ~(1ULL << 62);
        };
        sanitize(data->srcA, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT);
        sanitize(data->srcB, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT);
    }
    /* golden: same FP64 rotating composition, computed on the same NEON units */
    for (int i = 0; i < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT; i++) {
        data->expected[i] = fp64_rot(i % 4, data->srcA[i], data->srcB[i]);
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_run(struct test *test, int cpu) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Data *>(test->data);

    uint64x2_t *temp = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *dst  = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)));

    uint64_t sweep = 0;
    TEST_LOOP(test, 1 << 8) {
        const bool ascending = (sweep & 1) == 0;
        for (int n = 0; n < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT; n++) {
            const int i = ascending ? n : (NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT - 1 - n);

            uint64x2_t unused_x = load_vec(&data->scratch[i]);
            (void)unused_x;

            uint64x2_t a = load_vec(&data->srcA[i]);
            uint64x2_t b = load_vec(&data->srcB[i]);
            uint64x2_t res = fp64_rot(i % 4, a, b);

            store_vec(&temp[i], res);
            store_vec(&dst[i], res);
        }
        sweep++;

        if (memcmp(dst, data->expected, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_COUNT * sizeof(uint64x2_t)) != 0) {
            report_fail_msg("neon_rot_ldr_at_top_rowmajor_fp64 data miscompare");
        }
    }

    free(dst);
    free(temp);
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_cleanup(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Data *>(test->data);
    if (data) {
        free(data->srcA);
        free(data->srcB);
        free(data->scratch);
        free(data->expected);
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(neon_rot_ldr_at_top_rowmajor_fp64, "FP64 consumer variant of rowmajor: rotating fadd/fsub/fmul/fmax instead of integer ALU, load/store skeleton identical (integer vs high-precision-FP rotation axis)")
    .test_init    = neon_rot_ldr_at_top_rowmajor_fp64_init,
    .test_run     = neon_rot_ldr_at_top_rowmajor_fp64_run,
    .test_cleanup = neon_rot_ldr_at_top_rowmajor_fp64_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
