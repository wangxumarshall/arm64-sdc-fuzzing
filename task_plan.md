# Task Plan: ARMv8 SDC Fuzzing Technical Design

## Goal
Design a codebase-grounded SDC fuzzing technical方案 for ARMv8-A 64-bit microarchitectures such as Kunpeng 920 by deeply analyzing the current workspace and mapping the design onto real Microprobe, QEMU, gem5, and McPAT extension points.

## Current Phase
Phase 11 complete

## Phases

### Phase 1: Workspace Discovery
- [x] Understand user intent
- [x] Identify top-level constraints and repository composition
- [x] Record initial findings in findings.md
- **Status:** complete

### Phase 2: Microprobe Extension Mapping
- [x] Locate policy, pass, wrapper, and driver extension points
- [x] Inspect ARM64 target support and tool entrypoints
- [x] Record feasible integration seams and gaps
- **Status:** complete

### Phase 3: Execution Stack Mapping
- [x] Inspect QEMU/gem5/McPAT integration boundaries
- [x] Determine practical differential-testing workflow
- [x] Document risks, assumptions, and required glue code
- **Status:** complete

### Phase 4: Architecture Design
- [x] Draft the offline/online SDC fuzzing architecture
- [x] Define data model, scoring pipeline, and execution flow
- [x] Tailor the design to Kunpeng 920 style ARMv8-A behavior
- **Status:** complete

### Phase 5: Delivery
- [x] Summarize the recommended technical方案
- [x] Provide phased implementation roadmap grounded in the repo
- [x] Call out open questions and validation steps
- **Status:** complete

### Phase 6: Foundation Implementation
- [x] Add Microprobe benchmark metadata channel and ARM64 SDC analysis scaffolding
- [x] Add ARM64 SDC fuzzing policy and wrapper discovery fixes
- [x] Add McPAT ARM64/Kunpeng920 profile plumbing and template selection
- [x] Stabilize end-to-end McPAT execution for the ARM64 template on this local McPAT fork
- **Status:** complete

### Phase 7: Differential Execution Bring-Up
- [x] Add an ARM64 differential wrapper skeleton that snapshots architectural state and prints a digest
- [x] Add a lightweight `run_sdc_differential.py` executor skeleton for compile/QEMU/gem5/McPAT chaining
- [ ] Connect the new wrapper into a generated benchmark and validate a full QEMU digest run
- **Status:** in progress

### Phase 8: Systematic Code Review
- [x] Re-validate ARM64 target import after the latest compatibility fixes
- [x] Review the new ARM64/McPAT/SDC code for functional gaps, bugs, logic flaws, and security issues
- [x] Prepare a severity-ordered findings list with file/line references
- **Status:** complete

### Phase 9: End-to-End Documentation
- [x] Reconcile the prior design discussion with the repository's current on-disk state
- [x] Write a repository-grounded end-to-end ARM64 SDC fuzzing plan covering Microprobe, QEMU, gem5, McPAT, and deferred OpenDCDiag integration
- [x] Capture the current blockers, required file-level work, and acceptance criteria in a durable project document
- **Status:** complete

### Phase 10: Execution Path Hardening
- [x] Convert ARM64 target/wrapper assumptions into executable pytest coverage
- [x] Fix the C wrapper path so `BareMetalDiffWrapper` can render a digest-bearing source file
- [x] Add a first-class `McPATBackend` and a dedicated ARM64 SE gem5 config, then point the runner at them by default
- **Status:** complete

### Phase 11: Feedback Scheduling
- [x] Add a Python 3-native feedback scheduler for ranking seeds and folding execution results back into the vault
- [x] Add root-level tests for scheduler math, runner classification helpers, and backend normalization
- [x] Re-run cross-phase pytest coverage to verify the new scheduler layer does not regress the ARM64 contract path
- **Status:** complete

## Key Questions
1. Which existing Microprobe abstractions can host SDC-sensitive generation, static scoring, and GA feedback with minimal reinvention?
2. How should the offline vault, QEMU golden run, gem5 fault-injection run, and McPAT power feedback connect in this specific workspace?
3. What ARMv8-A/Kunpeng-specific stress patterns are most worth prioritizing in the first version?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use file-based planning for this task | The request is multi-stage research/design and will require many tool calls across several subprojects |
| Prioritize codebase mapping before proposing architecture details | The user explicitly asked for a deep understanding of the current directory's source code |
| Keep the design centered on Microprobe-native extensions and a lightweight executor | This matches the repository instructions and avoids heavy harness complexity |
| Treat bootstrap/foundation repair as part of the roadmap | ARM64 policy code exists, but target import and wrapper discovery are not yet coherent enough for end-to-end execution |
| Use a sidecar metadata channel instead of overloading `Benchmark.context` | The current `Context` type models execution state, not arbitrary score storage |
| Base the online differential loop on QEMU user-mode plus gem5 SE-mode | Those are the lightest viable execution seams already present in the workspace |
| Use `pypat` as the default McPAT entrypoint and keep `Gem5McPATParser_custom.py` as a thin compatibility wrapper | The newer `pypat` layer is simpler to extend and now supports template-profile selection |
| Use a Xeon-derived McPAT skeleton for the ARM64 Kunpeng920 template | The bundled ARM templates are rejected by this local McPAT/Cacti fork, while the Xeon skeleton accepts the Kunpeng-like cache/core parameters once retargeted |
| Treat `out.ptrace` as the authoritative power artifact for this McPAT fork | The local binary writes area to stdout and emits the per-block power trace to `out.ptrace`, so backend parsing must consume the trace file rather than stdout |
| Treat the current ARM64 ISA directory as a compatibility layer under repair rather than a complete target | The local ARM64 ISA data mixes partial format descriptions, sidecar instruction-definition YAMLs, and draft ISA helpers, so the review must account for both code and data-model debt |
| Ground the new方案 in the current disk state rather than only the older progress notes | The wrapper path and a few implementation details have drifted, so the final design document must reflect what is actually present in the workspace today |
| Prefer live pytest coverage over dormant legacy unittest files for ARM64 target hardening | The older ARM64 tests were mostly skip-based and not discovered in normal pytest runs, while new contract tests now exercise the repaired import and wrapper paths directly |
| Implement the feedback loop as a root-level Python module instead of reviving the deprecated Microprobe GA driver | The repository already persists enough testcase/runtime data in SQLite to rank and recycle seeds without depending on the abandoned `pyevolve` path |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| McPAT ARM64 template execution still fails on this local fork | 1 | Resolved by rebuilding the ARM64 template on a Xeon-derived skeleton and parsing `out.ptrace` instead of stdout area output |
| ARM64 target import still fails after tuple/uarch repair | 2 | Narrowed the remaining blocker to `targets/arm64/isa/armv8-common/isa.py`: the ISA class is still abstract and helper methods reference undefined instruction names |
| Prior notes and the current tree disagreed on the ARM64 differential wrapper filename | 3 | Re-read the wrapper directory and anchored the new end-to-end design doc to the real file set now present on disk (`baremetaldiff.py`, not `baremetal_diff.py`) |
| pytest could not import Microprobe because `typeguard` is optional but the testsuite decorator treated it as mandatory | 4 | Softened `typeguard_decorator.py` so runtime type checking only activates when `typeguard` is actually installed |
| Full end-to-end runtime validation is still blocked by missing local toolchain binaries | 5 | Confirmed that `aarch64-linux-gnu-gcc`, `qemu-aarch64`, and `gem5/build/ARM/gem5.opt` are not currently available on this machine, so this phase focused on logic that can be fully verified in pure Python |

## Notes
- Re-read this plan before major decisions.
- Keep findings grounded in actual repository paths and extension seams.
- Prefer lightweight integration over introducing new heavyweight frameworks.
