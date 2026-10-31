/**
 * @file
 *
 * @copyright
 * Copyright 2022 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 *
 * @test @b eigen_gemm_cdouble_dynamic_square_dump
 * @parblock
 * Dump-on-failure variant of eigen_gemm_cdouble_dynamic_square. The FMA
 * hot path (x = lhs*rhs) is byte-for-byte identical to the original;
 * only the verification changes: instead of memcmp_or_fail over the raw
 * double stream (2*M_DIM*M_DIM doubles = real,imag interleaved), a cold
 * element-wise compare locates the first mismatch and dumps its complex
 * element index, the golden/actual real and imag doubles, their IEEE-754
 * bit xors, and a per-byte breakdown, so an SDC bit-flip can be located.
 * Mirrors the movbe_dump / mrn_rmw_dump design: no extra hot-path reads.
 *
 * @note This test requires at least 2 threads to run.
 * @endparblock
 */

#include <sandstone.h>

#include <Eigen/Core>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
using namespace Eigen;

// Binary fail-record: appended to /tmp/eigen_gemm_cdouble_dump_<pid>.bin on
// each miscompare. Cold-branch only; FMA hot path (x = lhs*rhs) byte-identical
// to the original (see memory eigen-sdc-bitflip-position-stats: dump variants
// reproduce the original fail count — cold-branch dumps do not suppress the
// defect). component=0 real, =1 imag (complex double stream is real,imag
// interleaved).
#pragma pack(push, 1)
struct eigen_gemm_dump_record {
    uint64_t timestamp_us;
    uint32_t cpu;
    uint32_t iteration;
    uint32_t row;
    uint32_t col;
    uint32_t elem_idx;        // raw double index in the interleaved stream
    uint32_t component;       // 0=real, 1=imag
    uint64_t golden_bits;
    uint64_t actual_bits;
    uint64_t xor_val;
};
#pragma pack(pop)

#define M_DIM 221 // weird dim on purpose

typedef Matrix < std::complex < double >, Dynamic, Dynamic > Mat;

namespace {
struct eigen_test_data {
    Mat lhs;
    Mat rhs;
    Mat prod;
    int dump_fd;
};
}

#define CAST(_x) static_cast<struct eigen_test_data *>(_x)

static int eigen_gemm_cdouble_dynamic_square_init(struct test *test) {
    test->data = new(eigen_test_data);
    try {
        CAST(test->data)->lhs = Mat::Random(M_DIM, M_DIM);
        CAST(test->data)->rhs = Mat::Random(M_DIM, M_DIM);
        CAST(test->data)->prod = CAST(test->data)->lhs * CAST(test->data)->rhs;
    } catch (...) {
        report_fail_msg("Exception on Eigen code, most probably OOM");
    }

    char path[256];
    snprintf(path, sizeof(path), "/tmp/eigen_gemm_cdouble_dump_%d.bin", getpid());
    CAST(test->data)->dump_fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (CAST(test->data)->dump_fd < 0)
        log_error("eigen_gemm_cdouble_dump: failed to open dump log %s", path);

    return EXIT_SUCCESS;
}

static int eigen_gemm_cdouble_dynamic_square_run(struct test *test, int cpu) {
    uint32_t iter = 0;
    do {
        auto testdata = CAST(test->data);
        Mat x;
        x = testdata->lhs * testdata->rhs;          // FMA hot path: unchanged

        // Original compared the raw double stream (real,imag interleaved).
        // Keep that exact byte-level semantics: compare as 2*M_DIM*M_DIM
        // doubles, and on first mismatch map back to a complex element +
        // real/imag component for the dump.
        const double *xd = reinterpret_cast<const double *>(x.data());
        const double *pd = reinterpret_cast<const double *>(testdata->prod.data());
        const int N = 2 * M_DIM * M_DIM;
        for (int idx = 0; idx < N; ++idx) {
            if (xd[idx] != pd[idx]) {
                // complex element index = idx/2; component = idx%2 (0=real,1=imag)
                int cidx = idx / 2;
                int row = cidx / M_DIM, col = cidx % M_DIM;
                const char *comp = (idx % 2 == 0) ? "real" : "imag";
                uint64_t golden_bits, actual_bits;
                memcpy(&golden_bits, &pd[idx], sizeof(uint64_t));
                memcpy(&actual_bits, &xd[idx], sizeof(uint64_t));
                uint64_t xorv = golden_bits ^ actual_bits;
                unsigned char *gb = (unsigned char *)&golden_bits;
                unsigned char *ab = (unsigned char *)&actual_bits;
                unsigned char *xb = (unsigned char *)&xorv;
                log_error("eigen_gemm_cdouble_dump: miscompare at [%d,%d].%s (didx=%d): "
                          "golden=%g actual=%g | bits golden=0x%016lX actual=0x%016lX "
                          "xor=0x%016lX (flipped bit(s)) | "
                          "bytes[b7..b0] golden=%02X%02X%02X%02X%02X%02X%02X%02X "
                          "actual=%02X%02X%02X%02X%02X%02X%02X%02X "
                          "xor=%02X%02X%02X%02X%02X%02X%02X%02X",
                          row, col, comp, idx,
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
                        .component = (uint32_t)(idx % 2),
                        .golden_bits = golden_bits,
                        .actual_bits = actual_bits,
                        .xor_val = xorv,
                    };
                    write(testdata->dump_fd, &rec, sizeof(rec));
                }
                report_fail_msg("eigen_gemm_cdouble_dump: product miscompare at [%d,%d].%s", row, col, comp);
            }
        }
        iter++;
    } while (test_time_condition(test));
    return EXIT_SUCCESS;
}

static int eigen_gemm_cdouble_dynamic_square_finish(struct test *test) {
    if (CAST(test->data)->dump_fd >= 0)
        close(CAST(test->data)->dump_fd);
    delete(CAST(test->data));
    return EXIT_SUCCESS;
}

DECLARE_TEST(eigen_gemm_cdouble_dynamic_square_dump, "Eigen GEMM payload (cplx double, dynamic, square) — dump variant records golden/actual/xor (text + binary log) on miscompare")
  .groups = DECLARE_TEST_GROUPS(&group_math),
  .test_init = eigen_gemm_cdouble_dynamic_square_init,
  .test_run = eigen_gemm_cdouble_dynamic_square_run,
  .test_cleanup = eigen_gemm_cdouble_dynamic_square_finish,
  .fracture_loop_count = 5,
  .quality_level = TEST_QUALITY_PROD,
END_DECLARE_TEST
