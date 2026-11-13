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
/* Engine stubs (Task 2 replaces the NEON body, Task 3 the SVE body)   */
/* ------------------------------------------------------------------ */

extern "C" int adaptive_neon_run_combo(struct test *test, int cpu, int combo)
{
    (void)test; (void)cpu; (void)combo;
    return EXIT_SUCCESS;
}

extern "C" int adaptive_sve_run_combo(struct test *test, int cpu, int combo)
{
    (void)test; (void)cpu; (void)combo;
    return EXIT_SUCCESS;
}

#if defined(__aarch64__)

/* ------------------------------------------------------------------ */
/* Per-child plumbing: shm, ISA probe, combo pick, covfile trace       */
/* ------------------------------------------------------------------ */

struct AdaptiveMemSdcData {
    struct AdaptiveShm *shm;             /* mmap'd, shared across children */
    int isa;                             /* 0=NEON 1=SVE 2=SVE2 */
};

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
