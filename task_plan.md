# Task Plan: End-to-End SDC-Agent Delivery

## Goal
Drive the monorepo's SDC-Agent control plane and supporting source code to match the completed architecture and delivery requirements defined in `docs/spec.md` and `docs/plan.md`, and verify the result end to end.

## Current Phase
Phase 5

## Phases
### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints and requirements
- [x] Document findings in `findings.md`
- **Status:** complete

### Phase 2: Gap Analysis & Technical Plan
- [x] Inspect current control-plane modules and tests
- [x] Map implemented behavior to spec/plan phases
- [x] Define the highest-impact missing work
- **Status:** complete

### Phase 3: Implementation
- [x] Implement missing source changes
- [x] Keep database, orchestration, and CLI paths coherent
- [x] Add or update tests for new behavior
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Run targeted unit and integration tests
- [x] Run broader regression coverage where feasible
- [x] Fix issues uncovered by verification
- **Status:** complete

### Phase 5: Delivery
- [ ] Review modified files and outcomes
- [ ] Confirm alignment with `docs/spec.md` and `docs/plan.md`
- [ ] Deliver concise completion summary to user
- **Status:** in_progress

### Phase 6: ARM64 Full-Catalog Generation
- [x] Build an official-XML-backed ARM64/A64 catalog
- [x] Expose catalog-driven generation profiles and audit coverage
- [x] Verify full-catalog generation and ARM64 regressions
- **Status:** complete

## Key Questions
1. Which capabilities described as "进行中" or partially complete in `docs/plan.md` are still missing in the current control plane?
2. Are there failing or missing tests that reveal the true unfinished edges of Phases 3-6?
3. What is the minimum but sufficient code change set needed to produce a real end-to-end usable path instead of placeholders?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use `docs/spec.md` and `docs/plan.md` as the source of truth for acceptance | The user explicitly asked to build against those two documents end to end |
| Start with control-plane code and tests before touching large vendor subtrees | The spec and plan identify the control plane as the integration bus and most likely source of missing glue |
| Track work in project-root planning files | The task is large and will require sustained multi-phase implementation and verification |
| Treat environment reproducibility as part of the deliverable | End-to-end validation should not depend on unstated interpreter quirks |
| Prioritize Phase 3 feedback-loop upgrades over speculative new subsystems | The largest code-level gap against the plan was missing power/diversity-aware evolution guidance |
| Fix direct `pytest` from repo root instead of documenting a special invocation | Repo-local testability is a source-level quality issue, not just a workflow note |
| Implement full A64 coverage through an XML-backed catalog plus assembly generation before attempting full bitfield-level `instruction.yaml` expansion | This delivers 100% catalog coverage and legal sequence generation without destabilizing the existing executable subset |
| Keep `SIM_SAFE` / `HW_AGGRESSIVE` on the existing synthesizer path and add new catalog-driven profiles for `ALL_GENERATABLE`, `EXECUTABLE_SAFE`, and `KUNPENG920_STRESS` | The repo already has a stable executable subset; full-catalog generation has different constraints and should not regress the current differential flow |
| Use Python-side gem5 `physProxy` for the first real `memory_bit_flip` injector path | This closes a meaningful Phase 5 gap without waiting for a deeper C++ memory injector |
| Add template/PCFG generation as an opt-in strategy layered over the current generator | This matches the Phase 7 contract without destabilizing the existing baseline path |
| Treat `mem:0x...` fault targets as guest virtual addresses and reject malformed CPU prefixes early | This avoids silently corrupting the wrong memory in SE mode and prevents wasted campaign runs |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `pytest` could not import `sdc_agent` from repo root | 1 | Added `tests/conftest.py` to place the repo root on `sys.path` during test collection |
| `/usr/bin/python3 -m pytest` lacked `pytest` | 1 | Use the available Conda Python for verification and consider codifying it in repo config |
| Initial `neon_fma_heavy` template used `LD1`/`ST1`, which did not synthesize cleanly through the current wrapper path | 1 | Tightened the first template version to aggressive mnemonics that the current synthesizer path can render reliably |

## Notes
- Re-read `docs/spec.md`, `docs/plan.md`, and this plan before major implementation choices.
- Treat tests as the quickest signal for uncovered gaps between docs and code.
- Avoid destructive git actions; preserve the clean worktree unless edits are needed for the task.
- The ARM64 target now exposes a catalog helper backed by `arm_a64_catalog.json`; this is the new source of truth for full A64 generation coverage.
- The remaining blockers that cannot be fully closed on this machine are real hardware deployment/validation and a true external LLM-backed mutation advisor.
