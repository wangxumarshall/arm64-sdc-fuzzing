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

## Visual/Browser Findings
- No browser-based or image-based findings captured yet.

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
