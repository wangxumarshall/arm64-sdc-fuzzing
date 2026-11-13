/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b neon_rot_ldr_at_top_rowmajor_fp64_ldrw
 * @parblock
 * Narrow-GPR-access variant of neon_rot_ldr_at_top_rowmajor_fp64 (2026-11-11,
 * user directive: 32-bit GPR access form, completing the access-width curve
 * 128b q > 64b scalar(=0) > 32b > 16b).
 *
 * Axis: the per-element memory instructions become 32-bit GPR forms -
 *   load:  ldr q (128b)  ->  ldr %w (32b)
 *   store: str q (128b)  ->  str %w (32b), back-to-back pair preserved
 * Consumer axis kept FP64: the u32 value is widened EXACTLY to double
 * (ucvtf, integers <= 2^32 are exact), rotated through the scalar FP64
 * chain (fadd/fsub/fmul/fmax, slot = i%4), then narrowed back UB-free.
 *
 * Element = uint32_t; buffers sized to the parent's 16KB footprint
 * (4096 x 4B vs 1024 x 16B). Skeleton preserved: scratch ldr w at top
 * (unused, asm-volatile DCE guard), 2-src ldr w, back-to-back str w pair,
 * ascending/descending sweeps, per-sweep cold memcmp, golden recomputed
 * in init with the SAME code sequence.
 *
 * Determinism contract (no UB anywhere):
 *   widen:  (double)u32_value  - exact for <= 2^32, well-defined always
 *   rotate: a+b / a-b / a*b / fmax - all finite
 *   narrow: slot add/mul/max -> (uint64_t)d, guarded: d >= 2^64 (the
 *             (2^32-1)^2 product rounds UP to exactly 2^64.0, which would
 *             be UB for a plain cast) saturates to ~0ULL like fcvtzu
 *           slot sub         -> (uint64_t)(int64_t)d  (value in (-2^33,2^33))
 *           then truncate to uint32_t (low 32 bits, defined)
 *   The mul-slot saturating guard adds fcmp+fsel to that one slot - a
 *   documented cost of making the 32-bit form UB-free.
 *
 * Detection caveat (inherent to narrow-store chassis): the comparator sees
 * the element-width residue of the FP result - an FP-internal bit flip
 * that vanishes under narrow+truncate is masked. Any observed mismatch is
 * still a REAL SDC (golden uses the identical sequence).
 * @endparblock
 */

#include "sandstone.h"
#include <cstdint>
#include <cstring>

#if defined(__aarch64__)

#define FP64_LDRW_COUNT 4096   /* 4096 x 4B = 16KB, same bytes as parent 1024 x 16B */

struct Fp64LdrwData {
    uint32_t *srcA;
    uint32_t *srcB;
    uint32_t *scratch;
    uint32_t *expected;
};

static inline void store_w32(void *addr, uint32_t v) {
    __asm__ volatile ("str %w1, [%0]" : : "r"(addr), "r"(v) : "memory");
}

static inline uint32_t load_w32(const void *addr) {
    uint32_t v;
    __asm__ volatile ("ldr %w0, [%1]" : "=r"(v) : "r"(addr) : "memory");
    return v;
}

/* FP64 rotation on widened scalars; slot order mirrors the fp64 parent:
 * 0=fadd 1=fsub 2=fmul 3=fmax. Narrowing folded in, UB-free by construction. */
static inline uint32_t fp64_rot_w32(int slot, uint32_t a, uint32_t b) {
    const double fa = (double)a;
    const double fb = (double)b;
    uint64_t r;
    switch (slot) {
        case 0: r = (uint64_t)(fa + fb); break;
        case 1: r = (uint64_t)(int64_t)(fa - fb); break;
        case 2: {
            const double m = fa * fb;
            /* (2^32-1)^2 rounds up to exactly 2^64.0 -> plain cast would be UB;
             * saturate like fcvtzu (2^64.0 literal is exactly representable) */
            r = (m < 18446744073709551616.0) ? (uint64_t)m : ~0ULL;
            break;
        }
        default: r = (uint64_t)__builtin_fmax(fa, fb); break;
    }
    return (uint32_t)r;
}

#endif

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrw_init(struct test *test) {
    auto *data = static_cast<Fp64LdrwData *>(malloc(sizeof(Fp64LdrwData)));
    data->srcA = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));
    data->srcB = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));
    data->scratch = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));
    data->expected = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));

    memset_random(data->srcA, FP64_LDRW_COUNT * sizeof(uint32_t));
    memset_random(data->srcB, FP64_LDRW_COUNT * sizeof(uint32_t));
    memset_random(data->scratch, FP64_LDRW_COUNT * sizeof(uint32_t));

    /* golden: same widen->rotate->narrow sequence, computed in init */
    for (int i = 0; i < FP64_LDRW_COUNT; i++) {
        data->expected[i] = fp64_rot_w32(i % 4, load_w32(&data->srcA[i]), load_w32(&data->srcB[i]));
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrw_run(struct test *test, int cpu) {
    auto *data = static_cast<Fp64LdrwData *>(test->data);

    uint32_t *temp = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));
    uint32_t *dst  = static_cast<uint32_t *>(aligned_alloc(64, FP64_LDRW_COUNT * sizeof(uint32_t)));

    uint64_t sweep = 0;
    TEST_LOOP(test, 1 << 8) {
        const bool ascending = (sweep & 1) == 0;
        for (int n = 0; n < FP64_LDRW_COUNT; n++) {
            const int i = ascending ? n : (FP64_LDRW_COUNT - 1 - n);

            uint32_t unused_x = load_w32(&data->scratch[i]);
            (void)unused_x;

            uint32_t a = load_w32(&data->srcA[i]);
            uint32_t b = load_w32(&data->srcB[i]);
            uint32_t res = fp64_rot_w32(i % 4, a, b);

            store_w32(&temp[i], res);
            store_w32(&dst[i], res);
        }
        sweep++;

        if (memcmp(dst, data->expected, FP64_LDRW_COUNT * sizeof(uint32_t)) != 0) {
            report_fail_msg("neon_rot_ldr_at_top_rowmajor_fp64_ldrw data miscompare");
        }
    }

    free(dst);
    free(temp);
    return EXIT_SUCCESS;
}

static int neon_rot_ldr_at_top_rowmajor_fp64_ldrw_cleanup(struct test *test) {
    auto *data = static_cast<Fp64LdrwData *>(test->data);
    if (data) {
        free(data->srcA);
        free(data->srcB);
        free(data->scratch);
        free(data->expected);
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(neon_rot_ldr_at_top_rowmajor_fp64_ldrw, "32-bit GPR access variant of fp64 rowmajor: ldr/str w per element, FP64 rotation on widened scalars; access-width axis (128b q > 64b scalar=0 > 32b > 16b)")
    .test_init    = neon_rot_ldr_at_top_rowmajor_fp64_ldrw_init,
    .test_run     = neon_rot_ldr_at_top_rowmajor_fp64_ldrw_run,
    .test_cleanup = neon_rot_ldr_at_top_rowmajor_fp64_ldrw_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
