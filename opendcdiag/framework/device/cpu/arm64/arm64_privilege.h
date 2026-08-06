/*
 * Copyright 2025 Intel Corporation.
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef ARM64_PRIVILEGE_H
#define ARM64_PRIVILEGE_H

#include <cstdint>
#include <cstddef>

enum access_method_t
{
    ACCESS_USER_SPACE,
    ACCESS_SYSFS,
    ACCESS_PROCFS,
    ACCESS_PERF_EVENT,
    ACCESS_ACPI
};

struct memory_error_stats
{
    uint64_t ce_count;
    uint64_t ue_count;
    bool ce_fatal;
    bool ue_fatal;
    char dimm_name[256];
    char dimm_id[256];
};

struct hw_access_ops
{
    int (*init)(void);
    int (*read_msr)(uint32_t msr, uint64_t *value, int cpu);
    int (*write_msr)(uint32_t msr, uint64_t value, int cpu);
    int (*read_ecc)(memory_error_stats *stats, int cpu);
    int (*setup_ras_monitoring)(void);
    void (*cleanup)(void);
    const char *backend_name;
};

struct hw_access_ops *arm64_get_hw_access_ops(void);
int arm64_hw_init(void);

// Kunpeng920 ECC backend (defined in kunpeng920_ecc.cpp). Declared here so
// that arm64_sdc_detect.cpp (and other consumers) can call them without each
// translation unit needing its own forward declaration.
#ifdef __cplusplus
extern "C" {
#endif
int kunpeng920_ecc_init(void);
int kunpeng920_ecc_read_errors(struct memory_error_stats *stats, int cpu);
#ifdef __cplusplus
}
#endif

#endif // ARM64_PRIVILEGE_H
