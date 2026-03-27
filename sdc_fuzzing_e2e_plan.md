# ARM64 SDC Fuzzing End-to-End Plan

## 1. Scope and Core Decision

This repository should treat Microprobe as the control plane, QEMU and gem5 SE as the execution backends, and McPAT as the default power post-processing backend. OpenDCDiag stays in the architecture as an optional interface layer for later real-hardware validation, but it does not belong on the default simulator execution path.

The default closed loop is:

1. Offline generation and static scoring in Microprobe.
2. Golden execution with `qemu-aarch64`.
3. Faulted execution with gem5 SE.
4. McPAT post-processing from gem5 outputs.
5. Result persistence and feedback scheduling via SQLite.

This plan is intentionally grounded in the current repository state rather than only the earlier design notes. Several major building blocks already exist, but the system is not yet runnable end to end because the ARM64 target-definition layer and the gem5 fault-injection seam are still incomplete.

## 2. Current Repository Baseline

### 2.1 Already present and reusable

- `microprobe/src/microprobe/code/benchmark.py`
  - `Benchmark.metadata` already exists and is the correct structured channel for `ace_score`, `ibr_score`, `memory_pressure_score`, power summaries, and execution annotations.
- `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
  - Static ACE, IBR, memory-pressure, and Capstone validation passes already exist.
- `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
  - The SDC-oriented ARM64 policy already selects FMA, `LDP/STP`, and LSE-style instructions and chains the static scoring passes.
- `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
  - The offline CLI already generates candidates, synthesizes them through Microprobe, and persists them.
- `sdc_vault.py`
  - The SQLite vault already stores offline candidates, hashes, power, status, and metadata.
- `run_sdc_differential.py`
  - The differential runner already orchestrates compile, QEMU, gem5, and McPAT in one place.
- `mcpat/mcpat/gem5_mcpat_parser/Gem5McPATParser_custom.py`
  - The old custom parser has already been reduced to a thin compatibility wrapper around the newer `pypat` conversion path.
- `mcpat/mcpat/gem5_mcpat_parser/kunpeng920_profile.json`
  - A Kunpeng920-like ARM64 power profile already exists.
- `mcpat/mcpat/gem5_mcpat_parser/template_arm64_kunpeng920.xml`
  - An ARM64 McPAT template already exists and is usable with the local McPAT fork.

### 2.2 Still blocking a real closed loop

- `microprobe/targets/arm64/isa/armv8-common/isa.py`
  - `Arm64ISA` is still not import-clean enough for a reliable target bring-up. The class contains useful helper logic, but target import still stops in the ISA layer.
- `microprobe/targets/arm64/tests/targets/targets_tests.py`
- `microprobe/targets/arm64/tests/targets/integration_tests.py`
  - The ARM64 tests mostly skip on failure today, so they do not protect the repaired target contract.
- `microprobe/targets/arm64/wrappers/baremetaldiff.py`
  - The dedicated digest wrapper exists, but it still needs ABI-hardening validation and name normalization with the surrounding documentation and tooling.
- `run_sdc_differential.py`
  - The runner still defaults gem5 to `configs/deprecated/example/se.py` instead of a dedicated ARM/Kunpeng-style SE script.
- `gem5`
  - No real ARM SE transient fault injector is wired in-tree yet. That is the single biggest missing execution capability.

### 2.3 Non-default but valuable secondary assets

- `microprobe/sdc_fuzzing_generator.py`
  - Provides a reusable instruction pool, scoring hints, and mutation logic.
- `opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp`
- `opendcdiag/framework/device/cpu/arm64/kunpeng920_ecc.cpp`
  - Good reference material for checksum, ECC, and RAS semantics, but not a default simulator harness.
- `kunpeng920.md`
  - The architectural baseline for Kunpeng 920 / TaiShan V110-like tuning.

## 3. Target End-to-End Architecture

### 3.1 Control plane

Microprobe owns testcase synthesis, testcase metadata, and testcase selection policy.

Responsibilities:

- Select ARM64 instruction mixes that are SDC-sensitive.
- Compute static heuristics such as ACE, IBR, and memory pressure.
- Emit compilable sources or assembly.
- Store testcase metadata and runtime results in the vault.

### 3.2 Offline engine

The offline engine should live on top of the pieces already in-tree:

- Policy: `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
- Passes: `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
- Generator CLI: `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
- Vault: `sdc_vault.py`
- Optional mutation primitives: `microprobe/sdc_fuzzing_generator.py`

Offline responsibilities:

1. Generate ARM64 candidates with emphasis on:
   - 128-bit NEON
   - `FMADD/FMSUB/FNMADD/FNMSUB`
   - `LDP/STP`
   - LSE atomics
   - flag-setting arithmetic and branch chains
   - memory streams with `>= 8 KB` stride
2. Run static passes and persist:
   - `ace_score`
   - `ibr_score`
   - `memory_pressure_score`
   - `risk_score`
   - generation metadata
3. Keep only the best candidates in `PENDING` state for the outer loop.

### 3.3 Online differential engine

The default runtime pipeline is:

1. Wrap a testcase into a static ARM64 binary.
2. Run the golden binary with `qemu-aarch64`.
3. Run the same binary in gem5 SE with injected faults.
4. Extract digest from both runs.
5. If gem5 exits successfully and digest differs from the QEMU digest, classify as SDC.
6. Run McPAT on gem5 outputs and attach power summaries.
7. Persist all results back into the vault.

The main components are:

- Wrapper: `microprobe/targets/arm64/wrappers/baremetaldiff.py`
- Runner: `run_sdc_differential.py`
- gem5 config to add: `gem5/configs/example/arm/sdc_kunpeng920_se.py`
- McPAT backend to add: `power_backends/mcpat_backend.py`

### 3.4 Optional backend layer

Two power/validation backends should exist behind a common interface:

- `McPATBackend`
  - Default and required.
  - Input: gem5 `config.json`, `stats.txt`, runtime directory.
  - Output: `power_total`, `power_dynamic`, `power_leakage`, optional raw artifact paths.
- `OpenDCDiagBackend`
  - Disabled by default.
  - Future use only for real-hardware Kunpeng validation and RAS/ECC observation.

## 4. Default Data Model

### 4.1 Benchmark metadata

Use `Benchmark.metadata`, not `Benchmark.context`, for analysis and runtime annotations.

Recommended metadata keys:

- `ace_score`
- `ibr_score`
- `memory_pressure_score`
- `risk_score`
- `preferred_stride_bytes`
- `capstone_validated`
- `instruction_names`
- `seed`
- `wrapper_name`
- `golden_digest`
- `faulted_digest`
- `sdc_signal`
- `power_total`
- `power_dynamic`
- `power_leakage`
- `fault_model`
- `fault_site`

### 4.2 Vault schema

`sdc_vault.py` already contains a strong starting schema. Keep `offline_testcases` as the canonical testcase table and extend it only where feedback scheduling needs more fidelity.

Recommended steady-state columns:

- `test_id`
- `testcase_key`
- `asm_content`
- `target_name`
- `policy_name`
- `ace_score`
- `ibr_score`
- `memory_pressure_score`
- `risk_score`
- `qemu_golden_hash`
- `gem5_fault_hash`
- `mcpat_power`
- `status`
- `metadata_json`
- `created_at`
- `updated_at`

Recommended status lifecycle:

- `PENDING`
- `GOLDEN_READY`
- `RUNNING`
- `MATCHED`
- `SDC_FOUND`
- `CRASHED`
- `TIMEOUT`
- `INVALID`
- `RETIRED`

## 5. Implementation Roadmap

### Phase 0: Foundation Repair

Goal: make ARM64 target discovery, import, wrappers, and tests trustworthy enough for the rest of the pipeline.

Required work:

- Normalize target naming around one canonical tuple.
  - Candidate: `armv8_common-armv8_common-aarch64_linux_gcc`
- Keep legacy aliases only as compatibility shims.
- Complete the ARM64 ISA bring-up in:
  - `microprobe/targets/arm64/isa/armv8-common/isa.py`
- Verify the corresponding definitions in:
  - `microprobe/targets/arm64/isa/armv8-common/isa.yaml`
  - `microprobe/targets/arm64/uarch/armv8-common/microarchitecture.yaml`
  - `microprobe/targets/arm64/env/aarch64_linux_gcc.py`
  - `microprobe/targets/arm64/env/aarch64_baremetal.py`
- Decide one stable filename strategy for the ARM64 wrappers:
  - Keep `arm64asm.py`
  - Keep or rename `baremetaldiff.py`
  - Align all references, tests, and docs to the same choice
- Convert ARM64 tests from `skip on failure` to real assertions after target import is repaired.

Exit criteria:

- `import_definition(...)` succeeds for the canonical ARM64 target.
- `Arm64AsmWrapper` and `BareMetalDiffWrapper` are discoverable through the wrapper registry.
- ARM64 target tests fail loudly on regressions instead of silently skipping.

### Phase 0A: McPAT ARM64 / Kunpeng920 Foundation

Goal: make ARM64 McPAT a default backend, not a side experiment.

Required work:

- Treat these as production inputs rather than provisional experiments:
  - `mcpat/mcpat/gem5_mcpat_parser/kunpeng920_profile.json`
  - `mcpat/mcpat/gem5_mcpat_parser/template_arm64_kunpeng920.xml`
  - `mcpat/mcpat/gem5_mcpat_parser/Gem5McPATParser_custom.py`
- Add a first-class backend module:
  - `power_backends/mcpat_backend.py`
- Expose a stable result contract:
  - `power_total`
  - `power_dynamic`
  - `power_leakage`
  - artifact paths
- Continue to treat `out.ptrace` as the authoritative power artifact for this fork.
- Keep OpenDCDiag out of the default path.

Exit criteria:

- A known-good gem5 output directory produces non-zero ARM64 power summaries through the backend.
- The backend contract is callable from `run_sdc_differential.py` without direct parser knowledge.

### Phase 1: Offline Static SDC Engine

Goal: make offline generation high-throughput, deterministic, and vault-backed.

Required work:

- Keep the existing pass package as the analysis home:
  - `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
- Keep the existing policy as the generator entrypoint:
  - `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
- Keep the existing CLI as the operator-facing offline generator:
  - `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
- Reuse `InstructionPool` and mutation logic from:
  - `microprobe/sdc_fuzzing_generator.py`
- Strengthen the risk function to combine:
  - `ace_score`
  - `ibr_score`
  - `memory_pressure_score`
  - optional instruction-class bonuses for FMA, LSE, branch/flag chains, and long-stride memory
- Ensure every generated testcase lands in the vault with reproducible metadata.

Exit criteria:

- Offline CLI can generate a batch of ARM64 candidates and insert them into SQLite.
- Vault ordering by risk is stable and deterministic.

### Phase 2: Differential Execution Engine

Goal: make the outer loop actually runnable on QEMU + gem5 + McPAT.

Required work:

- Treat `microprobe/targets/arm64/wrappers/baremetaldiff.py` as the digest-emitting wrapper baseline.
- Preserve the digest scope:
  - `X0-X30`
  - `NZCV`
  - touched or conservatively full SIMD state
  - bounded global-memory checksum
- Add ABI and correctness hardening tests around the wrapper.
- Replace the runner's gem5 default with a new script:
  - `gem5/configs/example/arm/sdc_kunpeng920_se.py`
- Base the new script on:
  - `gem5/configs/example/arm/starter_se.py`
  - `gem5/src/python/gem5/components/boards/se_binary_workload.py`
- Add a fault-hook interface in the gem5 script or immediately below it.
- Keep QEMU as the ISA golden executor for statically linked single-thread ELFs.

Exit criteria:

- A no-fault run produces the same digest in QEMU and gem5.
- A deliberately injected fault can flip the gem5 digest without causing a crash.
- McPAT output from the same gem5 run is attached to the result payload.

### Phase 3: Feedback Scheduling and Evolution

Goal: replace the deprecated GA path with a Python 3-native scheduler.

Required work:

- Do not inherit from `microprobe/src/microprobe/driver/genetic.py`.
- Add a new scheduler:
  - `sdc_scheduler.py` or `sdc_feedback.py`
- Fetch seeds from `sdc_vault.py` by risk and recent outcome.
- Combine static and dynamic evidence in the fitness function:
  - `fitness = (ace_score * ibr_score * sdc_signal) / (mcpat_power + 1)`
- Keep room for policy switches that bias toward:
  - low-power high-coverage seeds
  - high-power thermal-edge seeds
- Reuse mutation and recombination logic from `microprobe/sdc_fuzzing_generator.py` where possible.

Exit criteria:

- Scheduler can select, execute, score, and reinsert seeds without touching deprecated GA code.

### Phase 4: Validation, Regression, and Operations

Goal: turn the prototype into a maintainable research toolchain.

Required work:

- Add unit tests for:
  - ARM64 target import
  - static pass metadata
  - vault ordering
  - McPAT backend summaries
- Add integration tests for:
  - offline batch generation
  - wrapper compilation
  - QEMU digest extraction
  - no-fault QEMU vs gem5 match
- Add operator documentation for required toolchain pieces:
  - `aarch64-linux-gnu-gcc`
  - `qemu-aarch64`
  - `gem5.opt`
  - McPAT runtime
- Define artifact layout for:
  - generated sources
  - compiled ELFs
  - gem5 output directories
  - JSON result payloads

### Phase 5: Deferred OpenDCDiag Integration

Goal: keep a clean extension seam for later real-hardware validation.

Required work:

- Add:
  - `power_backends/opendcdiag_backend.py`
- Restrict scope to interface definition and result-shape compatibility.
- Defer real enablement until Kunpeng hardware validation becomes a project goal.

Exit criteria:

- The default simulator pipeline works without OpenDCDiag.
- The backend interface is stable enough that real-node validation can be added later without reworking the vault or scheduler contracts.

## 6. File-Level Ownership Map

| Area | Existing files to keep | New or revised files |
|------|------------------------|----------------------|
| ARM64 target import | `microprobe/targets/arm64/isa/armv8-common/isa.py`, `microprobe/src/microprobe/target/__init__.py`, `microprobe/targets/arm64/env/aarch64_linux_gcc.py`, `microprobe/targets/arm64/env/aarch64_baremetal.py` | none required, but tests must be tightened |
| Offline analysis | `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`, `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`, `microprobe/sdc_fuzzing_generator.py` | optional new pass helpers only if required |
| Offline orchestration | `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`, `sdc_vault.py` | optional vault migration helper |
| Differential wrapper | `microprobe/targets/arm64/wrappers/baremetaldiff.py`, `microprobe/targets/arm64/wrappers/arm64asm.py` | optional wrapper alias/rename for naming consistency |
| Differential runner | `run_sdc_differential.py` | `gem5/configs/example/arm/sdc_kunpeng920_se.py` |
| Power backend | `mcpat/mcpat/gem5_mcpat_parser/Gem5McPATParser_custom.py`, `mcpat/mcpat/gem5_mcpat_parser/kunpeng920_profile.json`, `mcpat/mcpat/gem5_mcpat_parser/template_arm64_kunpeng920.xml` | `power_backends/mcpat_backend.py`, `power_backends/__init__.py` |
| Feedback loop | `microprobe/sdc_fuzzing_generator.py`, `sdc_vault.py` | `sdc_scheduler.py` or `sdc_feedback.py` |
| Deferred hardware backend | `opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp`, `opendcdiag/framework/device/cpu/arm64/kunpeng920_ecc.cpp` | `power_backends/opendcdiag_backend.py` |

## 7. Acceptance Criteria

The project should only be called end-to-end ready when all of the following are true:

1. ARM64 target import succeeds through the canonical tuple without manual patching during the run.
2. Offline generation can create and persist batches of candidates into the SQLite vault.
3. The digest wrapper can compile a static ELF through `aarch64-linux-gnu-gcc`.
4. QEMU and gem5 match on the same testcase when no fault is injected.
5. gem5 can expose at least one real faulted run that differs from the QEMU golden digest while still exiting normally.
6. McPAT can post-process that gem5 output and produce non-zero power summaries.
7. The vault records testcase metadata, hashes, power, status, and scheduler annotations.
8. A Python 3-native scheduler can feed successful or near-miss seeds back into the offline generator.

## 8. Recommended Immediate Next Steps

If execution starts now, the most effective order is:

1. Finish ARM64 target import in `microprobe/targets/arm64/isa/armv8-common/isa.py`.
2. Tighten ARM64 tests so they assert the repaired contract instead of skipping.
3. Add `gem5/configs/example/arm/sdc_kunpeng920_se.py` with a fault-hook seam.
4. Move McPAT invocation behind `power_backends/mcpat_backend.py`.
5. Validate `QEMU == gem5` on no-fault runs.
6. Only then add the Python 3 feedback scheduler.

That ordering preserves the intended A/B asynchronous design while respecting the actual state of this repository.
