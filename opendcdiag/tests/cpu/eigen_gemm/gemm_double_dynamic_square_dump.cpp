/**
 * @file
 *
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b eigen_gemm_double_dynamic_square_dump
 * @parblock
 * Dump-on-failure variant of eigen_gemm_double_dynamic_square. The FMA
 * hot path (x = lhs*rhs) is byte-for-byte identical to the original;
 * only the verification changes: instead of memcmp_or_fail over the whole
 * matrix, a cold element-wise compare loop locates the first mismatch and
 * dumps its row/col, golden, actual, IEEE-754 bit xor, and a per-byte
 * breakdown, so an SDC bit-flip in the product can be located. Mirrors the
 * movbe_dump / mrn_rmw_dump design: no extra hot-path reads or snapshots.
 *
 * @note Although the test should run fine on a single thread, it is
 * only expected to catch defects if run on at least 2 cores.
 * @endparblock
 */

#include <sandstone.h>

#include <Eigen/Core>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
using namespace Eigen;

// Binary fail-record: appended to /tmp/eigen_gemm_double_dump_<pid>.bin on
// each miscompare. Mirrors movbe_dump / mrn_rmw_dump: written only from the
// cold verification branch; the FMA hot path (x = lhs*rhs) is byte-for-byte
// identical to the original test (see memory eigen-sdc-bitflip-position-stats:
// dump variants reproduce the original fail count — cold-branch dumps do not
// suppress the defect).
#pragma pack(push, 1)
struct eigen_gemm_dump_record {
    uint64_t timestamp_us;   // microseconds since epoch
    uint32_t cpu;            // logical cpu where failure occurred
    uint32_t iteration;       // do-while iteration counter
    uint32_t row;             // matrix row of mismatch
    uint32_t col;             // matrix col of mismatch
    uint32_t elem_idx;        // raw element index
    uint32_t component;       // 0=scalar (float/double); 1=imag (cdouble)
    uint64_t golden_bits;     // expected value bits (memcpy, IEEE-754)
    uint64_t actual_bits;     // actual value bits (memcpy, IEEE-754)
    uint64_t xor_val;         // golden_bits ^ actual_bits (flipped bit(s))
};
#pragma pack(pop)

// Matrix dimension. Historically hardcoded to 256. Now configurable via
// the GEMM_K_DIM environment variable (default 256 = original baseline) so
// the fault-propagation-vs-k-dimension hypothesis can be tested without
// touching random-generation / tolerance / report logic. Nothing else
// changes: Mat::Random seeding and report_fail behavior are untouched.
static int gemm_k_dim() {
    static int dim = -1;
    if (dim < 0) {
        int d = 256;
        if (const char *env = getenv("GEMM_K_DIM")) {
            int parsed = atoi(env);
            if (parsed > 0) d = parsed;
        }
        dim = d;
    }
    return dim;
}
#define M_DIM gemm_k_dim()

typedef Matrix < double, Dynamic, Dynamic > Mat;

namespace {
struct eigen_test_data {
    Mat lhs;
    Mat rhs;
    Mat prod;
    int dump_fd;   // binary fail-log file descriptor (-1 if disabled)
};
}

#define CAST(_x) static_cast<struct eigen_test_data *>(_x)

static int eigen_gemm_double_dynamic_square_init(struct test *test) {
    test->data = new(eigen_test_data);
    try {
        CAST(test->data)->lhs = Mat::Random(M_DIM, M_DIM);
        CAST(test->data)->rhs = Mat::Random(M_DIM, M_DIM);
        CAST(test->data)->prod = CAST(test->data)->lhs * CAST(test->data)->rhs;
    } catch (...) {
        report_fail_msg("Exception on Eigen code, most probably OOM");
    }

    // Open per-process binary fail-log (append). The hot path never touches it.
    char path[256];
    snprintf(path, sizeof(path), "/tmp/eigen_gemm_double_dump_%d.bin", getpid());
    CAST(test->data)->dump_fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (CAST(test->data)->dump_fd < 0)
        log_error("eigen_gemm_double_dump: failed to open dump log %s", path);

    return EXIT_SUCCESS;
}

static int eigen_gemm_double_dynamic_square_run(struct test *test, int cpu) {
    uint32_t iter = 0;
    do {
        auto testdata = CAST(test->data);
        Mat x;
        x = testdata->lhs * testdata->rhs;          // FMA hot path: unchanged

        const double *xd = x.data();
        const double *pd = testdata->prod.data();
        // Element-wise byte-exact compare (same semantics as the original
        // memcmp_or_fail). On the first mismatch, dump golden/actual + the
        // IEEE-754 bit xor and per-byte breakdown, then fail. All of this
        // is cold: the hot path only does the gemm + the compare branch.
        bool ok = true;
        for (int idx = 0; idx < M_DIM * M_DIM; ++idx) {
            if (xd[idx] != pd[idx]) {
                ok = false;
                uint64_t golden_bits, actual_bits;
                memcpy(&golden_bits, &pd[idx], sizeof(uint64_t));
                memcpy(&actual_bits, &xd[idx], sizeof(uint64_t));
                uint64_t xorv = golden_bits ^ actual_bits;
                int row = idx / M_DIM, col = idx % M_DIM;
                unsigned char *gb = (unsigned char *)&golden_bits;
                unsigned char *ab = (unsigned char *)&actual_bits;
                unsigned char *xb = (unsigned char *)&xorv;
                log_error("eigen_gemm_double_dump: miscompare at [%d,%d] (idx=%d): "
                          "golden=%g actual=%g | bits golden=0x%016lX actual=0x%016lX "
                          "xor=0x%016lX (flipped bit(s)) | "
                          "bytes[b7..b0] golden=%02X%02X%02X%02X%02X%02X%02X%02X "
                          "actual=%02X%02X%02X%02X%02X%02X%02X%02X "
                          "xor=%02X%02X%02X%02X%02X%02X%02X%02X",
                          row, col, idx,
                          pd[idx], xd[idx],
                          (unsigned long)golden_bits, (unsigned long)actual_bits,
                          (unsigned long)xorv,
                          gb[7], gb[6], gb[5], gb[4], gb[3], gb[2], gb[1], gb[0],
                          ab[7], ab[6], ab[5], ab[4], ab[3], ab[2], ab[1], ab[0],
                          xb[7], xb[6], xb[5], xb[4], xb[3], xb[2], xb[1], xb[0]);

                // Binary record (cold branch only — hot path is the gemm above)
                if (testdata->dump_fd >= 0) {
                    struct timeval tv;
                    gettimeofday(&tv, NULL);
                    struct eigen_gemm_dump_record rec = {
                        .timestamp_us = (uint64_t)tv.tv_sec * 1000000ULL + (uint64_t)tv.tv_usec,
                        .cpu = (uint32_t)cpu,
                        .iteration = iter,
                        .row = (uint32_t)row,
                        .col = (uint32_t)col,
                        .elem_idx = (uint32_t)idx,
                        .component = 0,
                        .golden_bits = golden_bits,
                        .actual_bits = actual_bits,
                        .xor_val = xorv,
                    };
                    write(testdata->dump_fd, &rec, sizeof(rec));
                }
                report_fail_msg("eigen_gemm_double_dump: product miscompare at [%d,%d]", row, col);
            }
        }
        (void)ok;
        iter++;
    } while (test_time_condition(test));
    return EXIT_SUCCESS;
}

static int eigen_gemm_double_dynamic_square_finish(struct test *test) {
    if (CAST(test->data)->dump_fd >= 0)
        close(CAST(test->data)->dump_fd);
    delete(CAST(test->data));
    return EXIT_SUCCESS;
}

DECLARE_TEST(eigen_gemm_double_dynamic_square_dump, "Eigen GEMM payload (double, dynamic, square) — dump variant records golden/actual/xor (text + binary log) on miscompare")
  .groups = DECLARE_TEST_GROUPS(&group_math),
  .test_init = eigen_gemm_double_dynamic_square_init,
  .test_run = eigen_gemm_double_dynamic_square_run,
  .test_cleanup = eigen_gemm_double_dynamic_square_finish,
  .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
