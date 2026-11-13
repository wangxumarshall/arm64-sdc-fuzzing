/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b neon_rot_ldr_at_top_rowmajor_fp64_ldrh
 * @parblock
 * Narrow-GPR-access variant of neon_rot_ldr_at_top_rowmajor_fp64 (2026-11-11,
 * user directive: 16-bit GPR access form, completing the access-width curve
 * 128b q > 64b scalar(=0) > 32b > 16b).
 *
 * Axis: the per-element memory instructions become 16-bit GPR forms -
 *   load:  ldr q (128b)  ->  ldrh %w (16b), zero-extended into a w-register
 *   store: str q (128b)  ->  strh %w (16b), back-to-back pair preserved
 * Consumer axis kept FP64: the narrow value is widened EXACTLY to double
 * (ucvtf, integers <= 2^16 are exact), rotated through the scalar FP64
 * chain (fadd/fsub/fmul/fmax, slot = i%4), then narrowed back with a
 * UB-free, architecturally deterministic sequence (see below).
 *
 * Element = uint16_t; buffers sized to the parent's 16KB footprint
 * (8192 x 2B vs 1024 x 16B). Skeleton preserved: scratch ldrh at top
 * (unused, asm-volatile DCE guard), 2-src ldrh, back-to-back strh/strh
 * pair, ascending/descending sweeps, per-sweep cold memcmp, golden
 * recomputed in init with the SAME code sequence.
 *
 * Determinism contract (no UB anywhere):
 *   widen:  (double)u32_value  - exact for <= 2^16, well-defined always
 *   rotate: a+b / a-b / a*b / fmax - all finite (|mul| <= 2^32 < 2^64)
 *   narrow: slot add/mul/max -> (uint64_t)d   (value in [0, 2^64) - in range)
 *           slot sub         -> (uint64_t)(int64_t)d (value in (-2^32, 2^32) -
 *                               in int64 range; wraparound is defined)
 *           then truncate to uint16_t (low 16 bits, defined)
 *
 * Detection caveat (inherent to narrow-store chassis): the comparator sees
 * the element-width residue of the FP result - an FP-internal bit flip
 * that vanishes under narrow+truncate is masked. Same applies to golden,
 * so any observed mismatch is still a REAL SDC.
 * @endparblock
 */

#include "sandstone.h"
#include <cstdint>
#include <cstring>

#if defined(__aarch64__)

#define FP64_LDRH_COUNT 8192   /* 8192 x 2B = 16KB, same bytes as parent 1024 x 16B */

struct Fp64LdrhData {
    uint16_t *srcA;
    uint16_t *srcB;
    uint16_t *scratch;
    uint16_t *expected;
};

static inline void store_h16(void *addr, uint32_t v) {
    __asm__ volatile ("strh %w1, [%0]" : : "r"(addr), "r"(v) : "memory");
}

static inline uint32_t load_h16(const void *addr) {
    uint32_t v;
    __asm__ volatile ("ldrh %w0, [%1]" : "=r"(v) : "r"(addr) : "memory");
    return v;
}

/* FP64 rotation on widened scalars; slot order mirrors the fp64 parent:
 * 0=fadd 1=fsub 2=fmul 3=fmax. Narrowing folded in, UB-free by construction. */
static inline uint16_t fp64_rot_h16(int slot, uint32_t a, uint32_t b) {
    const double fa = (double)a;
    const double fb = (double)b;
    uint64_t r;
    switch (slot) {
        case 0: r = (uint64_t)(fa + fb); break;
        case 1: r = (uint64_t)(int64_t)(fa - fb); break;
        case 2: r = (uint64_t)(fa * fb); break;
        default: r = (uint64_t)__builtin_fmax(fa, fb); break;
    }
    return (uint16_t)r;
}

#endif

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrh_init(struct test *test) {
    auto *data = static_cast<Fp64LdrhData *>(malloc(sizeof(Fp64LdrhData)));
    data->srcA = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));
    data->srcB = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));
    data->scratch = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));
    data->expected = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));

    memset_random(data->srcA, FP64_LDRH_COUNT * sizeof(uint16_t));
    memset_random(data->srcB, FP64_LDRH_COUNT * sizeof(uint16_t));
    memset_random(data->scratch, FP64_LDRH_COUNT * sizeof(uint16_t));

    /* golden: same widen->rotate->narrow sequence, computed in init */
    for (int i = 0; i < FP64_LDRH_COUNT; i++) {
        data->expected[i] = fp64_rot_h16(i % 4, load_h16(&data->srcA[i]), load_h16(&data->srcB[i]));
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrh_run(struct test *test, int cpu) {
    auto *data = static_cast<Fp64LdrhData *>(test->data);

    uint16_t *temp = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));
    uint16_t *dst  = static_cast<uint16_t *>(aligned_alloc(64, FP64_LDRH_COUNT * sizeof(uint16_t)));

    uint64_t sweep = 0;
    TEST_LOOP(test, 1 << 8) {
        const bool ascending = (sweep & 1) == 0;
        for (int n = 0; n < FP64_LDRH_COUNT; n++) {
            const int i = ascending ? n : (FP64_LDRH_COUNT - 1 - n);

            uint32_t unused_x = load_h16(&data->scratch[i]);
            (void)unused_x;

            uint32_t a = load_h16(&data->srcA[i]);
            uint32_t b = load_h16(&data->srcB[i]);
            uint16_t res = fp64_rot_h16(i % 4, a, b);

            store_h16(&temp[i], res);
            store_h16(&dst[i], res);
        }
        sweep++;

        if (memcmp(dst, data->expected, FP64_LDRH_COUNT * sizeof(uint16_t)) != 0) {
            report_fail_msg("neon_rot_ldr_at_top_rowmajor_fp64_ldrh data miscompare");
        }
    }

    free(dst);
    free(temp);
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrh_cleanup(struct test *test) {
    auto *data = static_cast<Fp64LdrhData *>(test->data);
    if (data) {
        free(data->srcA);
        free(data->srcB);
        free(data->scratch);
        free(data->expected);
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(neon_rot_ldr_at_top_rowmajor_fp64_ldrh, "16-bit GPR access variant of fp64 rowmajor: ldrh/strh per element, FP64 rotation on widened scalars; access-width axis (128b q > 64b scalar=0 > 32b > 16b)")
    .test_init    = neon_rot_ldr_at_top_rowmajor_fp64_ldrh_init,
    .test_run     = neon_rot_ldr_at_top_rowmajor_fp64_ldrh_run,
    .test_cleanup = neon_rot_ldr_at_top_rowmajor_fp64_ldrh_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
