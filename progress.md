# Progress Log

## Session: 2026-04-04

### Phase 1: Requirements & Discovery
- **Status:** complete
- **Started:** 2026-04-04
- Actions taken:
  - Inspected repository layout and confirmed this is a large monorepo with control-plane, test, and vendor subtree paths.
  - Read `docs/spec.md` to capture the target completed architecture and required loops.
  - Read `docs/plan.md` to capture claimed phase completion levels and unfinished areas.
  - Created persistent planning files to track work during end-to-end implementation.
- Files created/modified:
  - `task_plan.md` (created)
  - `findings.md` (created)
  - `progress.md` (created)

### Phase 2: Gap Analysis & Technical Plan
- **Status:** complete
- Actions taken:
  - Read `docs/state.md` to reconcile documented completion claims with currently declared open risks.
  - Inspected outer-loop, scheduler, hardware-lane, and hardware-result control-plane code paths and their core tests.
  - Ran repo-root `pytest` and observed collection failure due to missing repo-local import configuration.
  - Checked available interpreters and identified the usable Conda Python and `pytest` binaries in `/Users/wangxu/anaconda3/bin`.
- Files created/modified:
  - `task_plan.md` (updated)
  - `findings.md` (updated)
  - `progress.md` (updated)

### Phase 3: Implementation
- **Status:** complete
- Actions taken:
  - Added `tests/conftest.py` so direct `pytest` from the repo root can import `sdc_agent`.
  - Extended `sdc_agent/scheduler.py` to compute and expose `inner_value_score`, `diversity_bonus`, `legality_factor`, `power_gain`, `profile_name`, and instruction-family feedback.
  - Updated scheduler mutation planning and agent summaries to surface the new Phase 3 signals.
  - Extended `microprobe/src/microprobe/driver/genetic.py` with profile-aware fallback instruction recovery, diversity-aware partner selection, offspring profile filtering, and richer lineage metadata.
  - Updated hardware-promotion scoring to consider the new inner-loop value signal.
  - Added and updated tests in `tests/test_sdc_scheduler.py`, `tests/test_sdc_genetic_driver.py`, and `tests/test_sdc_agent.py`.
- Files created/modified:
  - `tests/conftest.py` (created)
  - `sdc_agent/scheduler.py` (updated)
  - `sdc_agent/agent.py` (updated)
  - `sdc_agent/hardware_lane.py` (updated)
  - `microprobe/src/microprobe/driver/genetic.py` (updated)
  - `tests/test_sdc_scheduler.py` (updated)
  - `tests/test_sdc_genetic_driver.py` (updated)
  - `tests/test_sdc_agent.py` (updated)

### Phase 4: Testing & Verification
- **Status:** complete
- Actions taken:
  - Verified targeted control-plane regressions with Conda Python module invocation.
  - Verified direct repo-root `pytest` now succeeds after adding `tests/conftest.py`.
  - Ran the full root `tests/` suite and targeted `microprobe` ARM64 tests.
- Files created/modified:
  - `progress.md` (updated)

### Phase 6: ARM64 Full-Catalog Generation
- **Status:** complete
- Actions taken:
  - Downloaded and extracted the official Arm A64 XML snapshot and normalized it into a local ARM64 catalog.
  - Added catalog parsing, sample-assembly rendering, execution classification, Kunpeng920 hotness tagging, and clang-based validation utilities.
  - Generated `microprobe/targets/arm64/isa/armv8-common/arm_a64_catalog.json` and wired catalog-backed profiles into offline generation.
  - Extended the ARM64 audit tool to compare both the legacy executable subset and the new catalog against the official XML baseline.
  - Added regression tests for catalog parsing, catalog-aware audit reporting, catalog-driven generation profiles, and ARM64 target catalog access.
- Files created/modified:
  - `microprobe/src/microprobe/utils/arm64_isa_catalog.py` (created)
  - `microprobe/targets/arm64/tools/a64_isa_catalog.py` (created)
  - `microprobe/targets/arm64/isa/armv8-common/arm_a64_catalog.json` (generated)
  - `microprobe/targets/arm64/tools/a64_isa_audit.py` (updated)
  - `microprobe/targets/generic/tools/mp_sdc_offline_gen.py` (updated)
  - `sdc_agent/generation.py` (updated)
  - `microprobe/targets/arm64/isa/armv8-common/isa.py` (updated)
  - `microprobe/targets/arm64/tests/tools/test_a64_isa_catalog.py` (created)
  - `microprobe/targets/arm64/tests/tools/test_a64_isa_audit.py` (updated)
  - `tests/test_sdc_generation_profiles.py` (updated)
  - `microprobe/targets/arm64/tests/targets/test_target_contract.py` (updated)

### Phase 7: Remaining Local Plan Execution
- **Status:** complete
- Actions taken:
  - Added real scripted `memory_bit_flip` support across gem5 fault target parsing, `sdc_kunpeng920_se.py`, and differential observation parsing.
  - Upgraded hardware result ingest so detector payloads and machine/build/runtime metadata are normalized before writeback.
  - Added template/PCFG generation helpers and heuristic mutation-advice output to the generation and scheduling paths.
  - Re-ran root, microprobe, and gem5 helper regressions after the new Phase 5/6/7 work.
- Files created/modified:
  - `gem5/configs/example/arm/sdc_fault_request.py` (updated)
  - `gem5/configs/example/arm/sdc_kunpeng920_se.py` (updated)
  - `gem5/tests/test_sdc_fault_request.py` (updated)
  - `sdc_agent/differential.py` (updated)
  - `sdc_agent/hardware_results.py` (updated)
  - `sdc_agent/generation.py` (updated)
  - `sdc_agent/generation_strategies.py` (created)
  - `sdc_agent/mutation_advisor.py` (created)
  - `sdc_agent/scheduler.py` (updated)
  - `sdc_agent/agent.py` (updated)
  - `tests/test_run_sdc_differential.py` (updated)
  - `tests/test_hardware_results.py` (updated)
  - `tests/test_sdc_generation_strategies.py` (created)
  - `tests/test_sdc_scheduler.py` (updated)

### PR Check Follow-up
- **Status:** complete
- Actions taken:
  - Reworked `memory_bit_flip` semantics so `mem:0x...` is treated as guest virtual memory in SE mode instead of raw physical memory.
  - Added strict validation for malformed CPU-qualified fault targets and incompatible fault-model/target-kind combinations.
  - Added BaseCPU helpers for virtual-memory byte read/bit-flip and updated the gem5 ARM64 SE runner to use them.
  - Re-ran differential, gem5 helper, outer-loop, and phase4 validation regressions after the fix.
- Files created/modified:
  - `gem5/configs/example/arm/sdc_fault_request.py` (updated)
  - `gem5/configs/example/arm/sdc_kunpeng920_se.py` (updated)
  - `gem5/src/cpu/base.hh` (updated)
  - `gem5/src/cpu/base.cc` (updated)
  - `gem5/src/cpu/BaseCPU.py` (updated)
  - `sdc_agent/differential.py` (updated)
  - `gem5/tests/test_sdc_fault_request.py` (updated)
  - `tests/test_run_sdc_differential.py` (updated)

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Planning bootstrap | Read docs and create plan files | On-disk task context exists | Created `task_plan.md`, `findings.md`, `progress.md` | PASS |
| Repo-root pytest collection | `pytest -q tests/test_sdc_inner_loop.py ...` | Tests collect from repo root | Collection failed with `ModuleNotFoundError: sdc_agent` | FAIL |
| Interpreter discovery | `which -a python python3 pytest` | Find a usable project Python | Conda Python/pytest found at `/Users/wangxu/anaconda3/bin` | PASS |
| Targeted control-plane regressions | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_scheduler.py tests/test_sdc_genetic_driver.py tests/test_sdc_agent.py tests/test_sdc_inner_loop.py tests/test_sdc_outer_loop.py tests/test_sdc_hardware_lane.py tests/test_sdc_phase4_validation.py tests/test_sdc_phase2_validation.py` | New Phase 3 changes do not break control plane | `27 passed` | PASS |
| Direct root pytest after bootstrap fix | `/Users/wangxu/anaconda3/bin/pytest -q tests/test_sdc_scheduler.py tests/test_sdc_genetic_driver.py tests/test_sdc_agent.py` | Direct pytest from repo root works | `14 passed` | PASS |
| Full root test suite | `/Users/wangxu/anaconda3/bin/pytest -q tests` | No regressions across project tests | `58 passed` | PASS |
| Microprobe ARM64 targeted tests | `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py` | Evolution/profile changes preserve target contracts | `8 passed` | PASS |
| Supporting v2 and hardware tests | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_generation_profiles.py tests/test_sdc_vault_v2.py tests/test_hardware_results.py tests/test_power_backends.py` | Adjacent regressions remain green | `11 passed` | PASS |
| ARM64 catalog parser tests | `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_a64_isa_catalog.py` | XML/docs parsing and sample validation remain stable | `2 passed` | PASS |
| ARM64 audit tests | `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_a64_isa_audit.py` | Catalog-aware audit reporting works | `2 passed` | PASS |
| Catalog-backed generation profiles | `/Users/wangxu/anaconda3/bin/pytest -q tests/test_sdc_generation_profiles.py` | New catalog profiles do not regress existing generation behavior | `5 passed` | PASS |
| ARM64 root regressions | `/Users/wangxu/anaconda3/bin/pytest -q tests` | Root project regression suite remains green | `61 passed` | PASS |
| ARM64 target regressions | `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests` | ARM64 target/tool tests remain green | `42 passed` | PASS |
| Real XML audit | `python3 microprobe/targets/arm64/tools/a64_isa_audit.py ...` | Catalog should cover all official mnemonics in selected classes | `general/system/float/advsimd cat missing = 0` | PASS |
| Real full-catalog generation | `python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py --profile ALL_GENERATABLE --count 1 --sequence-length 512 ...` | Generator should auto-expand work to cover the full catalog | `planned=4 inserted=4 failed=[]` | PASS |
| Memory fault + gem5 helper regressions | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_run_sdc_differential.py gem5/tests/test_sdc_fault_request.py` | New memory injector path parses and classifies correctly | `13 passed` | PASS |
| Hardware ingest normalization regressions | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_hardware_results.py tests/test_power_backends.py` | Detector and machine metadata normalization stays compatible | `4 passed` | PASS |
| Phase 7 strategy regressions | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_generation_strategies.py tests/test_sdc_generation_profiles.py tests/test_sdc_scheduler.py tests/test_sdc_agent.py tests/test_sdc_genetic_driver.py` | Template/PCFG generation and mutation advice integrate cleanly | `23 passed` | PASS |
| Expanded root test suite after Phase 5/6/7 work | `/Users/wangxu/anaconda3/bin/pytest -q tests` | Entire root suite remains green after new work | `65 passed` | PASS |
| Expanded targeted subtree tests | `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py gem5/tests/test_sdc_fault_request.py` | Microprobe target contract and gem5 helper stay green | `13 passed` | PASS |
| PR-check follow-up regressions | `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_run_sdc_differential.py gem5/tests/test_sdc_fault_request.py tests/test_sdc_outer_loop.py tests/test_sdc_phase4_validation.py` | Guest-virtual memory injection semantics and fail-fast parsing do not break orchestration | `22 passed` | PASS |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-04-04 | None yet | 1 | Discovery phase only |
| 2026-04-04 | `pytest` could not import `sdc_agent` | 1 | Resolved by adding `tests/conftest.py` with repo-root path bootstrap |
| 2026-04-04 | `/usr/bin/python3 -m pytest` lacked `pytest` | 1 | Switched to identifying the intended Python environment instead of repeating the same failing invocation |
| 2026-04-04 | Initial catalog sample validation picked feature-gated `ABS` encodings and failed on default `.arch armv8-a` | 1 | Kept clang validation as best-effort metadata for catalog sequences instead of using it as the sole acceptance criterion for full-catalog generation |
| 2026-04-04 | Initial `neon_fma_heavy` template used `LD1`/`ST1` and failed during wrapper assembly generation | 1 | Replaced unstable mnemonics with aggressive but wrapper-stable `LDP/STP` in the first template version |
| 2026-04-05 | First `memory_bit_flip` path wrote through physical memory and could target the wrong byte in SE mode | 1 | Switched the injector to an SE-translating virtual-memory helper and tightened fault-target validation |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 5: Delivery |
| Where am I going? | Final review and concise handoff |
| What's the goal? | Bring the source implementation in line with `docs/spec.md` and `docs/plan.md`, including full ARM64 catalog generation coverage and the remaining locally feasible Phase 5/6/7 upgrades, and verify it end to end |
| What have I learned? | Full A64 coverage is best modeled as an official-XML-backed catalog plus generation profiles, while the remaining local plan gaps centered on memory fault injection, richer hardware ingest, and smarter generation advice |
| What have I done? | Added the catalog pipeline, advanced Phase 5/6/7 with memory fault injection and intelligent generation helpers, and verified the changes across root tests, ARM64 tests, and targeted gem5 helper tests |

---
*Update after completing each phase or encountering errors*
