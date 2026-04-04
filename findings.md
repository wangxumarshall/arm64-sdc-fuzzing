# Findings & Decisions

## Requirements
- Use `docs/spec.md` and `docs/plan.md` as the authoritative definition of project scope and completion criteria.
- Continue working until the end-to-end source implementation is complete, rather than stopping at analysis.
- Preserve the monorepo control-plane architecture centered on `sdc_agent/*`, `tools/*`, Vault persistence, inner loop, outer loop, and hardware lane.
- Ensure the delivered source aligns with the three-loop system in the spec: high-frequency inner loop, low-frequency outer loop, and hardware validation lane.

## Research Findings
- The repository is already a large monorepo containing `microprobe`, `qemu`, `gem5`, `mcpat`, `opendcdiag`, `sdc_agent`, `tools`, and `tests`.
- `docs/spec.md` describes a completed architecture where the database is the system bus and where inner loop, outer loop, and hardware lane all write back structured records.
- `docs/plan.md` states that Phase 2 and Phase 4 are largely implemented, while Phase 3, Phase 5, Phase 6, and Phase 7 still contain real gaps.
- The plan specifically calls out partially completed work in power-driven evolution, gem5 real injector coverage, richer hardware ingest, and broader intelligent generation.
- The current git worktree is clean, which lowers merge-risk for substantial edits.
- `docs/state.md` confirms that Phase 2, Phase 4, and a bootstrap version of Phase 6 are already wired through the control plane, and that the main remaining risks are broader injector coverage, hardware validation depth, and deployment maturity.
- The repository has no `pyproject.toml`, `pytest.ini`, `setup.py`, or `setup.cfg`, so Python import/test behavior is not codified at the repo level.
- Running plain `pytest` from the repo root fails collection with `ModuleNotFoundError: sdc_agent`, which exposes a reproducibility gap in local verification.
- The machine has multiple Python interpreters; the usable testing stack appears to live under `/Users/wangxu/anaconda3/bin/python` and `/Users/wangxu/anaconda3/bin/pytest`, not `/usr/bin/python3`.
- The most actionable gap against `docs/plan.md` was Phase 3: the scheduler exposed `fitness` and outer-loop signals, but did not yet model a separate `inner_value_score` or feed diversity/profile-aware breakdowns back into evolution.
- `microprobe/src/microprobe/driver/genetic.py` already had a Python 3 evolution path, but partner selection was simplistic, profile-aware fallback instruction recovery was incomplete, and lineage metadata did not explain why a parent/partner pair was chosen.
- A small repo-local test bootstrap is enough to make direct `pytest` from the root work again without changing user shell state.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Use planning files in the project root | This is a long-running, multi-phase implementation task with many tool calls |
| Prioritize inspecting `sdc_agent/*`, `tools/*`, and `tests/*` before editing | These paths likely contain the integration gaps implied by the docs |
| Let tests drive the concrete implementation target | The docs are strategic; tests will show the executable contract |
| Fix repo-local verification ergonomics alongside feature work | A source-complete project still needs a predictable way to run tests from the root |
| Implement Phase 3 feedback in scheduler and genetic driver without forcing a new DB migration | The required signals can be computed from existing projections and stored in testcase metadata/lineage |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `rg --files .` returned the full monorepo and was too broad to reason about directly | Narrow subsequent inspection to docs, control-plane modules, CLIs, and tests |
| Validation depends on interpreter choice and import path behavior | Capture this as a concrete repo gap and verify against the available Conda Python |
| Phase 3 scoring and evolution feedback were under-modeled relative to the plan | Extended scheduler ranking metadata, mutation planning, and genetic lineage feedback to expose inner-loop value and diversity signals |

## Resources
- `/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md`
- `/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md`
- `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent`
- `/Users/wangxu/1-project/sdc-fuzzing/tools`
- `/Users/wangxu/1-project/sdc-fuzzing/tests`
- `/Users/wangxu/1-project/sdc-fuzzing/docs/state.md`
- `/Users/wangxu/anaconda3/bin/python`
- `/Users/wangxu/anaconda3/bin/pytest`

## Visual/Browser Findings
- No browser or image-based inspection has been used; current findings come from local repository documents and shell inspection.

## Implementation Outcomes
- Added repo-root pytest bootstrap via `/Users/wangxu/1-project/sdc-fuzzing/tests/conftest.py`, which fixes direct `pytest` collection for `sdc_agent`.
- Extended `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py` with `STATIC_DONE` handling, `diversity_bonus`, `legality_factor`, `power_gain`, and `inner_value_score`, and exposed these values through ranking, mutation planning, and result recording.
- Extended `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/driver/genetic.py` with profile-aware fallback instruction recovery, diversity-aware partner selection, profile filtering of offspring instructions, and richer lineage/evolution feedback metadata.
- Updated `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py` and `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/hardware_lane.py` to consume the new ranking signals in summaries and hardware promotion scoring.
- Added regression coverage for scheduler scoring, genetic-driver lineage metadata, agent summary output, and direct pytest collection behavior.
- Added `/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/utils/arm64_isa_catalog.py`, which parses the official Arm A64 XML snapshot plus `docs/armv8-isa` into a normalized catalog with 790 instruction pages, 1576 encodings, execution classification, Kunpeng920 hotness tags, sample assembly, and clang-based sequence validation.
- Added `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/tools/a64_isa_catalog.py` and generated `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/isa/armv8-common/arm_a64_catalog.json` as the local full-A64 source of truth.
- Extended `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py` and `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/generic/tools/mp_sdc_offline_gen.py` with `ALL_GENERATABLE`, `EXECUTABLE_SAFE`, and `KUNPENG920_STRESS` profiles; catalog-driven runs now auto-expand batch count to cover the full catalog.
- Extended `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/tools/a64_isa_audit.py` to report both the legacy `instruction.yaml` gap and the new catalog coverage against official XML.
- Updated `/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/isa/armv8-common/isa.py` to expose catalog-backed profile enumeration directly from the ARM64 ISA object.

## ARM64 Catalog Findings
- The official A64 XML snapshot used in this implementation contains 790 instruction documents and 1576 encoding variants across the `general`, `system`, `float`, and `advsimd` classes.
- The legacy ARM64 `instruction.yaml` still contains only 57 entries and 28 unique mnemonics, so it remains an executable subset rather than the full ISA definition.
- The generated local catalog covers all official mnemonics in the selected classes: `general 248/248`, `system 74/74`, `float 48/48`, `advsimd 284/284`.
- `docs/armv8-isa` currently maps cleanly to 279 of 387 pages by normalized title; the remaining pages are naming/heading mismatches, not XML catalog gaps.
- Full-catalog validation is intentionally split from execution: many encodings are feature-gated, privileged, or trap-like, so the catalog records `executable`, `privileged`, `trap_like`, and `execution_block_reason` instead of pretending everything belongs in the same runtime wrapper.

## Additional Outcomes
- Added a real scripted `memory_bit_flip` path through `/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_fault_request.py`, `/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_kunpeng920_se.py`, and `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py`.
- Upgraded `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/hardware_results.py` so hardware ingest now normalizes detectors, derives detector summaries, and preserves richer machine/build/runtime context.
- Added `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation_strategies.py` plus `/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/mutation_advisor.py`, wiring template/PCFG generation and heuristic mutation advice into the existing generation/scheduler/agent path.
- Verified these additions with targeted and broad regressions, including root `tests`, ARM64 target tests, and gem5 helper tests.
- PR-check follow-up confirmed that the first `memory_bit_flip` implementation was semantically wrong in SE mode because it wrote via physical memory instead of the guest virtual translation path.
- The fix was to move memory fault injection onto an SE-translating path anchored on `ThreadContext`, and to make malformed CPU prefixes or incompatible target kinds fail fast instead of degrading into no-op simulations.

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
