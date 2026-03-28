# Findings & Decisions

## Requirements
- Build a technical方案 for ARMv8-A 64-bit SDC fuzzing, with Kunpeng 920 as a representative microarchitecture target.
- Deeply understand the current workspace instead of proposing a generic architecture.
- Reuse Microprobe-native abstractions where possible.
- Favor a lightweight differential-testing execution layer over heavyweight validation harnesses.
- Consider advanced planning/parallel-analysis techniques where helpful.

## Research Findings
- The workspace is a monorepo-style integration environment containing `microprobe`, `qemu`, `gem5`, `mcpat`, and `opendcdiag`.
- The repository already includes an `AGENTS.md` that proposes an ARM64/TaiShan-oriented SDC fuzzing architecture with offline static scoring plus online QEMU-vs-gem5 differential validation.
- Microprobe is explicitly pass- and policy-oriented, which aligns well with implementing ACE/IBR scoring as native passes and generation strategy as policy code.
- gem5 is present as full simulator source, making SE-mode integration and targeted ARM builds feasible in-tree.
- `microprobe/targets/arm64/policies/sdc_detect.py` already exists, so the ARM64 SDC direction is not greenfield in this repo.
- The existing `sdc_detect` policy looks like a draft rather than production-ready integration: it references `DefineDataSegmentPass` and `AllocateRegistersPass`, which need to be verified against the real pass inventory.
- `Benchmark.context` in `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/code/benchmark.py` is an execution `Context` object, not a generic dictionary. This means `benchmark.context['ace_score']` is not currently a native storage pattern.
- The wrapper abstraction in `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/code/wrapper.py` is suitable for a new lightweight differential wrapper because it already centralizes headers, global vars, main-loop structure, instruction wrapping, and reserved-register policy.
- `microprobe/sdc_fuzzing_generator.py` already implements an `InstructionPool` and `MutationEngine`, so there is an existing basis for category-aware mutation and weighted instruction sampling.
- The current ARM64 target branch is centered on `armv8-common-cortex-a53-aarch64_linux_gcc`; there is no Kunpeng 920 / TaiShan V110-specific target tuple yet.
- `microprobe/targets/arm64/uarch/armv8-common/microarchitecture.yaml` is a generic ARMv8 model, not a Kunpeng-calibrated OoO server-core model.
- ARM64 ISA property YAMLs already include SIMD, floating-point, pair load/store, and vector-memory instruction descriptions, which is enough to drive first-pass SDC-sensitive instruction filtering.
- `microprobe/src/microprobe/driver/genetic.py` is currently unusable as-is for Python 3 because it immediately raises `NotImplementedError` and documents the old pyevolve dependency as deprecated.
- `microprobe/targets/generic/tools/mp_seq.py` shows the standard policy invocation path: resolve wrapper, build `extra_arguments`, `find_policy(...)`, `policy.apply(...)`, `synthesize()`, then `save(...)`. A new offline generator tool can mirror this flow instead of inventing a new front-end.
- `gem5/tests/gem5/stats/configs/simple_binary_run.py` provides a minimal ARM SE-mode binary execution path with `SimpleBoard`, `SimpleProcessor`, and `set_se_binary_workload(...)`.
- `gem5/configs/deprecated/example/se.py` is still present for flexible syscall-emulation runs, but it is explicitly deprecated; the stdlib-style board setup is a cleaner basis for a new differential runner.
- The workspace does not appear to contain an existing transient fault-injection framework for gem5. Searches for `fault injection`-style hooks only surfaced unrelated FDP prefetch code.
- `mcpat/mcpat/README.md` shows the local McPAT fork supports decoupled initialization and consecutive `-trace` power recomputation, which is ideal for the online outer loop.
- `kunpeng920.md` provides a strong architecture note: Kunpeng 920 is based on TaiShan V110, a 4-wide OoO ARMv8.2-A server core with 128-bit NEON, dual FPU pipelines, 2 AGUs, 64 KB L1I/L1D, 512 KB private L2, and a large partitionable LLC. This favors stressing NEON/FMA-like vector math, pair load/store, long-latency memory streams, and cache-eviction-friendly access patterns.
- Runtime probing shows `find_policy(...)` succeeds for both `seq` and `sdc_detect`, so policy registration is wired into the workspace.
- Runtime probing also shows `import_definition('armv8-common-cortex-a53-aarch64_linux_gcc')` fails with `MicroprobeTargetDefinitionError` because the tuple parser expects exactly three `-`-separated parts. The existing ARM64 target naming is therefore not importable through the standard API in its current form.
- Runtime probing of wrappers reveals `get_wrapper('AsmWrapper')` fails because no such wrapper class is registered, and `get_wrapper('CWrapper')` triggers a module-name collision between the generic `wrappers/asm.py` and `targets/arm64/wrappers/asm.py`.
- `Instruction.sets()`, `Instruction.uses()`, and `Bbl.distance()` are real APIs in the current Microprobe core, so a native static ACE pass is feasible without invasive IR redesign.
- For IBR-like width scoring, the ARM64 register-type YAML already encodes `GPR64`, `SIMD128`, and related widths. A first implementation can score by destination/source register type size and memory operand length rather than by custom instruction annotations.
- `microprobe/src/microprobe/__init__.py` plus `microprobe/src/microprobe/utils/policy.py` / `microprobe/src/microprobe/code/__init__.py` confirm that policies, wrappers, and architecture data are discovered through `MICROPROBEDATA` / `MICROPROBEWRAPPERS` search roots. A clean implementation should stay inside these extension seams.
- The best place for a concrete differential wrapper is not `microprobe/src/microprobe/code/wrapper.py` but a new wrapper module built on top of `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/generic/wrappers/c.py`.
- The current ARM64 wrapper file name `asm.py` collides with the generic wrapper module of the same name during wrapper discovery. A new ARM64 wrapper should use a unique module filename.
- `microprobe/targets/generic/tools/mp_seq.py` is the right template for a new offline SDC generator CLI: choose wrapper, collect `extra_arguments`, resolve policy, `synthesize()`, then `save()`.
- The current ARM64 `seq` policy uses real pass names such as `SimpleBuildingBlockPass`, `SetInstructionTypeBySequencePass`, `SingleMemoryStreamPass`, and `DefaultRegisterAllocationPass`, while `sdc_detect.py` calls nonexistent `DefineDataSegmentPass` and `AllocateRegistersPass`. This suggests we should fork from `seq.py`, not from the current `sdc_detect.py`.
- The current target tuple parser in `microprobe/src/microprobe/target/__init__.py` hardcodes a three-part `<isa>-<uarch>-<env>` split, which explains why `armv8-common-cortex-a53-aarch64_linux_gcc` is not importable through the standard API.
- The generic `CWrapper` already provides `headers()`, `declare_global_var()`, `post_var()`, `start_main()`, and related scaffolding. A `BareMetalDiffWrapper` can be implemented as a focused subclass rather than a new wrapper stack from scratch.
- `gem5/src/python/gem5/components/boards/se_binary_workload.py` already exposes `set_se_binary_workload(..., stdout_file=..., stderr_file=...)`, which makes it easy to capture digest output from a wrapped binary in SE mode without modifying gem5 internals.
- For the online runner, `gem5/configs/example/arm/starter_se.py` is a better base than deprecated `gem5/configs/deprecated/example/se.py` when more realistic CPU/cache/memory topology is needed.
- QEMU user-mode documentation and the local AArch64 tree confirm that `qemu-aarch64` is the right ISA-level golden executor for static single-threaded ELF workloads.
- The bundled gem5-to-McPAT parser is x86-biased and not a low-friction fit for ARM/Kunpeng in its current form; McPAT should therefore be phase-2 feedback, not a hard prerequisite for the initial SDC loop.
- The in-repo `pypat` layer is a better default McPAT integration surface than the legacy `Gem5McPATParser_custom.py` script because it already centralizes template loading, config/stats substitution, and McPAT invocation.
- The current `pypat` converter had a latent parsing bug: it split every comma in config expressions, which broke new ARM profile expressions such as `max(config..., config...)`. This required a top-level comma splitter instead of a raw `str.split(",")`.
- The `pypat` launcher also had a path-resolution bug for the local `mcpat` binary: passing `mcpat` without a slash relied on `PATH` instead of the current directory.
- A new ARM64/Kunpeng920 profile and template-selection path can now be threaded through `pypat` and the legacy parser entrypoint.
- ARM64 McPAT XML generation is now working with a Kunpeng920-like profile, but end-to-end McPAT execution is still not stable on the local 2015 McPAT fork.
- The local McPAT fork rejects direct 7nm modeling and is more compatible with a coarser compatibility node. The current ARM64 profile therefore separates the real process node from the McPAT-compatible node.
- The bundled ARM processor description files themselves fail with `ERROR: no valid data array organizations found`, which means the remaining McPAT blocker is not specific to the new Kunpeng template alone.
- The local McPAT fork accepts Kunpeng-like ARM64 parameters when they are projected onto a Xeon-derived skeleton. The structural template compatibility was the blocker, not the ARM64 cache/core values themselves.
- The local `mcpat` binary writes `out.area` to stdout and `out.ptrace` as the per-block power artifact. Parsing stdout alone therefore loses the power signal needed by the SDC feedback loop.
- `pypat.conversion.convert.run(...)` now succeeds end-to-end for the `arm64-kunpeng920` profile and returns non-zero power values after switching parsing to `out.ptrace`.
- Microprobe wraps generated C benchmarks in the order `start_main -> post_var -> init -> body -> fini -> end_loop -> end_main`, so the ARM64 digest logic must live in `end_main()` and run before any context-reset epilogue.
- A practical ARM64 differential wrapper can preserve post-benchmark state by saving `sp/x29` at function entry, snapshotting GPR/SIMD/NZCV immediately after the generated instruction stream, and only then returning to normal C control flow.
- A lightweight top-level differential runner is now in place and can compile a static ELF, run `qemu-aarch64`, optionally run gem5, and append McPAT results into one JSON object.
- `mcpat/mcpat/gem5_mcpat_parser/README` references `run_mcpat.sh`, but that script is not present in the current tree. The parser logic exists, but the shell-level glue is incomplete.
- OpenDCDiag in this workspace does contain ARM64 SDC- and Kunpeng920-related code, but it is oriented toward host-side RAS/ECC observation and real-hardware diagnostics, not a lightweight simulator execution harness.
- `opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp` and `kunpeng920_ecc.cpp` are still valuable as design references: they show which CRC/checksum or ECC/RAS signals matter for real Kunpeng-class validation, even though they do not replace simulator fault injection.
- The local ARM64 microarchitecture YAML already models a 4-wide, dual-FPU, load/store separated ARMv8 core with 64 KB L1 and 512 KB L2, which is directionally aligned with Kunpeng 920 / TaiShan V110 stress priorities even if it is not a calibrated vendor model.
- The ARM64 SIMD/property YAMLs already include vector arithmetic, vector multiply-accumulate style ops, vector loads/stores, and `LDP/STP` forms. That is enough to seed a first-version SDC-sensitive instruction selector without inventing new ISA tags.
- The ARM64 register-type YAML already exposes `GPR64`, `GPR32`, and 128-bit `SIMD_FP`, so a practical IBR implementation can score by operand/register width immediately.
- The repository now already contains most of the Phase 1/2 scaffolding discussed in the design notes: `Benchmark.metadata`, `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`, `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`, `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`, `sdc_vault.py`, and `run_sdc_differential.py`.
- The actual ARM64 differential wrapper file on disk is `microprobe/targets/arm64/wrappers/baremetaldiff.py`, while older notes referenced `baremetal_diff.py`. The class name is still `BareMetalDiffWrapper`, so naming is functionally close but not fully normalized.
- `run_sdc_differential.py` is already wired for `compile -> qemu -> gem5 -> McPAT`, but it still defaults gem5 to `configs/deprecated/example/se.py` rather than a dedicated ARM Kunpeng-style SE config.
- `microprobe/targets/generic/tools/mp_sdc_offline_gen.py` already persists generated candidates into `sdc_vault.py`, so the remaining gap is not the existence of an offline generator but the reliability of the ARM64 target import path it depends on.
- The ARM64 `targets_tests.py` and `integration_tests.py` still mostly skip on failure instead of asserting the repaired target contract, so they are not yet strong regression guards for the desired end-to-end pipeline.
- `Arm64ISA` in `microprobe/targets/arm64/isa/armv8-common/isa.py` contains substantial helper logic, but the target import is still blocked by abstract ISA requirements and incomplete instruction-name coverage.
- A fresh runtime probe now shows `import_definition('armv8_common-armv8_common-aarch64_linux_gcc')` succeeds; the target-import blocker documented earlier has been resolved in the current tree, and the next bottlenecks have shifted to wrapper rendering, gem5 default wiring, and real fault injection.
- `BareMetalDiffWrapper` had a real render-time failure path: `CWrapper.start_main()` assumed every `pass_info` entry used the historic `"Pass - Detail"` format. The newer SDC passes emit plain strings, so `synth._wrap(bench)` used to raise `IndexError` until the generic wrapper was hardened.
- The repository now has a first-class `power_backends` package with a default `McPATBackend` and a deferred `OpenDCDiagBackend` interface, which cleanly separates power post-processing from the differential runner.
- The repository now also has a dedicated ARM64 gem5 SE config at `gem5/configs/example/arm/sdc_kunpeng920_se.py`, so the runner no longer has to default to deprecated `se.py`.
- The old ARM64 target unittest files remain in-tree, but the new executable guardrail is `microprobe/targets/arm64/tests/targets/test_target_contract.py`, which pytest discovers and which now covers canonical import, legacy alias import, wrapper registry, policy synthesis, and digest-wrapper rendering.
- `microprobe.utils.typeguard_decorator` treated `typeguard` as an implicit hard dependency whenever `unittest` was present in `sys.modules`. On this machine the package is absent, so tests only became runnable after making that dependency optional.
- The root repository now contains `sdc_scheduler.py`, a Python 3-native feedback scheduler that ranks seeds directly from `sdc_vault.py`, normalizes execution statuses from `run_sdc_differential.py`, and writes scheduler metadata back into the vault.
- The feedback scheduler deliberately gives explicit status priority to `SDC_FOUND` seeds over merely high-risk `PENDING` seeds. Pure fitness-by-formula was not enough because an unexecuted high-score seed could otherwise outrank a confirmed SDC-triggering seed.
- The root test layer now covers three previously unguarded surfaces: scheduler ranking/feedback persistence, runner digest/classification helpers, and backend normalization behavior through pure-Python tests.
- Full runtime proof of `offline -> compiler -> qemu -> gem5 -> mcpat` is still blocked on this machine because `aarch64-linux-gnu-gcc`, `qemu-aarch64`, and `gem5/build/ARM/gem5.opt` are not currently present.
- `sdc_scheduler.py` now has a shell-friendly CLI with `rank`, `plan`, and `record` subcommands, which means the vault feedback loop no longer requires embedding Python snippets just to rank or fold back results.
- `sdc_preflight.py` establishes the current runtime boundary in one place: on this machine the McPAT binary and gem5 config are present, while the ARM cross-compiler, `qemu-aarch64`, and built `gem5.opt` binary are still missing.
- The root repo now has a real outer-loop orchestrator in `sdc_campaign.py`. It can select ranked candidates from the vault, resolve testcase source files, execute the differential runner, emit per-testcase artifacts, and fold the result back through the scheduler.
- `run_sdc_differential.py` is no longer CLI-only; its new `run_differential(...)` API makes the execution chain testable and reusable from higher-level tooling without subprocess wrappers around the script itself.
- `sdc_materialize.py` closes the biggest remaining root-level dataflow gap: vault entries that only have `asm_content` can now be turned into digest-bearing ARM64 C sources, and the generated `source_path` is written back into testcase metadata.
- `sdc_campaign.py` now auto-materializes candidates when `source_path` is absent, so the outer loop can consume raw vault rows directly instead of requiring a separate manual source preparation step.
- The root test layer now includes a true cross-repo integration check: it imports the real `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`, generates a testcase with `BareMetalDiffWrapper`, stores it in the SQLite vault, and then drives that testcase through `sdc_campaign.py`.
- The root orchestration layer now exposes the gem5 fault request as structured CLI/API fields. `run_sdc_differential.py` and `sdc_campaign.py` both accept `fault_model`, `fault_target`, `fault_bit`, and `fault_tick`, so injector intent is no longer hidden inside opaque `--gem5-arg` strings.
- The current ARM64/Kunpeng McPAT path mixed flat profile constants, gem5-shape inference, and XML-template details in one place. A dedicated Kunpeng adapter layer is the cleanest upstreamable seam because it can normalize config/stat inputs before template rendering.
- `kunpeng920.md` is detailed enough to drive a first-class McPAT topology model: 64 cores, 4 cores per cluster, 16 clusters, 2 compute dies, 512 KiB private L2 per core, and a 64 MiB LLC best represented as 16 homogeneous 4 MiB slices inside McPAT.
- The previous ARM64 Kunpeng template still hard-coded many runtime counters (`ROB_*`, rename/window/register-file accesses, cache accesses, memory accesses, and duty cycles), which meant conversion output was only weakly connected to real gem5 stats.
- A dedicated `pypat/conversion/arm64_kunpeng920.py` adapter is sufficient to decouple Kunpeng support from the conversion core: it builds a structured McPAT model from config/profile data, flattens derived values back into the legacy profile contract for template compatibility, and synthesizes `stats.mcpat.*` counters that replace the previous constants.
- `power_backends/mcpat_backend.py` had a latent import-path bug: it inserted the local McPAT executable path into `sys.path` instead of the `mcpat/` Python package root. The pure-Python test path hid this, but a real backend invocation would eventually trip over it.
- `mcpat/` is a nested git repository. Root-level `git diff` does not show the actual Kunpeng converter/template changes unless the nested repo status is checked separately with `git -C mcpat ...`.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Treat `AGENTS.md` as a directional design artifact, not the final answer | The user asked for a deeper, codebase-specific方案 and mentioned Kunpeng 920 rather than only TaiShan |
| Use Microprobe as the control plane and QEMU/gem5 as execution backends | This preserves a clean separation between testcase synthesis and fault-observable execution |
| Plan around a metadata-channel gap in Microprobe | The requested `benchmark.context` dictionary pattern does not match the current `Context` implementation |
| Treat the existing ARM64 code as an in-progress local fork rather than stable upstream-grade support | Several files are 2026 additions with draft-style tests and incomplete integrations |
| Plan to replace or sidestep the deprecated genetic driver instead of subclassing it directly | The current Python 3 code path raises immediately and cannot serve as the real online GA engine |
| Split the roadmap into foundation repair and SDC feature delivery | Target importability and wrapper discovery must be fixed before the execution engine can become reliable |
| Use QEMU user-mode plus gem5 SE mode as the primary differential pair | The workspace already offers lightweight ARM SE entrypoints and QEMU user-mode is a natural ISA-level oracle |
| Treat McPAT and OpenDCDiag as secondary integrations | McPAT parser bias and OpenDCDiag’s host/RAS orientation make them poor foundations for the first executable loop |
| Build the first SDC policy by extending ARM64 `seq` rather than patching current `sdc_detect` in place | The existing sequence policy is structurally closer to a working generator path |
| Prefer a sidecar SQLite metadata model over forcing scores into `Context` | This avoids bending a register/memory state object into a generic dictionary |
| Use `pypat` template profiles as the default ARM64 McPAT extension point | This keeps ARM64/Kunpeng configuration in declarative files instead of another monolithic parser fork |
| Keep real-node and McPAT-compatible-node separate in the ARM64 profile | Kunpeng 920 is a 7nm part, but this McPAT fork only tolerates a coarser compatibility node |
| Base the ARM64 Kunpeng920 template on a Xeon-derived McPAT skeleton | This local McPAT fork rejects the bundled ARM templates, but the Xeon skeleton remains compatible after ARM/Kunpeng retargeting |
| Parse power from `out.ptrace` rather than stdout | The local McPAT executable prints area vectors to stdout and power vectors to `out.ptrace` |
| Put the ARM64 digest logic in a dedicated `BareMetalDiffWrapper` subclass | The generic `CWrapper` epilogue restores target context too late for SDC capture and does not preserve the needed architectural snapshot semantics |
| The default end-to-end方案 should treat existing scaffolding as partial implementation, not future intent | The current tree has enough material to avoid re-planning from scratch, but not enough to claim the pipeline is production-ready without target, gem5, and validation repairs |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Planning files were absent in the project root | Created `task_plan.md`, `findings.md`, and `progress.md` to track multi-step analysis |
| Broad `rg` searches produced noisy results in very large vendored trees | Narrowed subsequent searches to specific modules and config entrypoints |
| ARM64 target import failed during runtime probing | Treated this as a design constraint and evidence that the target-definition layer needs repair before implementation phases can fully execute |
| Wrapper discovery hit a duplicate module-name conflict on `asm.py` | Recorded this as a concrete integration bug that argues for a new uniquely named ARM64 wrapper module |
| Existing ARM64 `sdc_detect` policy references pass classes absent from the current tree | Treated this as evidence that the file is a draft and should not be used as the main implementation base |
| McPAT parser README references a missing shell entrypoint | Treated the parser as reusable but the orchestration script as missing glue work for later phases |
| ARM64 McPAT runs still fail inside the local McPAT binary | Resolved by moving the ARM64 template onto a Xeon-derived skeleton and adapting the backend to consume `out.ptrace` |
| ARM64 ISA import still fails after fixing operand constants and microarchitecture scaffolding | The remaining blocker is now clearly in `targets/arm64/isa/armv8-common/isa.py`: the ISA class is still abstract and some helpers reference undefined instruction names |
| ARM64 `instruction_props` currently contains extra instruction definitions rather than property files | Added a compatibility shim in the generic instruction importer so these sidecar YAMLs can be imported as instruction-definition extensions, but the directory semantics still need a follow-up cleanup |
| The new `BareMetalDiffWrapper` wraps arbitrary benchmark instructions in inline asm blocks without explicit inputs, outputs, or clobber lists | This leaves the surrounding C compiler free to make invalid ABI/register assumptions around the benchmark body, which is now the highest-risk correctness issue in the execution path |
| Prior progress notes and the wrapper directory disagreed about the exact wrapper filename | Re-read the directory and aligned the new documentation to the actual file layout so the plan does not point future work at a nonexistent path |
| The generic C wrapper assumed every pass-info message contained a `-` separator and crashed on newer SDC pass metadata | Hardened `microprobe/targets/generic/wrappers/c.py` so wrapper rendering tolerates both legacy and plain-string pass-info formats |
| pytest could not import Microprobe in this environment because `typeguard` is not installed | Made `typeguard` optional in `microprobe/src/microprobe/utils/typeguard_decorator.py` so tests fall back cleanly instead of failing during import |
| A purely formula-based scheduler allowed high-risk pending seeds to outrank confirmed SDC hits | Added explicit status priority in `sdc_scheduler.py` so the closed loop preserves empirically successful seeds before exploring additional pending work |
| The operator path still lacked a first-class shell entrypoint for scheduler actions and environment readiness checks | Added `sdc_scheduler.py` subcommands and `sdc_preflight.py` so the runtime harness can validate prerequisites and update the vault without ad-hoc helper scripts |
| The outer loop still required ad-hoc glue between candidate selection, execution, and vault feedback | Added `sdc_campaign.py` plus a reusable `run_differential(...)` API so the rank -> execute -> record workflow is now a first-class root-level interface |
| The outer loop still could not execute raw vault entries because they only persisted assembly text | Added `sdc_materialize.py` and campaign-side auto-materialization so the vault can now feed the differential runner without a manually curated source file per testcase |
| The root regression suite still lacked proof that cross-repo artifacts line up across the intended boundaries | Added `tests/test_offline_to_campaign_integration.py` so a real `microprobe`-generated testcase is now validated through the root vault and campaign interfaces |
| The root runner and campaign still treated fault-injection intent as an untyped gem5 passthrough | Added first-class fault arguments to the root APIs and tests that verify those fields reach the gem5 invocation layer unchanged |
| The ARM64 Kunpeng McPAT converter still relied on hard-coded XML stats and mixed-profile logic | Added a dedicated `arm64_kunpeng920.py` normalization layer, switched the template to derived `stats.mcpat.*` counters, and covered both model-building and XML generation with new regression tests |
| Root-level `git diff` appeared to miss the McPAT-side implementation changes | Confirmed that `mcpat/` is a nested git repository and checked/report the nested repo status separately from the root workspace |

## Resources
- `/Users/wangxu/1-project/sdc-fuzzing/AGENTS.md`
- `/Users/wangxu/1-project/sdc-fuzzing/microprobe/README.md`
- `/Users/wangxu/1-project/sdc-fuzzing/gem5/README.md`
- `/Users/wangxu/1-project/sdc-fuzzing/microprobe/sdc_fuzzing_generator.py`
- `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_detect.py`
- `/Users/wangxu/1-project/sdc-fuzzing/gem5/tests/gem5/stats/configs/simple_binary_run.py`
- `/Users/wangxu/1-project/sdc-fuzzing/mcpat/mcpat/README.md`
- `/Users/wangxu/1-project/sdc-fuzzing/kunpeng920.md`
- `/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/starter_se.py`
- `/Users/wangxu/1-project/sdc-fuzzing/gem5/src/python/gem5/components/boards/se_binary_workload.py`
- `/Users/wangxu/1-project/sdc-fuzzing/qemu/docs/user/main.rst`
- `/Users/wangxu/1-project/sdc-fuzzing/opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp`

## Microprobe Architecture Deep Dive (Phase 18)

### Core Architecture Components
- **Target System**: The `Target` class in `microprobe/src/microprobe/target/__init__.py` is the facade that combines ISA, Microarchitecture, and Environment. It provides a unified API for querying target properties.
- **ISA Layer**: `GenericISA` in `microprobe/src/microprobe/target/isa/__init__.py` defines the abstract interface for instruction set architectures. Key methods include `set_register()`, `load()`, `store_integer()`, `branch_unconditional_relative()`, etc.
- **Microarchitecture Layer**: `GenericCPUMicroarchitecture` provides cache hierarchy and functional unit modeling.
- **Environment Layer**: Defines execution context (baremetal, Linux userspace, etc.) and reserved registers.

### ARM64 ISA Implementation
- **ISA Class**: `Arm64ISA` in `targets/arm64/isa/armv8-common/isa.py` extends `GenericISA` with ARM64-specific implementations.
- **Register Files**:
  - GPR64: X0-X30, XZR (zero register), SP (stack pointer)
  - GPR32: W0-W30, WZR (32-bit view)
  - SIMD_FP: V0-V31 (128-bit), D0-D31 (64-bit view), S0-S31 (32-bit view)
  - Special: NZCV (condition flags), FPCR, FPSR, system registers
- **Instruction Formats**: Defined in `instruction_format.yaml`:
  - `ADD_SUB_IMM`: Add/Subtract immediate
  - `ADD_SUB_REG`: Add/Subtract shifted register
  - `MOVE_WIDE`: MOVZ/MOVK/MOVN
  - `LOAD_STORE_IMM`: Load/Store with immediate offset
  - `SIMD_DP_*`: SIMD data processing formats

### ARM64 Instruction Coverage Analysis
- **Currently Implemented**: ~100+ instruction variants covering:
  - Data processing (ADD, SUB, MUL, DIV, shifts, logical ops)
  - Load/Store (LDR, STR, LDP, STP)
  - Branch (B, BL, RET, conditional branches)
  - SIMD/FP operations (vector arithmetic, FMA)
- **SDC-Sensitive Instructions** (identified in `SDCSensitiveAnalyzer`):
  - FMA: FMADD, FMSUB, FNMADD, FNMSUB
  - Pair Memory: LDP, STP (64-bit variants)
  - LSE Atomics: CAS, LDADD, LDXR/STXR, LDAXR/STLXR

### BareMetalDiffWrapper Architecture
- **Purpose**: Generate ARM64 C code that captures architectural state after benchmark execution.
- **State Capture**: Saves/restores X19-X30, SP, V8-V15 across benchmark body.
- **Digest Computation**: Hashes GPRs (X0-X30, excluding X18), NZCV, SIMD registers (V0-V31), and memory variables.
- **Output Format**: Single `SDC_DIGEST=<hex>` line for differential testing.

### Static SDC Analysis Passes
- **StaticACECalculatorPass**: Estimates register exposure by computing def-to-last-use instruction distance.
- **StaticIBRCoveragePass**: Measures information-bit richness from wide register (64/128-bit) and memory usage.
- **Kunpeng920MemoryPressurePass**: Scores pair-memory, atomic, and cache-pressure patterns.
- **CapstoneValidationPass**: Optional disassembly validation using Capstone library.

### Kunpeng 920 Microarchitecture Insights (from kunpeng920.md)
- **Core**: TaiShan V110, 4-wide OoO, ARMv8.2-A
- **Cache Hierarchy**:
  - L1I/D: 64KB each, 4-way, 64B line
  - L2: 512KB private per core
  - L3: 64MB shared, partitioned per 4-core cluster
- **Execution Units**:
  - 3x ALU (simple/add/bitwise)
  - 1x complex (multiply/divide)
  - 2x FPU (FP32 FMA dual-issue, FP64 quarter-rate)
  - 2x AGU (load/store)
- **SDC Stress Priorities**:
  - NEON/FMA operations (128-bit data paths)
  - Pair load/store (LDP/STP) for cache pressure
  - LSE atomics for synchronization stress
  - Long-latency memory streams (≥8KB stride)

### Identified Gaps
1. **Instruction Coverage**: Current ARM64 ISA definition covers core instructions but lacks:
   - Full NEON instruction set (only subset implemented)
   - SVE (Scalable Vector Extension) instructions
   - Crypto extensions (SHA, AES, PMULL)
   - Full LSE atomic instruction set
2. **Microarchitecture Model**: `Arm64Microarchitecture` is a thin wrapper; no Kunpeng-specific pipeline model.
3. **Fault Injection**: No native gem5 fault injection framework; requires external scripts.
4. **Test Coverage**: ARM64 tests focus on import/synthesis, not on instruction encoding correctness.

## Visual/Browser Findings
- No browser-based or image-based findings captured yet.

## ARM64 Instruction Coverage Gap Analysis (Phase 18)

### Current Implementation Status
- **Core instruction.yaml**: 57 instruction definitions covering basic data processing, load/store, branch, and logical operations
- **Extension instruction_props/**: 109 additional instructions across:
  - `simd.yaml`: ~45 NEON/SIMD instructions (vector arithmetic, logical, shift, load/store, compare, duplicate)
  - `floating.yaml`: ~35 floating-point instructions (FADD, FSUB, FMUL, FDIV, FCMP, FCVT, SCVTF, UCVTF)
  - `atomic.yaml`: ~25 LSE atomic instructions (LDAXR, STLXR, LDADD, CAS, SWP variants)
  - `system.yaml`: System instructions
- **Total implemented**: ~166 instruction variants

### Reference Documentation Coverage
- **doc/armv8-isa/**: 387 instruction manual files
- **Instruction categories**:
  - Load/Store: 124 files (largest category)
  - Other (miscellaneous): 81 files
  - Arithmetic: 33 files
  - Bit Manipulation: 26 files
  - Logical: 23 files
  - Barrier/Hint: 17 files
  - System: 16 files
  - Branch: 13 files
  - Pointer Authentication: 12 files
  - Compare: 11 files
  - Conditional Select: 8 files
  - Atomic: 7 files
  - PC-Relative: 3 files
  - Cryptographic: 2 files
  - Count: 2 files

### Identified Gaps

#### 1. Missing FMA Instructions (Critical for SDC)
Current implementation lacks scalar FMA instructions:
- **FMADD**: Fused Multiply-Add
- **FMSUB**: Fused Multiply-Subtract
- **FNMADD**: Fused Negate Multiply-Add
- **FNMSUB**: Fused Negate Multiply-Subtract

These are **SDC-sensitive** because they perform multiple operations in a single instruction, increasing the window for silent errors.

#### 2. Incomplete NEON Coverage
Missing key NEON instruction families:
- **FMLA/FMLS**: Vector Fused Multiply-Accumulate/Subtract
- **FMLAL/FMLSL**: Mixed-precision FMA (FP16→FP32)
- **SABD/UABD**: Absolute Difference
- **SADALP/UADALP**: Add and Accumulate Pairwise
- **EXT**: Extract vector from pair
- **TBL/TBX**: Table lookup
- **ZIP/UZP/TRN**: Vector permutation
- **REV64/REV32/REV16**: Vector reverse

#### 3. Missing Crypto Extensions
No support for cryptographic instructions:
- **AES**: AESE, AESD, AESMC, AESIMC
- **SHA**: SHA256H, SHA256SU0, SHA256SU1, SHA512H, etc.
- **PMULL**: Polynomial Multiply
- **CRC32**: CRC32B, CRC32H, CRC32W, CRC32X

#### 4. Incomplete LSE Atomic Coverage
Missing variants:
- 8/16/32-bit atomic operations (only 64-bit implemented)
- **LDCLR/LDCLRA/LDCLRAL**: Atomic bit clear
- **LDEOR/LDEORA/LDEORAL**: Atomic exclusive OR
- **LDSET/LDSETA/LDSETAL**: Atomic bit set
- **LDSMAX/LDSMAXA/LDSMAXAL**: Atomic signed maximum
- **LDSMIN/LDSMINA/LDSMINAL**: Atomic signed minimum
- **LDUMAX/LDUMAXA/LDUMAXAL**: Atomic unsigned maximum
- **LDUMIN/LDUMINA/LDUMINAL**: Atomic unsigned minimum

#### 5. Missing SVE Support
No Scalable Vector Extension support:
- SVE is critical for modern ARM servers (Neoverse N1/V1)
- Enables vector-length-agnostic programming
- Includes gather/scatter, predicated operations

#### 6. Missing Pointer Authentication
No PAUTH support:
- **PACIA/PACIB/PACDA/PACDB**: Pointer authentication codes
- **AUTIA/AUTIB/AUTDA/AUTDB**: Authenticate pointers
- **BTI**: Branch Target Identification

### Enhancement Recommendations

#### Priority 1: SDC-Critical Instructions
1. **Add scalar FMA instructions** (FMADD, FMSUB, FNMADD, FNMSUB)
   - Format: `FP_DP_3REG` (3-register floating-point)
   - Critical for TaiShan V110 dual FPU pipelines

2. **Complete LSE atomic coverage**
   - Add all size variants (8/16/32/64-bit)
   - Add missing operations (LDCLR, LDEOR, LDSET, LDSMAX, LDSMIN, LDUMAX, LDUMIN)

3. **Add vector FMA** (FMLA, FMLS)
   - Critical for NEON-based SDC detection

#### Priority 2: Kunpeng 920 Optimization
1. **Pair memory operations**: Already implemented (LDP/STP)
2. **Cache prefetch**: Add PRFM variants
3. **Memory tagging**: Add LDG/STG/IRG instructions (MTE extension)

#### Priority 3: Extended Coverage
1. **NEON permutation**: ZIP, UZP, TRN, EXT
2. **Crypto extensions**: AES, SHA, PMULL (for security-focused SDC testing)
3. **SVE basics**: LD1B, ST1B, ADD, SUB (for future-proofing)

### Microarchitecture Model Gaps

#### Current State
- `Arm64Microarchitecture` is a thin wrapper around generic CPU model
- No TaiShan V110-specific pipeline modeling
- Cache hierarchy is configurable but not Kunpeng-specific

#### Recommended Enhancements
1. **Pipeline Model**: Add TaiShan V110 execution port mapping
   - 3x ALU (simple/add/bitwise)
   - 1x complex (multiply/divide)
   - 2x FPU (FP32 FMA dual-issue, FP64 quarter-rate)
   - 2x AGU (load/store)

2. **Cache Model**: Add Kunpeng 920 cache topology
   - L1I/D: 64KB each, 4-way, 64B line
   - L2: 512KB private per core
   - L3: 64MB shared, partitioned per 4-core cluster

3. **Memory Pressure Scoring**: Already implemented in `Kunpeng920MemoryPressurePass`

### Test Coverage Recommendations
1. **Instruction encoding validation**: Add tests for each instruction format
2. **ABI compliance**: Verify wrapper preserves callee-saved registers
3. **Digest consistency**: Test hash stability across runs
4. **Fault injection**: Add gem5 fault injection test harness

## Phase 19: ARM64 SDC-Critical Instruction Enhancement

### Implementation Summary

#### 1. Scalar FMA Instructions (floating.yaml)
Added 8 scalar FMA instruction variants:
- **FMADD_D_V0 / FMADD_S_V0**: Fused Multiply-Add (Double/Single precision)
- **FMSUB_D_V0 / FMSUB_S_V0**: Fused Multiply-Subtract (Double/Single precision)
- **FNMADD_D_V0 / FNMADD_S_V0**: Fused Negate Multiply-Add (Double/Single precision)
- **FNMSUB_D_V0 / FNMSUB_S_V0**: Fused Negate Multiply-Subtract (Double/Single precision)

#### 2. Vector FMA Instructions (simd.yaml)
Added 6 vector FMA instruction variants:
- **FMLA_V_2S_V0 / FMLA_V_4S_V0 / FMLA_V_2D_V0**: Vector FMA (2xSingle, 4xSingle, 2xDouble)
- **FMLS_V_2S_V0 / FMLS_V_4S_V0 / FMLS_V_2D_V0**: Vector FMS (2xSingle, 4xSingle, 2xDouble)

#### 3. LSE Atomic Instructions (atomic.yaml)
Added missing LSE operations:
- **LDSMAX_X_V0**: Atomic Signed Maximum
- **LDSMIN_X_V0**: Atomic Signed Minimum
- **LDUMAX_X_V0**: Atomic Unsigned Maximum
- **LDUMIN_X_V0**: Atomic Unsigned Minimum

#### 4. Instruction Format (instruction_format.yaml)
Added `FP_DP_3REG` format for 3-register floating-point operations:
- Fields: type, o1, o0, Vm, 0_5, Va, Vn, Vd
- Assembly: "OPC Vd, Vn, Vm, Va"

#### 5. Instruction Fields (instruction_field.yaml)
Added missing field definitions:
- **o0**: FMA opcode bit 0 (1-bit)
- **o1**: FMA opcode bit 1 (1-bit)
- **Va**: Accumulator SIMD Register (5-bit, SIMD_FP_regs operand)

#### 6. SDCSensitiveAnalyzer Update
Extended `_FMA_MNEMONICS` set to include:
- FMADD, FMSUB, FNMADD, FNMSUB (scalar FMA)
- FMLA, FMLS (vector FMA)

### Files Modified
| File | Changes |
|------|---------|
| `instruction_format.yaml` | Added FP_DP_3REG format |
| `instruction_field.yaml` | Added o0, o1, Va fields |
| `floating.yaml` | Updated FMA instructions to use FP_DP_3REG |
| `simd.yaml` | Added vector FMA instructions |
| `atomic.yaml` | Added LDSMAX, LDSMIN, LDUMAX, LDUMIN |
| `sdc_fuzzing_policy.py` | Extended FMA mnemonic set |

### Test Results
All 16 tests passed:
- 7 ARM64 target contract tests
- 4 scheduler tests
- 4 campaign tests
- 1 offline-to-campaign integration test

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
