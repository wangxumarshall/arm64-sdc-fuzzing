/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b neon_rot_ldr_at_top_rowmajor_fp64_ldpstp
 * @parblock
 * Memory-op-pairing variant of neon_rot_ldr_at_top_rowmajor_fp64 (2026-11-10,
 * user directive: probe LDP/STP pair pressure vs LDR/STR on the 179 trigger).
 *
 * Every 16B NEON ldr/str q of the parent becomes a paired 32B ldp/stp
 * (q, q) instruction - one instruction, two consecutive elements:
 *   scratch (unused, asm-volatile DCE guard): ldr q x COUNT -> ldp q,q x N/2
 *   srcA / srcB dual source:                   ldr q x COUNT -> ldp q,q x N/2
 *   temp/dst back-to-back store pair:          str q + str q  -> stp q,q + stp q,q
 * ALU rotation (FP64 fadd/fsub/fmul/fmax, slot = element_index % 4),
 * ascending/descending sweep order, per-sweep cold-path memcmp and
 * golden-recomputed-in-init are all preserved from the parent.
 *
 * What changes as a package (stated honestly): per-element memory-instruction
 * count halves (2.5 vs 5), each access doubles to 32B, and each step carries
 * two independent ALU chains (ILP x 2). "Pair pressure" is the axis under
 * test - not a single-instruction swap. Descending sweep visits elements in
 * pair granularity ((N-2,N-1) first) vs the parent's single-element order.
 *
 * FP determinism argument inherited from the parent: golden recomputed in
 * init with the SAME intrinsics on the SAME random bits; NEON FP ops are
 * non-trapping and NaN/denormal semantics architecturally specified; any
 * bit mismatch is a real SDC.
 * @endparblock
 */

#include "sandstone.h"
#include <cstdint>
#include <cstring>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#define NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT 1024

struct NeonRotLdrAtTopRowMajorFp64LdpStpData {
    uint64x2_t *srcA;
    uint64x2_t *srcB;
    uint64x2_t *scratch;
    uint64x2_t *expected;
};

#if defined(__aarch64__)

static inline void store_pair(void *addr, uint64x2_t v0, uint64x2_t v1) {
    __asm__ volatile ("stp %q0, %q1, [%2]" : : "w"(v0), "w"(v1), "r"(addr) : "memory");
}

static inline void load_pair(const void *addr, uint64x2_t &r0, uint64x2_t &r1) {
    __asm__ volatile ("ldp %q0, %q1, [%2]" : "=w"(r0), "=w"(r1) : "r"(addr) : "memory");
}

/* FP64 rotation, slot order mirrors the fp64 parent: 0=fadd 1=fsub
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

static int neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_init(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64LdpStpData *>(malloc(sizeof(NeonRotLdrAtTopRowMajorFp64LdpStpData)));
    data->srcA = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));
    data->srcB = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));
    data->scratch = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));
    data->expected = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));

    memset_random(data->srcA, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t));
    memset_random(data->srcB, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t));
    memset_random(data->scratch, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t));

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
        sanitize(data->srcA, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT);
        sanitize(data->srcB, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT);
    }
    /* golden: same FP64 rotating composition per element, on the same NEON units */
    for (int i = 0; i < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT; i++) {
        data->expected[i] = fp64_rot(i % 4, data->srcA[i], data->srcB[i]);
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_run(struct test *test, int cpu) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64LdpStpData *>(test->data);

    uint64x2_t *temp = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *dst  = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)));

    uint64_t sweep = 0;
    TEST_LOOP(test, 1 << 8) {
        const bool ascending = (sweep & 1) == 0;
        for (int p = 0; p < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT / 2; p++) {
            const int base = ascending ? 2 * p
                                       : (NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT - 2 - 2 * p);

            uint64x2_t t0, t1;
            load_pair(&data->scratch[base], t0, t1);
            (void)t0; (void)t1;

            uint64x2_t a0, a1, b0, b1;
            load_pair(&data->srcA[base], a0, a1);
            load_pair(&data->srcB[base], b0, b1);
            uint64x2_t r0 = fp64_rot(base % 4, a0, b0);
            uint64x2_t r1 = fp64_rot((base + 1) % 4, a1, b1);

            store_pair(&temp[base], r0, r1);
            store_pair(&dst[base], r0, r1);
        }
        sweep++;

        if (memcmp(dst, data->expected, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_LDPSTP_COUNT * sizeof(uint64x2_t)) != 0) {
            report_fail_msg("neon_rot_ldr_at_top_rowmajor_fp64_ldpstp data miscompare");
        }
    }

    free(dst);
    free(temp);
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_cleanup(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64LdpStpData *>(test->data);
    if (data) {
        free(data->srcA);
        free(data->srcB);
        free(data->scratch);
        free(data->expected);
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(neon_rot_ldr_at_top_rowmajor_fp64_ldpstp, "LDP/STP memory-op variant of fp64 rowmajor: paired 32B ldp/stp (q,q) replace single ldr/str q; FP64 rotation and skeleton preserved (pair-pressure axis)")
    .test_init    = neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_init,
    .test_run     = neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_run,
    .test_cleanup = neon_rot_ldr_at_top_rowmajor_fp64_ldpstp_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
