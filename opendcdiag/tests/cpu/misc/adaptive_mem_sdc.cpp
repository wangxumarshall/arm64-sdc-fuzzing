/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b adaptive_mem_sdc
 * @parblock
 * Adaptive memory-access SDC test (2026-11-13).
 * Spec: docs/ADAPTIVE_MEM_SDC_DESIGN_20261113.md (v2, approved);
 * plan: docs/superpowers/plans/2026-11-13-adaptive-mem-sdc.md.
 *
 * Cross-machine axiom (user-provided): the machine's widest SIMD ISA is
 * the most SDC-prone — NEON(128b) on Kunpeng 920, SVE(256b) on 920B,
 * SVE2 on 950.  This test probes HWCAP once per child, then every
 * short-lived fork_each_test child picks one combo from the 30-entry
 * priority sequence (dtype FP64>int > ldr 2>3 > str 2>3/4 > load
 * fp64rot/introt/empty/mla/sub) and runs it for its whole lifetime:
 * normal mode by wall-clock slice (30min per combo, anchor in shm),
 * verify mode by a round-robin counter (each child takes the next combo
 * so a short -T run covers all 30 goldens).
 *
 * On SDC the failing child tags its report_fail_msg with the combo
 * identity and sets a shm flag that makes later children idle; the
 * campaign script SIGKILLs the main process on the first fail block
 * (the framework itself never exits on fail).
 *
 * Env contract (campaign script): ADAPTIVE_MEM_SDC_KEY (shm name
 * suffix; fresh key = fresh anchor), ADAPTIVE_MEM_SDC_VERIFY=1 (verify
 * mode), ADAPTIVE_MEM_SDC_COVFILE (per-child combo trace, one line per
 * init: "<iso> <pid> <isa> <mode> <combo>").
 * @endparblock
 */

#include "sandstone.h"
#include "adaptive_mem_sdc.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <type_traits>
#include <fcntl.h>
#include <unistd.h>

#if defined(__aarch64__)
#include <sys/auxv.h>
#include <asm/hwcap.h>
#include <sys/mman.h>
#endif

/* ------------------------------------------------------------------ */
/* Combo priority table (spec §2, exact 30 rows)                       */
/* ------------------------------------------------------------------ */

extern "C" const struct ComboDef kComboTable[ADAPT_COMBO_COUNT] = {
    /* #0-5  FP64 segment: ldr2 str2/3/4, ldr3 str2/3/4 — all FP64 rotation */
    { DT_FP64, 2, 2, LOAD_FP64ROT, "fp64rot" },
    { DT_FP64, 2, 3, LOAD_FP64ROT, "fp64rot" },
    { DT_FP64, 2, 4, LOAD_FP64ROT, "fp64rot" },
    { DT_FP64, 3, 2, LOAD_FP64ROT, "fp64rot" },
    { DT_FP64, 3, 3, LOAD_FP64ROT, "fp64rot" },
    { DT_FP64, 3, 4, LOAD_FP64ROT, "fp64rot" },
    /* #6-29 int segment: ldr 2 then 3, str 2/3/4, loads in priority order */
    { DT_INT, 2, 2, LOAD_INTROT, "introt" },
    { DT_INT, 2, 2, LOAD_EMPTY,  "empty"  },
    { DT_INT, 2, 2, LOAD_MLA,    "mla"    },
    { DT_INT, 2, 2, LOAD_SUB,    "sub"    },
    { DT_INT, 2, 3, LOAD_INTROT, "introt" },
    { DT_INT, 2, 3, LOAD_EMPTY,  "empty"  },
    { DT_INT, 2, 3, LOAD_MLA,    "mla"    },
    { DT_INT, 2, 3, LOAD_SUB,    "sub"    },
    { DT_INT, 2, 4, LOAD_INTROT, "introt" },
    { DT_INT, 2, 4, LOAD_EMPTY,  "empty"  },
    { DT_INT, 2, 4, LOAD_MLA,    "mla"    },
    { DT_INT, 2, 4, LOAD_SUB,    "sub"    },
    { DT_INT, 3, 2, LOAD_INTROT, "introt" },
    { DT_INT, 3, 2, LOAD_EMPTY,  "empty"  },
    { DT_INT, 3, 2, LOAD_MLA,    "mla"    },
    { DT_INT, 3, 2, LOAD_SUB,    "sub"    },
    { DT_INT, 3, 3, LOAD_INTROT, "introt" },
    { DT_INT, 3, 3, LOAD_EMPTY,  "empty"  },
    { DT_INT, 3, 3, LOAD_MLA,    "mla"    },
    { DT_INT, 3, 3, LOAD_SUB,    "sub"    },
    { DT_INT, 3, 4, LOAD_INTROT, "introt" },
    { DT_INT, 3, 4, LOAD_EMPTY,  "empty"  },
    { DT_INT, 3, 4, LOAD_MLA,    "mla"    },
    { DT_INT, 3, 4, LOAD_SUB,    "sub"    },
};

/* ------------------------------------------------------------------ */
/* Engine entry points.  SVE body arrives in Task 3.                    */
/* ------------------------------------------------------------------ */

extern "C" int adaptive_sve_run_combo(struct test *test, int cpu, int combo)
{
    (void)test; (void)cpu; (void)combo;
    return EXIT_SUCCESS;
}

#if defined(__aarch64__)

/* ------------------------------------------------------------------ */
/* NEON engine (Task 2): 30 hot-loop instances + fill + golden          */
/* ------------------------------------------------------------------ */

#include <arm_neon.h>

/* Per-child plumbing state (defined early: the engine reads test->data) */
struct AdaptiveMemSdcData {
    struct AdaptiveShm *shm;             /* mmap'd, shared across children */
    int isa;                             /* 0=NEON 1=SVE 2=SVE2 */
};

/* Per-call context.  Every test_run invocation owns its own buffers:
 * verify mode picks a fresh combo per call, so fill+golden+alloc are
 * per-call by design (cold path, noinline helpers below). */
struct NeonCtx {
    struct AdaptiveShm *shm;
    int combo;
    uint64_t sweep;                      /* ALT direction toggle */
    /* element buffers: ADAPT_COUNT * 16 bytes each (both vec types are 16B) */
    void *srcA, *srcB, *srcC, *scratch, *expected;
    void *temp, *dst, *junk1, *junk2;
};

/* DCE-guarded loads (family pattern: intrinsic loads are NOT volatile —
 * the empty-load slots must keep their unused b/c loads emitted). */
static inline uint64x2_t load_vec(const void *addr) {
    uint64x2_t res;
    __asm__ volatile ("ldr %q0, [%1]" : "=w"(res) : "r"(addr) : "memory");
    return res;
}
static inline uint32x4_t load_vec_u32(const void *addr) {
    uint32x4_t res;
    __asm__ volatile ("ldr %q0, [%1]" : "=w"(res) : "r"(addr) : "memory");
    return res;
}
static inline void store_vec(void *addr, uint64x2_t val) {
    vst1q_u64(static_cast<uint64_t *>(addr), val);
}
static inline void store_vec_u32(void *addr, uint32x4_t val) {
    vst1q_u32(static_cast<uint32_t *>(addr), val);
}

/* ---- 2-source slot ops (i%4) — exact family formulas ---- */

/* FP64 rotation: fadd/fsub/fmul/fmax, slot order mirrors the FP64 parent */
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

/* int rotation: add/eor/and/orr — rowmajor parent chassis */
static inline uint64x2_t int_rot(int slot, uint64x2_t a, uint64x2_t b) {
    switch (slot) {
        case 0: return vaddq_u64(a, b);
        case 1: return veorq_u64(a, b);
        case 2: return vandq_u64(a, b);
        default: return vorrq_u64(a, b);
    }
}

/* mla rotation (s32, decomposed — never the fused 3-operand form):
 * mul / mla-style (t+a) / mls-style (b−t) / eor control */
static inline uint32x4_t mla_rot(int slot, uint32x4_t a, uint32x4_t b) {
    const int32x4_t sa = vreinterpretq_s32_u32(a);
    const int32x4_t sb = vreinterpretq_s32_u32(b);
    switch (slot) {
        case 0: return vreinterpretq_u32_s32(vmulq_s32(sa, sb));
        case 1: return vreinterpretq_u32_s32(vaddq_s32(vmulq_s32(sa, sb), sa));
        case 2: return vreinterpretq_u32_s32(vsubq_s32(vmulq_s32(sa, sb), sb));
        default: return veorq_u32(a, b);
    }
}

/* sub rotation: sub (borrow chain) / eor / bic / orn */
static inline uint64x2_t sub_rot(int slot, uint64x2_t a, uint64x2_t b) {
    switch (slot) {
        case 0: return vsubq_u64(a, b);
        case 1: return veorq_u64(a, b);
        case 2: return vbicq_u64(a, b);
        default: return vornq_u64(a, b);
    }
}

/* ---- 3-source slot ops (i%4) — pinned formulas ----
 * FP64: no (a×b)+c form anywhere — fma contraction would rewrite it */
static inline uint64x2_t fp64_rot3(int slot, uint64x2_t a, uint64x2_t b, uint64x2_t c) {
    const float64x2_t fa = vreinterpretq_f64_u64(a);
    const float64x2_t fb = vreinterpretq_f64_u64(b);
    const float64x2_t fc = vreinterpretq_f64_u64(c);
    float64x2_t fres;
    switch (slot) {
        case 0: fres = vaddq_f64(vaddq_f64(fa, fb), fc); break;
        case 1: fres = vsubq_f64(vsubq_f64(fa, fb), fc); break;
        case 2: fres = vmulq_f64(vmulq_f64(fa, fb), fc); break;
        default: fres = vmaxq_f64(vmaxq_f64(fa, fb), fc); break;
    }
    return vreinterpretq_u64_f64(fres);
}

/* int 3src: the historical mrn_nuke_3src_alu mixing pattern, verbatim */
static inline uint64x2_t int_rot3(int slot, uint64x2_t a, uint64x2_t b, uint64x2_t c) {
    switch (slot) {
        case 0: return veorq_u64(veorq_u64(a, b), c);
        case 1: return veorq_u64(vaddq_u64(a, b), c);
        case 2: return veorq_u64(a, vaddq_u64(b, c));
        default: return vaddq_u64(veorq_u64(a, b), c);
    }
}

/* mla 3src: c is the accumulator-side operand */
static inline uint32x4_t mla_rot3(int slot, uint32x4_t a, uint32x4_t b, uint32x4_t c) {
    const int32x4_t sa = vreinterpretq_s32_u32(a);
    const int32x4_t sb = vreinterpretq_s32_u32(b);
    const int32x4_t sc = vreinterpretq_s32_u32(c);
    const int32x4_t t = vmulq_s32(sa, sb);
    switch (slot) {
        case 0: return vreinterpretq_u32_s32(t);
        case 1: return vreinterpretq_u32_s32(vaddq_s32(t, sc));
        case 2: return vreinterpretq_u32_s32(vsubq_s32(sc, t));
        default: return veorq_u32(veorq_u32(a, b), c);
    }
}

/* sub 3src: borrow chain / eor / bic chain / orn chain */
static inline uint64x2_t sub_rot3(int slot, uint64x2_t a, uint64x2_t b, uint64x2_t c) {
    switch (slot) {
        case 0: return vsubq_u64(vsubq_u64(a, b), c);
        case 1: return veorq_u64(veorq_u64(a, b), c);
        case 2: return vbicq_u64(a, vorrq_u64(b, c));       /* a & ~(b|c) */
        default: return vornq_u64(a, vandq_u64(b, c));      /* a | ~(b&c) */
    }
}

/* ---- hot sweep: one full sweep (1024 elements), noinline ---- */
template <AdaptLoad LOAD, int LDR, int STR, AdaptSweep SWEEP>
static bool __attribute__((noinline)) neon_hot_sweep(struct NeonCtx *ctx)
{
    constexpr bool is_u32 = (LOAD == LOAD_MLA);
    using V = std::conditional_t<is_u32, uint32x4_t, uint64x2_t>;

    V *srcA = static_cast<V *>(ctx->srcA);
    V *srcB = static_cast<V *>(ctx->srcB);
    V *srcC = static_cast<V *>(ctx->srcC);
    V *scratch = static_cast<V *>(ctx->scratch);
    V *expected = static_cast<V *>(ctx->expected);
    V *temp = static_cast<V *>(ctx->temp);
    V *dst = static_cast<V *>(ctx->dst);
    V *junk1 = static_cast<V *>(ctx->junk1);
    V *junk2 = static_cast<V *>(ctx->junk2);

    const bool descending = (SWEEP == SWEEP_ALT) && ((ctx->sweep & 1) != 0);

    for (int n = 0; n < ADAPT_COUNT; n++) {
        const int i = descending ? (ADAPT_COUNT - 1 - n) : n;

        /* top-of-iteration scratch load: DCE guard, value unused */
        if constexpr (is_u32) {
            uint32x4_t unused_x = load_vec_u32(&scratch[i]);
            (void)unused_x;
        } else {
            uint64x2_t unused_x = load_vec(&scratch[i]);
            (void)unused_x;
        }

        V res;
        if constexpr (is_u32) {
            uint32x4_t a = load_vec_u32(&srcA[i]);
            uint32x4_t b = load_vec_u32(&srcB[i]);
            if constexpr (LOAD == LOAD_EMPTY) {
                if constexpr (LDR == 3) { uint32x4_t c = load_vec_u32(&srcC[i]); (void)c; }
                res = a;
            } else if constexpr (LDR == 3) {
                uint32x4_t c = load_vec_u32(&srcC[i]);
                res = mla_rot3(i % 4, a, b, c);
            } else {
                res = mla_rot(i % 4, a, b);
            }
            store_vec_u32(&temp[i], res);
            if constexpr (STR >= 3) store_vec_u32(&junk1[i], res);
            if constexpr (STR >= 4) store_vec_u32(&junk2[i], res);
            store_vec_u32(&dst[i], res);
        } else {
            uint64x2_t a = load_vec(&srcA[i]);
            uint64x2_t b = load_vec(&srcB[i]);
            if constexpr (LOAD == LOAD_EMPTY) {
                if constexpr (LDR == 3) { uint64x2_t c = load_vec(&srcC[i]); (void)c; }
                res = a;
            } else if constexpr (LDR == 3) {
                uint64x2_t c = load_vec(&srcC[i]);
                if constexpr (LOAD == LOAD_FP64ROT)      res = fp64_rot3(i % 4, a, b, c);
                else if constexpr (LOAD == LOAD_INTROT)  res = int_rot3(i % 4, a, b, c);
                else                                     res = sub_rot3(i % 4, a, b, c);
            } else {
                if constexpr (LOAD == LOAD_FP64ROT)      res = fp64_rot(i % 4, a, b);
                else if constexpr (LOAD == LOAD_INTROT)  res = int_rot(i % 4, a, b);
                else                                     res = sub_rot(i % 4, a, b);
            }
            store_vec(&temp[i], res);
            if constexpr (STR >= 3) store_vec(&junk1[i], res);
            if constexpr (STR >= 4) store_vec(&junk2[i], res);
            store_vec(&dst[i], res);
        }
    }
    ctx->sweep++;

    if (memcmp(dst, expected, ADAPT_COUNT * sizeof(V)) != 0) {
        const struct ComboDef &cd = kComboTable[ctx->combo];
        /* set the cross-child flag BEFORE the noreturn report */
        __atomic_store_n(&ctx->shm->sdc_flag, 1u, __ATOMIC_RELEASE);
        report_fail_msg("adaptive_mem_sdc combo#%d [NEON/%s/ldr%d/str%d/%s] data miscompare",
                        ctx->combo, cd.dt == DT_FP64 ? "fp64" : "int",
                        cd.ldr, cd.str, cd.label);
    }

    /* any child/thread saw SDC -> this thread stops sweeping */
    return __atomic_load_n(&ctx->shm->sdc_flag, __ATOMIC_ACQUIRE) == 0u;
}

/* Dispatch table indexed BY the combo fields (load, ldr-2, str-2) —
 * the table's sweep discipline is derived per load row, so the 30
 * instantiations cannot drift out of order with kComboTable. */
using SweepFn = bool (*)(struct NeonCtx *);

static constexpr AdaptSweep sweep_for(AdaptLoad load)
{
    /* FP64/int rotations and empty: alternating (fp64 parent discipline);
     * mla/sub: monotonic ascending (their parent tests).  constexpr so it
     * can name the template argument in the dispatch table below. */
    return (load == LOAD_MLA || load == LOAD_SUB) ? SWEEP_MONO : SWEEP_ALT;
}

/* load->(sweep) table builder: one row per load keeps the STR/LDR
 * nesting uniform and visually checkable. */
#define ADAPT_ROW_2LDR(load)                                                  \
    { /* ldr=2 */ {                                                           \
        &neon_hot_sweep<load, 2, 2, sweep_for(load)>,                         \
        &neon_hot_sweep<load, 2, 3, sweep_for(load)>,                         \
        &neon_hot_sweep<load, 2, 4, sweep_for(load)> },                       \
      /* ldr=3 */ {                                                           \
        &neon_hot_sweep<load, 3, 2, sweep_for(load)>,                         \
        &neon_hot_sweep<load, 3, 3, sweep_for(load)>,                         \
        &neon_hot_sweep<load, 3, 4, sweep_for(load)> } }

static const SweepFn neon_by_lts[5][2][3] = {
    ADAPT_ROW_2LDR(LOAD_FP64ROT),
    ADAPT_ROW_2LDR(LOAD_INTROT),
    ADAPT_ROW_2LDR(LOAD_EMPTY),
    ADAPT_ROW_2LDR(LOAD_MLA),
    ADAPT_ROW_2LDR(LOAD_SUB),
};
#undef ADAPT_ROW_2LDR

/* ---- cold path: fill + golden (same intrinsics as the hot loop) ---- */

static void __attribute__((noinline)) neon_fill_golden(struct NeonCtx *ctx)
{
    const struct ComboDef &cd = kComboTable[ctx->combo];
    const size_t bytes = ADAPT_COUNT * 16;

    memset_random(ctx->srcA, bytes);
    memset_random(ctx->srcB, bytes);
    memset_random(ctx->srcC, bytes);
    memset_random(ctx->scratch, bytes);

    if (cd.load == LOAD_FP64ROT) {
        /* NaN-free inputs.  GCC freely reorders operands of the
         * commutative FP ops (fadd/fmul/fmax), and for a BOTH-sNaN
         * lane AArch64 returns the quieted *first* operand — so two
         * inlined copies of the "same" expression (golden loop vs hot
         * loop) can disagree bit-exactly on sNaN-pair lanes.  Clearing
         * the all-ones exponent at fill time (NaN/Inf -> finite, bit 62
         * cleared) removes the payload ambiguity entirely; finite
         * arithmetic is bit-deterministic under operand reordering.
         * Integer loads are exact and need no sanitize.  (Root cause:
         * 2026-11-13 verify fail, deterministic repro at ~1e4 rounds,
         * 300M rounds clean post-fix.) */
        auto sanitize = [](void *buf) {
            auto *w = static_cast<uint64_t *>(buf);
            for (int k = 0; k < ADAPT_COUNT * 2; k++)
                if ((w[k] >> 52 & 0x7ff) == 0x7ff)
                    w[k] &= ~(1ULL << 62);
        };
        sanitize(ctx->srcA);
        sanitize(ctx->srcB);
        sanitize(ctx->srcC);
    }

    if (cd.load == LOAD_MLA) {
        /* parent-mla pattern: narrow sources to 16-bit magnitude and
         * PERSIST them so golden recomputation sees identical inputs */
        auto *A = static_cast<uint32x4_t *>(ctx->srcA);
        auto *B = static_cast<uint32x4_t *>(ctx->srcB);
        auto *C = static_cast<uint32x4_t *>(ctx->srcC);
        const uint32x4_t mask = vdupq_n_u32(0x0000ffff);
        for (int i = 0; i < ADAPT_COUNT; i++) {
            A[i] = vandq_u32(A[i], mask);
            B[i] = vandq_u32(B[i], mask);
            C[i] = vandq_u32(C[i], mask);
        }
    }

    if (cd.load == LOAD_MLA) {
        auto *A = static_cast<uint32x4_t *>(ctx->srcA);
        auto *B = static_cast<uint32x4_t *>(ctx->srcB);
        auto *C = static_cast<uint32x4_t *>(ctx->srcC);
        auto *E = static_cast<uint32x4_t *>(ctx->expected);
        for (int i = 0; i < ADAPT_COUNT; i++) {
            if (cd.ldr == 3) E[i] = mla_rot3(i % 4, A[i], B[i], C[i]);
            else             E[i] = mla_rot(i % 4, A[i], B[i]);
        }
    } else {
        auto *A = static_cast<uint64x2_t *>(ctx->srcA);
        auto *B = static_cast<uint64x2_t *>(ctx->srcB);
        auto *C = static_cast<uint64x2_t *>(ctx->srcC);
        auto *E = static_cast<uint64x2_t *>(ctx->expected);
        for (int i = 0; i < ADAPT_COUNT; i++) {
            switch (cd.load) {
                case LOAD_FP64ROT:
                    E[i] = (cd.ldr == 3) ? fp64_rot3(i % 4, A[i], B[i], C[i])
                                         : fp64_rot(i % 4, A[i], B[i]);
                    break;
                case LOAD_INTROT:
                    E[i] = (cd.ldr == 3) ? int_rot3(i % 4, A[i], B[i], C[i])
                                         : int_rot(i % 4, A[i], B[i]);
                    break;
                case LOAD_EMPTY:
                    E[i] = A[i];         /* res = a regardless of ldr */
                    break;
                default: /* LOAD_SUB */
                    E[i] = (cd.ldr == 3) ? sub_rot3(i % 4, A[i], B[i], C[i])
                                         : sub_rot(i % 4, A[i], B[i]);
                    break;
            }
        }
    }
}

extern "C" int adaptive_neon_run_combo(struct test *test, int cpu, int combo)
{
    (void)cpu;
    if (combo < 0 || combo >= ADAPT_COMBO_COUNT)
        return EXIT_SUCCESS;

    auto *mdata = static_cast<struct AdaptiveMemSdcData *>(test->data);
    const struct ComboDef &cd = kComboTable[combo];

    struct NeonCtx ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.shm = mdata ? mdata->shm : nullptr;
    ctx.combo = combo;

    const size_t bytes = ADAPT_COUNT * 16;
    ctx.srcA     = aligned_alloc(64, bytes);
    ctx.srcB     = aligned_alloc(64, bytes);
    ctx.srcC     = aligned_alloc(64, bytes);
    ctx.scratch  = aligned_alloc(64, bytes);
    ctx.expected = aligned_alloc(64, bytes);
    ctx.temp     = aligned_alloc(64, bytes);
    ctx.dst      = aligned_alloc(64, bytes);
    ctx.junk1    = aligned_alloc(64, bytes);
    ctx.junk2    = aligned_alloc(64, bytes);

    neon_fill_golden(&ctx);

    SweepFn fn = neon_by_lts[cd.load][cd.ldr - 2][cd.str - 2];

    TEST_LOOP(test, 1 << 8) {
        if (!fn(&ctx))
            break;                       /* SDC seen somewhere: stop */
    }

    free(ctx.junk2);
    free(ctx.junk1);
    free(ctx.dst);
    free(ctx.temp);
    free(ctx.expected);
    free(ctx.scratch);
    free(ctx.srcC);
    free(ctx.srcB);
    free(ctx.srcA);
    return EXIT_SUCCESS;
}

#else  /* !__aarch64__ */

extern "C" int adaptive_neon_run_combo(struct test *test, int cpu, int combo)
{
    (void)test; (void)cpu; (void)combo;
    return EXIT_SUCCESS;
}

#endif

#if defined(__aarch64__)

/* ------------------------------------------------------------------ */
/* Per-child plumbing: shm, ISA probe, combo pick, covfile trace       */
/* ------------------------------------------------------------------ */

static const char *isa_tag(int isa)
{
    switch (isa) {
        case 2:  return "SVE2";
        case 1:  return "SVE";
        default: return "NEON";
    }
}

/* Map (or create) the named shm.  O_EXCL decides the creator; the
 * creator publishes the anchor then sets ready (release).  Latecomers
 * spin on ready (acquire) with a bounded wait — on timeout the mapping
 * is returned anyway and pick_combo() falls back to idle. */
static struct AdaptiveShm *shm_setup(void)
{
    const char *key = getenv("ADAPTIVE_MEM_SDC_KEY");
    char name[128];
    snprintf(name, sizeof(name), "/adaptive_mem_sdc_%s", key ? key : "dflt");

    int fd = shm_open(name, O_CREAT | O_EXCL | O_RDWR, 0600);
    bool creator = (fd >= 0);
    if (!creator) {
        if (errno != EEXIST)
            return nullptr;
        fd = shm_open(name, O_RDWR, 0600);
        if (fd < 0)
            return nullptr;
    }

    if (creator && ftruncate(fd, sizeof(struct AdaptiveShm)) != 0) {
        close(fd);
        return nullptr;
    }

    auto *shm = static_cast<struct AdaptiveShm *>(
            mmap(nullptr, sizeof(struct AdaptiveShm), PROT_READ | PROT_WRITE,
                 MAP_SHARED, fd, 0));
    close(fd);
    if (shm == MAP_FAILED)
        return nullptr;

    if (creator) {
        /* zero the fresh object (ftruncate gives zeros, be explicit anyway) */
        memset(shm, 0, sizeof(*shm));
        clock_gettime(CLOCK_MONOTONIC, &shm->anchor);
        __atomic_store_n(&shm->ready, 1u, __ATOMIC_RELEASE);
    } else {
        /* bounded spin: creator publishes within microseconds of our
         * EEXIST; 2s covers any pathological scheduling */
        for (int i = 0; i < 200000; i++) {
            if (__atomic_load_n(&shm->ready, __ATOMIC_ACQUIRE) == 1u)
                break;
            usleep(10);
        }
    }
    return shm;
}

static int probe_isa(void)
{
    /* SVE2 lives in AT_HWCAP2, SVE/ASIMD in AT_HWCAP — do not mix them up */
    unsigned long hwc2 = getauxval(AT_HWCAP2);
    if (hwc2 & HWCAP2_SVE2)
        return 2;
    unsigned long hwc = getauxval(AT_HWCAP);
    if (hwc & HWCAP_SVE)
        return 1;
    return 0;                            /* ASIMD/NEON: base aarch64 */
}

/* Pick this child's combo.  Returns -1 when the child should idle
 * (sdc_flag set, or shm unusable). */
static int pick_combo(struct AdaptiveShm *shm)
{
    if (!shm)
        return -1;
    if (__atomic_load_n(&shm->sdc_flag, __ATOMIC_ACQUIRE) != 0)
        return -1;

    if (getenv("ADAPTIVE_MEM_SDC_VERIFY") != nullptr) {
        uint32_t prev = __atomic_fetch_add(&shm->verify_ctr, 1u, __ATOMIC_RELAXED);
        return (int)(prev % ADAPT_COMBO_COUNT);
    }

    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    int64_t elapsed = (int64_t)(now.tv_sec - shm->anchor.tv_sec);
    if (now.tv_nsec < shm->anchor.tv_nsec)
        elapsed -= 1;
    if (elapsed < 0)
        elapsed = 0;
    int64_t idx = elapsed / ADAPT_SLICE_SECONDS;
    if (idx > ADAPT_COMBO_COUNT - 1)
        idx = ADAPT_COMBO_COUNT - 1;
    return (int)idx;
}

/* one line per child init: "<iso> <pid> <isa> <mode> <combo>" */
static void covfile_trace(int isa, int combo)
{
    const char *path = getenv("ADAPTIVE_MEM_SDC_COVFILE");
    if (!path)
        return;
    char line[160];
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm tm;
    localtime_r(&ts.tv_sec, &tm);
    char iso[32];
    strftime(iso, sizeof(iso), "%FT%T", &tm);
    snprintf(line, sizeof(line), "%s %d %s %s %d\n", iso, (int)getpid(),
             isa_tag(isa),
             getenv("ADAPTIVE_MEM_SDC_VERIFY") ? "verify" : "normal",
             combo);
    int fd = open(path, O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd < 0)
        return;
    (void)!write(fd, line, strlen(line));
    close(fd);
}

static int adaptive_mem_sdc_init(struct test *test)
{
    auto *data = static_cast<struct AdaptiveMemSdcData *>(malloc(sizeof(struct AdaptiveMemSdcData)));
    data->shm = shm_setup();
    data->isa = probe_isa();
    test->data = data;
    return EXIT_SUCCESS;
}

static int adaptive_mem_sdc_run(struct test *test, int cpu)
{
    auto *data = static_cast<struct AdaptiveMemSdcData *>(test->data);
    int combo = pick_combo(data->shm);
    covfile_trace(data->isa, combo);

    if (combo < 0)
        return EXIT_SUCCESS;             /* post-SDC or shm unusable: idle */

    switch (data->isa) {
        case 1:
        case 2:
            return adaptive_sve_run_combo(test, cpu, combo);
        default:
            return adaptive_neon_run_combo(test, cpu, combo);
    }
}

static int adaptive_mem_sdc_cleanup(struct test *test)
{
    auto *data = static_cast<struct AdaptiveMemSdcData *>(test->data);
    /* shm mapping dies with the child process; the named object is
     * removed by the campaign script at campaign end */
    free(data);
    test->data = nullptr;
    return EXIT_SUCCESS;
}

#else  /* !__aarch64__ */

static int adaptive_mem_sdc_init(struct test *test)  { (void)test; return EXIT_SUCCESS; }
static int adaptive_mem_sdc_run(struct test *test, int cpu) { (void)test; (void)cpu; return EXIT_SUCCESS; }
static int adaptive_mem_sdc_cleanup(struct test *test) { (void)test; return EXIT_SUCCESS; }

#endif

DECLARE_TEST(adaptive_mem_sdc, "Adaptive memory-access SDC test: probes widest SIMD (SVE2>SVE>NEON), sweeps 30-combo priority sequence (dtype>ldr>str>load, 30min wall-clock slice per combo, verify-mode round-robin for golden smoke), SDC report carries the combo tag")
    .test_init    = adaptive_mem_sdc_init,
    .test_run     = adaptive_mem_sdc_run,
    .test_cleanup = adaptive_mem_sdc_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
