# Progress Log

## Session: 2026-03-26

### Phase 1: Workspace Discovery
- **Status:** complete
- **Started:** 2026-03-26
- Actions taken:
  - Confirmed the workspace root and top-level repository composition.
  - Read the local planning skill instructions and initialized planning files.
  - Reviewed the top-level `AGENTS.md` plus the `microprobe` and `gem5` READMEs.
  - Mapped core Microprobe extension surfaces via search and identified ARM64-specific policy, tool, wrapper, ISA, and test files.
  - Read the base wrapper and pass abstractions plus the existing ARM64 `sdc_detect` policy.
  - Identified an architectural mismatch between the requested `benchmark.context['key']` data flow and the current `Benchmark.context -> Context` implementation.
  - Verified that the existing `sdc_detect` policy references pass classes that do not exist in the current Microprobe pass tree.
  - Read the local ARM64 environment, wrapper, user guide, ISA property YAMLs, and the existing `sdc_fuzzing_generator.py`.
  - Mapped a minimal gem5 ARM SE-mode execution path and confirmed the local McPAT fork supports incremental trace-style power recomputation.
  - Read the local `kunpeng920.md` architecture note to align testcase priorities with TaiShan V110/Kunpeng 920 behavior.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (created)

### Phase 2: Microprobe Extension Mapping
- **Status:** complete
- Actions taken:
  - Read ARM64-specific policy, environment, wrapper, user-guide, ISA property, and test files.
  - Verified the standard policy/tool invocation path via `mp_seq.py` and wrapper discovery in `microprobe.code`.
  - Confirmed that `Instruction.sets()`, `Instruction.uses()`, and `Bbl.distance()` provide the necessary primitives for a static ACE implementation.
  - Probed runtime behavior and found that ARM64 policies resolve, but ARM64 target import and wrapper discovery are currently inconsistent.
  - Integrated parallel exploration results for gem5/QEMU/McPAT/OpenDCDiag and for Microprobe ARM64 extension seams.
  - Confirmed that the current target tuple parser enforces a three-part name, which conflicts with the local ARM64 target naming convention.
  - Verified that the current ARM64 `seq` policy is a better implementation base than the draft `sdc_detect` policy because it uses real pass classes.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 3: Execution Stack Mapping
- **Status:** complete
- Actions taken:
  - Read minimal gem5 ARM SE-mode launchers, stdlib workload plumbing, and the ARM starter SE configuration.
  - Verified that `qemu-aarch64` user-mode execution is directly supported and suitable as the ISA-level golden oracle.
  - Inspected the bundled gem5-to-McPAT bridge and confirmed it is x86-biased rather than ARM-ready.
  - Inspected OpenDCDiag ARM64 SDC and Kunpeng920 ECC code to separate reusable detection ideas from non-reusable heavy runtime infrastructure.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 4: Architecture Design
- **Status:** complete
- Actions taken:
  - Synthesized a repository-grounded A/B asynchronous SDC fuzzing architecture for ARMv8-A and Kunpeng 920 style targets.
  - Identified foundation work needed before higher-level features: target import cleanup, wrapper module naming cleanup, metadata channel design, and a fresh GA driver path.
  - Aligned testcase priorities with TaiShan V110 / Kunpeng 920 traits: 4-wide OoO, 128-bit NEON, dual FPU, pair load/store, cache-sensitive memory behavior, and LSE-style synchronization pressure.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 5: Foundation Implementation
- **Status:** complete
- Actions taken:
  - Added structured `Benchmark.metadata` support to carry ACE/IBR/power-style scores without abusing `Context`.
  - Repaired ARM64 environment defaults and ARM64 SDC policy scaffolding so wrapper discovery and policy lookup are less brittle.
  - Added a native `microprobe.passes.sdc_analysis` package with static ACE/IBR/memory-pressure/capstone validation passes.
  - Added `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` as the new Kunpeng-aware offline generation policy surface.
  - Replaced the colliding ARM64 `asm.py` wrapper module with a uniquely named ARM64 wrapper module to stop generic wrapper discovery breakage.
  - Added `mcpat/mcpat/gem5_mcpat_parser/kunpeng920_profile.json` plus ARM64 template-profile selection through `mcpat/mcpat/pypat`.
  - Replaced the old `Gem5McPATParser_custom.py` implementation with a thin compatibility wrapper around `pypat`.
  - Fixed `pypat` config-expression parsing so ARM profile expressions using `max(...)` survive substitution.
  - Fixed local McPAT binary invocation to use a resolved path and added clearer McPAT failure messages with output excerpts.
  - Verified ARM64/Kunpeng-style McPAT XML generation from minimal synthetic gem5 `config.json` and `stats.txt`.
  - Rebuilt the ARM64 Kunpeng920 McPAT template on top of a Xeon-derived skeleton that the local McPAT/Cacti fork accepts.
  - Verified end-to-end ARM64 McPAT execution through `Gem5McPATParser_custom.py`, `python3 -m pypat`, and `pypat.conversion.convert.run(...)`.
  - Identified that this McPAT fork prints area vectors to stdout and writes block-level power to `out.ptrace`, then updated the backend to run in the target directory and parse `out.ptrace` as the authoritative power artifact.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/code/benchmark.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/env/aarch64_linux_gcc.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/env/aarch64_baremetal.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_detect.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/passes/sdc_analysis/__init__.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/wrappers/arm64asm.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/wrappers/asm.py` (deleted)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/gem5_mcpat_parser/kunpeng920_profile.json` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/gem5_mcpat_parser/template_arm64_kunpeng920.xml` (rewritten)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/gem5_mcpat_parser/Gem5McPATParser_custom.py` (rewritten)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/conversion/templates.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/conversion/profiles.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/conversion/gem5_to_mcpat.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/conversion/convert.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/parsers/mcpat_text.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/pypat/__main__.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/run_mcpat.sh` (updated)

### Phase 6: Differential Execution Bring-Up
- **Status:** in progress
- Actions taken:
  - Added `microprobe/targets/arm64/wrappers/baremetal_diff.py` with a `BareMetalDiffWrapper` that emits `volatile` inline asm, snapshots GPR/SIMD/NZCV state, hashes memory, and prints a single `SDC_DIGEST=...` line.
  - Preserved `sp` and `x29` across the digest epilogue so the wrapper can safely return to normal C control flow after arbitrary benchmark instructions.
  - Added `/Users/wangxu/1-project/sdc-fuzzing/run_sdc_differential.py` as the lightweight compile/QEMU/gem5/McPAT orchestration entrypoint.
  - Verified that the new wrapper module imports cleanly and that the new differential runner parses CLI arguments successfully.
  - Repaired the ARM64 operand/uarch definition layer enough to import the microarchitecture and expose the next real ISA blockers.
  - Added a compatibility path so ARM64 sidecar instruction YAMLs under `instruction_props/` are imported as instruction-definition extensions rather than misread as property files.
  - Confirmed that ARM64 target import still stops at `Arm64ISA` because the class remains abstract and references undefined instruction names.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/wrappers/baremetal_diff.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/run_sdc_differential.py` (created)

### Phase 8: Systematic Code Review
- **Status:** complete
- Actions taken:
  - Re-read the new ARM64/McPAT/SDC implementation with a code-review mindset focused on functionality, logic, security, and maintainability.
  - Cross-checked the default gem5 runner arguments against the repository’s actual ARM SE script interface.
  - Validated the remaining ARM64 target import failure path after each compatibility fix to isolate the current root cause.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Planning file presence | project root | Files exist for persistent task tracking | `task_plan.md`, `findings.md`, `progress.md` created | ✓ |
| Policy lookup | `find_policy(..., 'seq'/'sdc_detect')` | ARM64 policies resolvable | Both policies resolved | ✓ |
| Target import | `import_definition('armv8-common-cortex-a53-aarch64_linux_gcc')` | ARM64 target imports | Failed: invalid target tuple format | ✗ |
| Wrapper lookup | `get_wrapper('AsmWrapper')` | ARM64 asm wrapper available | Failed: unknown wrapper | ✗ |
| Wrapper lookup | `get_wrapper('CWrapper')` | Generic wrapper loads cleanly | Failed first due duplicate `asm.py` module name collision | ✗ |
| Execution seam check | gem5 `set_se_binary_workload(..., stdout_file=...)` | Can capture wrapped digest output in SE mode | Supported in stdlib board API | ✓ |
| McPAT seam check | bundled gem5 parser | ARM-friendly postprocessing path | Parser/template are x86-biased | ✗ |
| Static compile | updated Microprobe and McPAT Python files | Python syntax valid | `py_compile` passed across updated files | ✓ |
| ARM64 McPAT XML generation | minimal synthetic gem5 config/stats | Generate ARM64/Kunpeng-like McPAT XML | XML generated successfully via `Gem5McPATParser_custom.py` | ✓ |
| ARM64 McPAT execution | minimal synthetic gem5 config/stats | Local McPAT binary returns power report | `Gem5McPATParser_custom.py` + local `mcpat` returned successfully | ✓ |
| `pypat` directory mode | minimal synthetic gem5 config/stats | `python3 -m pypat` emits XML and McPAT artifacts | `conv.xml`, `out.area`, `out.ptrace`, `mcpat_results.txt` created successfully | ✓ |
| Structured McPAT summary | `pypat.conversion.convert.run(...)` with `arm64-kunpeng920` | Non-zero power summary for backend use | Returned non-zero `power_total` and `power_peak_dynamic` from `out.ptrace` | ✓ |
| Differential wrapper import | `baremetal_diff.py` | Wrapper module imports and constructs | `BareMetalDiffWrapper` instantiated successfully | ✓ |
| Differential runner CLI | `python3 run_sdc_differential.py --help` | CLI renders without runtime errors | Help text rendered successfully | ✓ |
| ARM64 uarch import | `import_microarchitecture_definition(.../armv8-common)` | ARM64 microarchitecture imports cleanly | Import succeeded with cache hierarchy | ✓ |
| ARM64 target import | `import_definition('armv8_common-armv8_common-aarch64_linux_gcc')` | End-to-end ARM64 target import succeeds | Failed later in `Arm64ISA`: abstract methods still unimplemented | ✗ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-03-26 | Planning files missing | 1 | Created the files in project root |
| 2026-03-26 | ARM64 target import tuple rejected | 1 | Logged as a foundational integration gap for the roadmap |
| 2026-03-26 | Wrapper discovery collided on `asm.py` module name | 1 | Logged as a foundational integration gap for the roadmap |
| 2026-03-26 | Draft ARM64 SDC policy referenced nonexistent passes | 1 | Recorded that implementation should branch from working `seq` policy instead |
| 2026-03-26 | McPAT parser README referenced missing `run_mcpat.sh` | 1 | Logged as a non-blocking glue gap; parser code itself is still reusable |
| 2026-03-26 | `pypat` config substitution broke on `max(...)` profile expressions | 1 | Replaced naive comma splitting with top-level comma parsing |
| 2026-03-26 | Local McPAT binary path resolved to `mcpat` instead of an executable path | 1 | Switched subprocess invocation to `Path.resolve()` |
| 2026-03-26 | Local McPAT ARM runs fail with data-array compatibility errors | 1 | Replaced the ARM template with a Xeon-derived compatible skeleton and verified successful execution |
| 2026-03-26 | `parse_mcpat_summary` returned zeros on successful runs | 1 | Discovered stdout carried `out.area` rather than power; switched backend execution to the target directory and parse fallback to `out.ptrace` |
| 2026-03-26 | ARM64 ISA import failed on implicit `NZCV`/`LR` operands and incomplete uarch layout | 2 | Re-declared those operands as constant-register operands and added the missing uarch class/module/property skeleton |
| 2026-03-26 | ARM64 instruction extension YAMLs were being parsed as property files | 2 | Added a compatibility shim so sibling instruction-definition YAMLs are imported as extension definitions instead of properties |
| 2026-03-26 | ARM64 target import now fails at `Arm64ISA` instantiation | 3 | Confirmed the class is still abstract and helper methods reference undefined instruction names, so execution remains blocked pending ISA implementation work |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 8 complete: systematic review finished after bringing the ARM64 target definition layer further forward |
| Where am I going? | Finish the concrete ARM64 ISA implementation work, then wire the new wrapper into a generated benchmark and validate the first real QEMU digest / gem5 differential pass |
| What's the goal? | Make the ARM64 SDC fuzzing foundation executable in this repo, not only documented |
| What have I learned? | The local McPAT fork can model Kunpeng-like ARM64 parameters if we stay on a Xeon-compatible skeleton and treat `out.ptrace` as the real power artifact; the main execution blockers have now shifted to the ARM64 ISA implementation and wrapper ABI correctness |
| What have I done? | Implemented the Microprobe/ARM64/`pypat` foundation changes, brought up ARM64 McPAT execution end-to-end, added the first ARM64 differential wrapper and runner skeleton, repaired much of the ARM64 target-definition layer, and completed a systematic review of the remaining high-risk issues |

---
*Update after completing each phase or encountering errors*

## Session: 2026-03-27

### Phase 9: End-to-End Documentation
- **Status:** complete
- Actions taken:
  - Re-read the project planning files before making new design decisions, per the planning workflow.
  - Re-validated the on-disk ARM64, Microprobe, gem5, McPAT, and vault files that matter for the SDC fuzzing pipeline.
  - Confirmed that several major building blocks already exist in-tree, including `Benchmark.metadata`, static SDC analysis passes, the ARM64 SDC fuzzing policy, the offline generator CLI, the SQLite vault, the ARM64 McPAT profile/template, and the differential runner skeleton.
  - Identified the most important remaining blockers to a true end-to-end run: incomplete ARM64 ISA importability, drift between historical notes and current wrapper filenames, lack of a real ARM SE fault injector, and gem5 still defaulting to a deprecated SE script in the differential runner.
  - Wrote a new repository-grounded end-to-end design document that turns the earlier discussion into a concrete roadmap with phases, file ownership, data flow, risks, and acceptance criteria.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_fuzzing_e2e_plan.md` (created)

### Phase 10: Execution Path Hardening
- **Status:** complete
- Actions taken:
  - Re-checked the current ARM64 target and confirmed that the canonical import path now succeeds in the current tree.
  - Hardened `microprobe/targets/generic/wrappers/c.py` so newer plain-string `pass_info` entries no longer crash wrapper rendering.
  - Added a compatibility wrapper alias file for `baremetal_diff.py` while keeping `baremetaldiff.py` as the canonical implementation module.
  - Added `power_backends/mcpat_backend.py` and `power_backends/opendcdiag_backend.py`, plus package exports, to make the power post-processing path explicit.
  - Added `gem5/configs/example/arm/sdc_kunpeng920_se.py` as the new ARM64/Kunpeng-like SE runner with guest stdout/stderr capture defaults and a fault-request manifest seam.
  - Rewired `run_sdc_differential.py` to default to the new ARM64 gem5 config and the new `McPATBackend`, while tolerating McPAT failures as data instead of hard-crashing the whole run.
  - Softened `microprobe/src/microprobe/utils/typeguard_decorator.py` so missing `typeguard` no longer breaks local test execution.
  - Added pytest-discoverable ARM64 contract tests that cover import aliases, wrapper registry, static-score synthesis, and digest-wrapper rendering.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/generic/wrappers/c.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/wrappers/baremetal_diff.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/power_backends/__init__.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/power_backends/mcpat_backend.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/power_backends/opendcdiag_backend.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_kunpeng920_se.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/run_sdc_differential.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/utils/typeguard_decorator.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/tests/conftest.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/tests/targets/test_target_contract.py` (created)

### Phase 11: Feedback Scheduling
- **Status:** complete
- Actions taken:
  - Added `sdc_scheduler.py` as the new Python 3-native seed ranking and result-foldback layer on top of `sdc_vault.py`.
  - Normalized runner statuses such as `golden_only`, `matched`, `sdc_found`, `gem5_timeout`, and failure modes into vault-friendly statuses.
  - Added root-level tests for scheduler persistence, candidate ordering, runner digest/classification helpers, and backend normalization.
  - Re-ran the ARM64 contract tests together with the new root tests to ensure the new feedback layer does not regress the earlier Microprobe/gem5/McPAT plumbing.
  - Checked local tool availability and confirmed that full binary runtime validation is still blocked because the required ARM cross-compiler, QEMU user-mode binary, and built gem5 ARM executable are not available in the current environment.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_scheduler.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_scheduler.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_run_sdc_differential.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_power_backends.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 12: Operator Tooling
- **Status:** complete
- Actions taken:
  - Added a real CLI to `sdc_scheduler.py` so operators can `rank`, `plan`, and `record` vault feedback directly from the shell.
  - Added `sdc_preflight.py` to check the local ARM64 SDC runtime prerequisites in one command before attempting differential execution.
  - Added `tests/test_sdc_preflight.py` to lock down command/path detection and non-ready environment reporting.
  - Re-ran the root test suite and verified that the scheduler CLI and preflight checker behave as expected in this environment.
  - Verified the current machine is still not runtime-ready because `aarch64-linux-gnu-gcc`, `qemu-aarch64`, and `gem5/build/ARM/gem5.opt` are absent, while the local McPAT binary and ARM64 gem5 config are present.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_scheduler.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_preflight.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_preflight.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 13: Campaign Orchestration
- **Status:** complete
- Actions taken:
  - Refactored `run_sdc_differential.py` so the compile/QEMU/gem5/McPAT chain is available through a reusable `run_differential(...)` Python API in addition to the existing CLI.
  - Added `sdc_campaign.py` as the root-level outer-loop orchestrator that selects candidates from the vault, resolves testcase source files, runs the differential executor, writes per-testcase result JSON artifacts, and folds the result back into the vault through the scheduler.
  - Added targeted tests for the new programmatic runner entrypoint and for campaign dry-run, successful execution, and preflight-blocked behavior.
  - Re-ran the expanded regression suite and confirmed the root stack now has 23 passing tests across ARM64 target contracts, scheduler math, runner helpers, power backends, preflight checks, and campaign orchestration.
  - Confirmed that the new orchestration layer is fully validated in pure Python, while true compiled execution is still gated on the missing ARM cross-compiler, QEMU user binary, and built gem5 ARM binary on this machine.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/run_sdc_differential.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_campaign.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_run_sdc_differential.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_campaign.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 14: Source Materialization
- **Status:** complete
- Actions taken:
  - Added `sdc_materialize.py` so raw vault `asm_content` can be rendered into digest-bearing ARM64 C sources with a stable `SDC_DIGEST` reporting scaffold.
  - Taught `sdc_campaign.py` to auto-materialize testcase sources on demand whenever `source_path` metadata is missing but the vault row still contains assembly text.
  - Added tests for source rendering, metadata update on materialization, and campaign execution that starts from a vault row with no pre-existing source file.
  - Fixed a real `sqlite3.Row` compatibility bug in the metadata decoder while validating the new materialization path.
  - Re-ran the full regression suite and confirmed 26 tests pass across the ARM64 contract path plus all current root-level orchestration layers.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_materialize.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_campaign.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_materialize.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_campaign.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 15: Cross-Repo Integration Validation
- **Status:** complete
- Actions taken:
  - Added `tests/test_offline_to_campaign_integration.py` to exercise the real `microprobe` offline generator path, persist the generated testcase into a temporary vault, and run that testcase through `sdc_campaign.py`.
  - Validated that `BareMetalDiffWrapper`-generated `.c` outputs now cross the repo boundary cleanly: the root campaign can consume the `source_path` produced by `microprobe` without materializing a fallback source.
  - Re-ran the expanded root regression suite and confirmed 27 tests now pass across ARM64 contracts, scheduler math, runner helpers, power backends, preflight, campaign orchestration, source materialization, and the new cross-repo flow.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_offline_to_campaign_integration.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 16: Fault Argument Plumbing
- **Status:** in progress
- Actions taken:
  - Added structured fault-request options to `run_sdc_differential.py` so the root differential runner can forward `fault_model`, `fault_target`, `fault_bit`, and `fault_tick` directly to the gem5 SDC config.
  - Threaded the same fault-request options through `sdc_campaign.py`, which means the outer-loop orchestrator can now express injection intent without forcing callers to build raw gem5 argument strings by hand.
  - Added focused tests that verify fault arguments are rendered correctly and that the campaign layer passes them through to the runner unchanged.
  - In parallel, hardened the gem5-side schema by adding `configs/example/arm/sdc_fault_request.py` and its own focused tests in the `gem5` repo, then pushed that phase to `stable`.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/run_sdc_differential.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/sdc_campaign.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_run_sdc_differential.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_sdc_campaign.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/tests/test_offline_to_campaign_integration.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)

### Phase 17: Kunpeng920 McPAT Decoupling
- **Status:** complete
- Actions taken:
  - Re-read `kunpeng920.md` and translated its stable topology/cache facts into a dedicated Kunpeng McPAT adapter at `mcpat/pypat/conversion/arm64_kunpeng920.py`.
  - Split the ARM64 McPAT conversion path into clearer responsibilities: `profiles.py` now selects and normalizes the Kunpeng config/model layer, `gem5_to_mcpat.py` applies a derived stats normalization pass, and the template consumes `stats.mcpat.*` values instead of old hard-coded counters.
  - Enriched `kunpeng920_profile.json` with Kunpeng topology fields (core count, clustering, die count, LLC total size, and conservative I/O defaults) while keeping the runtime path safe for SE-mode workloads by defaulting I/O duty/load to zero.
  - Reworked `template_arm64_kunpeng920.xml` so the system counts, private/shared cache topology, core micro-activity counters, cache/TLB counters, NoC traffic, and memory-controller traffic are all driven by normalized profile/stat data instead of baked-in constants.
  - Fixed a backend-path bug in `power_backends/mcpat_backend.py`, which had been inserting the McPAT executable path into `sys.path` rather than the `mcpat/` package root.
  - Added `mcpat/tests/test_arm64_kunpeng920_model.py` to lock down both model construction and generated XML contents, then re-ran focused McPAT and root orchestration tests.
  - Confirmed that the direct McPAT regression set passed with `PYTHONPATH=.`: 5 tests covering the new Kunpeng model, existing Kunpeng end-to-end conversion, and the normalized power backend; plus 10 additional root tests covering differential execution, campaign orchestration, and offline-to-campaign integration.
- Files created/modified:
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/pypat/conversion/arm64_kunpeng920.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/pypat/conversion/profiles.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/pypat/conversion/gem5_to_mcpat.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/gem5_mcpat_parser/kunpeng920_profile.json` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/gem5_mcpat_parser/template_arm64_kunpeng920.xml` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/mcpat/tests/test_arm64_kunpeng920_model.py` (created)
  - `/Users/wangxu/1-project/sdc-fuzzing/power_backends/mcpat_backend.py` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/task_plan.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/findings.md` (updated)
  - `/Users/wangxu/1-project/sdc-fuzzing/progress.md` (updated)
