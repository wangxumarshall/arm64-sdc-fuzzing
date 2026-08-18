/**
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b movbe_dump_probe_e
 * @parblock
 * SDC-trigger probe, variant E: **swapped buffer on a different NUMA/LLC
 * domain than input** (LLC cross-line interaction isolated from the
 * address-advance-stream).
 *
 * Baseline movbe_dump hot loop:
 *   ldr input[i] -> rev -> str swapped[i] -> ldr input[i](reload) -> cmp
 * The store writes to swapped[i] with a linearly-varying address (advances
 * across cache lines). Probe D proved that a *fixed*-address store does NOT
 * trigger (PASS), so the store's advancing address stream is a trigger
 * condition. The open question: is the trigger the advancing *address stream
 * per se, or a *same-LLC-domain interaction* between the swapped writes and
 * the input reloads (both in core 179's local LLC, node 7)?
 *
 * Probe E keeps the baseline structure byte-for-byte (same store to
 * swapped[i], same advancing address stream, same reload of input[i]) but
 * forces swapped and input onto DIFFERENT NUMA nodes / LLC domains:
 *   - input   -> mbind-bound to PROBE_E_INPUT_NODE  (default 7, core 179's home)
 *   - swapped -> mbind-bound to PROBE_E_SWAP_NODE   (default 0, different LLC)
 * So core 179's swapped writes go cross-NUMA (never enter the local LLC for
 * swapped), while input stays local. If probe E STILL triggers, the
 * advancing address stream alone is sufficient (LLC-domain interaction is
 * NOT required). If probe E PASSES, the swapped writes must stay in the
 * same LLC domain as input -- i.e. an LLC cross-line interaction is part of
 * the trigger.
 *
 * Allocation uses mmap + mbind(MPOL_BIND) directly via syscall, so it does
 * not depend on libnuma.
 * @endparblock
 */

#include "sandstone.h"
#include <sys/mman.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <cstring>
#include <cerrno>

#define MOVBE_BUFFER_SIZE (1 << 14)

// NUMA nodes -- override at compile time if needed. Defaults: input on core
// 179's home node (7), swapped on a different node (0) = different LLC.
#ifndef PROBE_E_INPUT_NODE
#  define PROBE_E_INPUT_NODE 7
#endif
#ifndef PROBE_E_SWAP_NODE
#  define PROBE_E_SWAP_NODE 0
#endif

struct movbe_data {
    uint32_t *input;
    uint32_t *swapped;
};

// mmap a page-aligned region of `bytes` and bind it to NUMA `node` via
// mbind(MPOL_BIND). Returns MAP_FAILED on failure. We round up to pages.
static void *mmap_on_node(size_t bytes, int node)
{
    long pagesize = sysconf(_SC_PAGESIZE);
    size_t total = (bytes + pagesize - 1) & ~(size_t)(pagesize - 1);
    // Ensure total is at least one page and a multiple of pagesize.
    if (total == 0) total = pagesize;

    void *p = mmap(nullptr, total, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return p;

    // Build a nodemask with just `node`.
    unsigned long nodemask = 0UL;
    if (node >= 0 && node < (int)(sizeof(unsigned long) * 8)) {
        nodemask = (1UL << node);
        // mbind(addr, len, MPOL_BIND, nodemask, maxnode, flags=0)
        // maxnode = number of bits in nodemask (use 64).
        long r = syscall(__NR_mbind, p, total, 2 /*MPOL_BIND*/,
                         &nodemask, sizeof(unsigned long) * 8, 0);
        if (r != 0) {
            // mbind failed: munmap and report failure so init aborts clearly.
            munmap(p, total);
            return MAP_FAILED;
        }
    }
    // Touch every page so the binding takes effect (first-touch).
    memset(p, 0, total);
    return p;
}

static int movbe_init(struct test *test)
{
    movbe_data *data = (movbe_data *)malloc(sizeof(movbe_data));
    data->input = (uint32_t *)mmap_on_node(MOVBE_BUFFER_SIZE * sizeof(uint32_t),
                                           PROBE_E_INPUT_NODE);
    data->swapped = (uint32_t *)mmap_on_node(MOVBE_BUFFER_SIZE * sizeof(uint32_t),
                                             PROBE_E_SWAP_NODE);
    if (data->input == MAP_FAILED || data->swapped == MAP_FAILED) {
        log_error("MovBE-probeE: mmap/mbind failed (input=%p swapped=%p errno=%d)",
                  (void *)data->input, (void *)data->swapped, errno);
        free(data);
        return EXIT_FAILURE;
    }

    for (size_t i = 0; i < MOVBE_BUFFER_SIZE; ++i) {
        data->input[i] = random32();
    }

    test->data = data;
    return EXIT_SUCCESS;
}

static int movbe_run(struct test *test, int cpu)
{
    movbe_data *data = (movbe_data *)test->data;

    TEST_LOOP(test, 1 << 13) {
        // Hot loop kept byte-for-byte identical to baseline movbe_dump:
        // read input[i], rev, store swapped[i], reload input[i], compare.
        // Only the buffer placements differ (input node 7, swapped node 0).
        for (size_t i = 0; i < MOVBE_BUFFER_SIZE; ++i) {
            uint32_t val = data->input[i];
            val = __builtin_bswap32(val);

            data->swapped[i] = val;

            val = __builtin_bswap32(val);

            if (val != data->input[i]) {
                uint32_t inputv = data->input[i];
                uint32_t golden = data->input[i];
                uint32_t actual = val;
                uint32_t xorv = golden ^ actual;
                unsigned char *ib = (unsigned char *)&inputv;
                unsigned char *gb = (unsigned char *)&golden;
                unsigned char *ab = (unsigned char *)&actual;
                unsigned char *xb = (unsigned char *)&xorv;
                log_error("MovBE-probeE: Round-trip failed at index %u: "
                          "input=0x%08X golden=0x%08X actual=0x%08X xor=0x%08X | "
                          "bytes[b3 b2 b1 b0] input=%02X%02X%02X%02X "
                          "golden=%02X%02X%02X%02X actual=%02X%02X%02X%02X "
                          "xor=%02X%02X%02X%02X",
                          (unsigned)i, inputv, golden, actual, xorv,
                          ib[3], ib[2], ib[1], ib[0],
                          gb[3], gb[2], gb[1], gb[0],
                          ab[3], ab[2], ab[1], ab[0],
                          xb[3], xb[2], xb[1], xb[0]);
                report_fail_msg("MovBE: Round-trip failed at index %u", (unsigned)i);
            }
        }
    }

    return EXIT_SUCCESS;
}

static int movbe_cleanup(struct test *test)
{
    movbe_data *data = (movbe_data *)test->data;
    if (data) {
        if (data->input && data->input != MAP_FAILED)
            munmap(data->input, MOVBE_BUFFER_SIZE * sizeof(uint32_t));
        if (data->swapped && data->swapped != MAP_FAILED)
            munmap(data->swapped, MOVBE_BUFFER_SIZE * sizeof(uint32_t));
        free(data);
    }
    return EXIT_SUCCESS;
}

DECLARE_TEST(movbe_dump_probe_e, "movbe_dump probe E: swapped on different NUMA/LLC than input (LLC cross-line interaction isolated)")
    .test_init = movbe_init,
    .test_run = movbe_run,
    .test_cleanup = movbe_cleanup,
    .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
