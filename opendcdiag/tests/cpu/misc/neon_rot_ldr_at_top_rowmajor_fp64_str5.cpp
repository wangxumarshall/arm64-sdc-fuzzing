/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b neon_rot_ldr_at_top_rowmajor_fp64_str5
 * @parblock
 * Store-count-dimension variant of neon_rot_ldr_at_top_rowmajor_fp64
 * (2026-11-13, user-directed str-count gradient completion).
 *
 * Single-variable axis: str per element 2 -> 5.  The parent's
 * back-to-back pair (temp, dst) becomes FIVE back-to-back stores of the
 * SAME res register to five independent buffers in the order
 * temp -> junk1 -> junk2 -> junk3 -> dst (junk1/junk2/junk3 are dead
 * stores, never read back; dst stays LAST so the per-sweep check
 * discipline is byte-identical to the parent).  Everything else is
 * byte-identical to the FP64 parent: the 3rd ldr at top (scratch), the
 * 2-src loads (srcA/srcB via inline-asm `ldr %q0` with "=w"), the FP64
 * rotation (fadd/fsub/fmul/fmax by i%4, reinterpreted raw random bits),
 * the ascending/descending sweep order, TEST_LOOP count 1<<8, and the
 * single per-sweep cold-path memcmp(dst, expected).
 *
 * Gradient context (all rowmajor-family chassis):
 *   str=2  FP64 parent   5.62/min pooled @96-189 AUTO fan (11-12
 *                         interleaved, 3x60min, 1011 fails all 179)
 *   str=3  integer str3  ~3.3/min (4 rounds, 133/164/51/49); FP64
 *                         str3 untested; integer str4 written 09-11
 *                         but never run
 *   str=4  fp64_str4     sibling, same protocol
 *   str=5  THIS TEST     30min @96-189 AUTO fan (user instruction)
 *
 * Pre-registered readouts (interpret together with str4):
 *   - monotone decay 2->4->5 : store-side pressure/timing erosion,
 *     more str pulls the store pair out of the trigger window;
 *   - cliff (parent fires, str4/str5 dead) : the 2-str adjacency is
 *     part of the recipe;
 *   - sustained/elevated : str count is a free axis on the trigger
 *     ridge, store-side pressure does not erode the window.
 * Check-granularity confound is NOT shared: per-sweep section stays a
 * single memcmp (the str3_checkall 3-memcmp lesson), so the cross-test
 * rate comparison against the FP64 parent is valid.
 * @endparblock
 */

#include "sandstone.h"
#include <cstdint>
#include <cstring>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#define NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT 1024

struct NeonRotLdrAtTopRowMajorFp64Str5Data {
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

/* FP64 rotation, slot order mirrors the FP64 parent: 0=fadd 1=fsub
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

static int neon_rot_ldr_at_top_rowmajor_fp64_str5_init(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Str5Data *>(malloc(sizeof(NeonRotLdrAtTopRowMajorFp64Str5Data)));
    data->srcA = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    data->srcB = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    data->scratch = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    data->expected = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));

    memset_random(data->srcA, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t));
    memset_random(data->srcB, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t));
    memset_random(data->scratch, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t));

    /* golden: same FP64 rotating composition, computed on the same NEON units */
    for (int i = 0; i < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT; i++) {
        data->expected[i] = fp64_rot(i % 4, data->srcA[i], data->srcB[i]);
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_str5_run(struct test *test, int cpu) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Str5Data *>(test->data);

    uint64x2_t *temp = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *dst  = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *junk1 = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *junk2 = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));
    uint64x2_t *junk3 = static_cast<uint64x2_t *>(aligned_alloc(64, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)));

    uint64_t sweep = 0;
    TEST_LOOP(test, 1 << 8) {
        const bool ascending = (sweep & 1) == 0;
        for (int n = 0; n < NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT; n++) {
            const int i = ascending ? n : (NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT - 1 - n);

            uint64x2_t unused_x = load_vec(&data->scratch[i]);
            (void)unused_x;

            uint64x2_t a = load_vec(&data->srcA[i]);
            uint64x2_t b = load_vec(&data->srcB[i]);
            uint64x2_t res = fp64_rot(i % 4, a, b);

            store_vec(&temp[i], res);
            store_vec(&junk1[i], res);
            store_vec(&junk2[i], res);
            store_vec(&junk3[i], res);
            store_vec(&dst[i], res);
        }
        sweep++;

        if (memcmp(dst, data->expected, NEON_ROT_LDR_AT_TOP_ROWMAJOR_FP64_STR5_COUNT * sizeof(uint64x2_t)) != 0) {
            report_fail_msg("neon_rot_ldr_at_top_rowmajor_fp64_str5 data miscompare");
        }
    }

    free(dst);
    free(junk3);
    free(junk2);
    free(junk1);
    free(temp);
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_str5_cleanup(struct test *test) {
    auto *data = static_cast<NeonRotLdrAtTopRowMajorFp64Str5Data *>(test->data);
    if (data) {
        free(data->srcA);
        free(data->srcB);
        free(data->scratch);
        free(data->expected);
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(neon_rot_ldr_at_top_rowmajor_fp64_str5, "Store-count variant of the FP64 rowmajor: 5 str per element (temp/junk1/junk2/junk3/dst, same res, dst last + single per-sweep memcmp = parent check discipline) at constant 3-ldr/FP64-rotation skeleton")
    .test_init    = neon_rot_ldr_at_top_rowmajor_fp64_str5_init,
    .test_run     = neon_rot_ldr_at_top_rowmajor_fp64_str5_run,
    .test_cleanup = neon_rot_ldr_at_top_rowmajor_fp64_str5_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
