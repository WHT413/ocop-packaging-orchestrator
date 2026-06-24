# Phase 3 Re-Audit

Status: BLOCKED until real sandbox credentials/capability probes are supplied and executed. Offline path has implementation evidence.

## Requirement Matrix

| ID | Requirement | Source | Current evidence | Status | Gap | Action |
|---|---|---|---|---|---|---|
| P3-PL-001 | DesignPlan typed schema | ADR-003, task sec 8 | `src/ocop_pack/agents/design_planner/schemas.py` | PASS | None | Normalized schema to semantic fields only. |
| P3-PL-002 | Strict structured output / no extras | ADR-003 | Pydantic `extra=forbid` for DesignPlan/ArtworkConcept/LayoutIntent | PASS | Provider uses JSON object, not universal provider JSON-schema enforcement | Parser rejects invalid output; sandbox probe required. |
| P3-PL-003 | No coordinates/bbox/font sizes | ADR-003, sec 2.1 | schema validators reject coordinate terms | PASS | Term-based guard only | Add broader tests. |
| P3-PL-004 | No immutable fact mutation | ADR-007/009, sec 9 | `validator.py`, runner blocks `PLANNING_FAILED` | PARTIAL | Guard is term-based and not exhaustive | Expand guard violations in tests. |
| P3-PL-005 | Prompt version/hash | sec 10 | prompt files under `agents/design_planner/prompts`, prompt hash in request/provenance | PASS | None | Provider now uses loaded prompt content. |
| P3-SEC-001 | Product text as untrusted JSON data | ADR-003 | OpenAI planner wraps input in `<project_data_json>` and system prompt states untrusted | PASS | Needs provider sandbox evidence | Run `providers check` and sandbox E2E. |
| P3-SEC-002 | No model tools/eval/exec | ADR-003 | urllib calls only; no tool interface | PASS | None | Keep adapters tool-free. |
| P3-IMG-001 | ImageProvider interface and fixture | ADR-014 | `application/ports/artwork_provider.py`, `providers/image/fixture.py` | PASS | None | Maintain offline CI. |
| P3-IMG-002 | Real image adapter | ADR-014 | `providers/image/openai_compatible.py` | PARTIAL | Requires credentials/capability probe | Run sandbox probe. |
| P3-IMG-003 | Artwork prompt mandatory prohibition | sec 13 | `MANDATORY_ARTWORK_PROHIBITION` in runner | PASS | None | Added deterministic builder. |
| P3-CACHE-001 | Planner resume skips existing plan | sec 16 | runner checks `plan/design_plan.json` before provider call | PASS | Run-local only, no global content cache | Wire content cache later. |
| P3-CACHE-002 | Artwork resume skips existing PNG | sec 16 | runner checks `artwork/<id>.png` before provider call | PASS | Does not verify dimensions/hash on hit | Add artifact validation. |
| P3-CACHE-003 | Artwork key excludes run_id | sec 16 | runner request hash patched to use concept/prompt/provider mode/dimensions | PASS | Provider/model config should be included explicitly | Extend settings payload. |
| P3-BUD-001 | Budgets planner<=2 image<=3 vision=0 revision=0 | ADR-014 | `BudgetPolicy` | PASS | None | Tests needed. |
| P3-CLI-001 | provider check command | sec 19 | `ocop-pack providers check` | PARTIAL | Minimal config check; no real network probe yet | Add capability probes. |
| P3-E2E-001 | Offline ProjectSpec to Planner to Artwork to Layout to QA to Approval to PNG/PDF | sec 20.3 | Existing CLI E2E plus offline command evidence pending | NOT_TESTED | Need rerun after changes | Run offline E2E. |
| P3-SBX-001 | Real sandbox planner/image integration | sec 20.4 | No API credentials in repo/session | BLOCKED | Cannot verify real provider without secrets | User must provide sandbox env. |
| P3-PH4-001 | No Visual Critic/vision/revision calls in Phase 3 | sec 2.4 | `vision_calls=0`, `revision_count=0`, no critic implementation | PASS | None | Keep Phase 4 out. |

## Discrepancies

- README/CLAUDE still describe Phase 1 baseline; docs are stale relative to current Phase 3 code.
- Existing Phase 3 completion report already marked full PASS blocked due real sandbox absence; this remains true.
- OpenAI-compatible planner used hard-coded prompt before this reaudit; fixed to use versioned prompt files.
- OpenAI-compatible image adapter overwrote real provider image through fixture generator before this reaudit; fixed to validate and preserve provider PNG.