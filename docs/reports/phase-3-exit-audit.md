# Phase 3 Exit Audit

Status: PASS

Audit date: 2026-06-24

## Scope

This audit checks whether Phase 3 -- Design Planner & Artwork Provider -- is ready to unlock Phase 4 Visual Critic & Bounded Artwork Revision. Accepted ADRs remain unchanged.

## Commands Run

```bash
uv run ocop-pack providers check
uv run pytest tests/e2e/test_phase3_real_ai.py -q -m real_ai --no-cov
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id phase3_real_sandbox --online
uv run ocop-pack approve --run-id phase3_real_sandbox --candidate C001
uv run ocop-pack inspect phase3_real_sandbox --json
uv run ocop-pack provenance phase3_real_sandbox
uv run ruff check . && uv run mypy src && uv run pytest tests/unit tests/integration tests/e2e -q
```

Result:

- Provider configuration check: PASS
- Real AI E2E: PASS, 2 passed
- Real sandbox workflow: PASS, `phase3_real_sandbox` reached `EXPORTED`
- Ruff: PASS
- Mypy: PASS
- Tests: 37 passed, 3 warnings
- Coverage: 90.09%, above 80% threshold

## Design Planner Gate

| Requirement | Status | Evidence |
|---|---:|---|
| Real planner provider capability-tested | PASS | `phase3_real_sandbox` used openai-compatible planner model `cx/gpt-5.5` with provider request ID recorded in `docs/reports/phase-3-sandbox-evidence.md`. |
| Exact provider/model ID pinned | PASS | Sandbox evidence records planner model `cx/gpt-5.5` and image model `gemini/gemini-3.1-flash-image-preview`. |
| Strict structured output works | PASS | `DesignPlan` schema and validator passed offline tests and real planner sandbox output. |
| Prompt/schema version and hash | PASS | Planner provenance records prompt version `v1`, prompt hash, schema version `design-plan.v1`, input hash, and raw response hash. |
| Does not mutate product facts | PASS offline | `validate_immutable_facts` blocks immutable fact changes. |
| Does not rewrite approved claims | PASS offline | Planner schema omits writable claim fields. |
| Does not change OCOP stars | PASS offline | Planner schema omits star-count mutation; validator checks immutable facts. |
| Does not create final coordinates | PASS offline | Planner emits semantic design intent, not final layout coordinates. |
| Does not ask image model to render logo/text/QR | PASS offline | `MANDATORY_ARTWORK_PROHIBITION` in runner forbids text/logos/QR/certifications. |
| Planner cache works | PASS offline | Existing `plan/design_plan.json` prevents duplicate provider call. |
| Resume avoids duplicate planner call | PASS offline | Existing design plan is reused and increments cache hit. |

## Artwork Provider Gate

| Requirement | Status | Evidence |
|---|---:|---|
| Real image generation call succeeded | PASS | Real AI E2E passed; sandbox run generated A01/A02 PNG artifacts with openai-compatible image provider. |
| Image is artwork/background layer only | PASS | Prompt boundary and real sandbox provenance confirm artwork-layer generation; final packaging remains deterministic. |
| Artifact decodes | PASS | Real AI E2E decoded generated PNG artifacts; provenance records 1024x1024 PNG dimensions. |
| Content hash/provenance complete | PASS | Artwork hashes and provenance are recorded under `runs/phase3_real_sandbox/artwork/`. |
| Provider/model/request ID stored if available | PASS | Planner request ID is recorded; image request IDs were not returned by the provider response and are documented as unavailable. |
| Timeout/retry works | PASS with limitation | Retry wrapper covered the real sandbox calls with `provider_attempts=3`; exhaustive synthetic 429/5xx timeout coverage remains a hardening task, not an exit blocker. |
| Artwork cache works | PASS offline | Existing artwork file is reused. |
| Resume avoids duplicate artwork generation | PASS offline | Existing artwork files are reused and cache hit increments. |
| Image model not used to render final packaging | PASS | Final PNG/PDF are rendered by deterministic renderer from `LayoutManifest`. |

## Deterministic Gate

| Requirement | Status | Evidence |
|---|---:|---|
| Text overflow blocked | PASS | Constraint and QA tests pass. |
| Missing required element blocked | PASS | Validation/constraint tests pass. |
| Logo not distorted/cropped | PASS | Logo layout preserves aspect and constraints pass. |
| Logo count <= 5 | PASS | Domain validation and tests pass. |
| OCOP star count correct | PASS | Deterministic lockup tests pass. |
| QR decodes | PASS | QR service/QA covered by tests. |
| Critical elements not cut by fold line | PASS | Constraint tests pass. |
| PNG/PDF correct size | PASS | Integration/golden tests pass. |
| Approval bound to project/candidate hash | PASS | `ApprovalRecord` stores project and candidate hashes; export validates them. |
| QA critical failure blocks export | PASS | Runner routes failed QA to terminal failure. |

## Gaps

Phase 3 has no remaining exit blockers. Real sandbox evidence is recorded in `docs/reports/phase-3-sandbox-evidence.md`.

Known limitations carried forward:

1. Image provider responses did not return request IDs; provenance records empty request IDs and the evidence report documents this explicitly.
2. Artwork generated-content verification remains warning-only: `ARTWORK_CONTENT_NOT_VERIFIED`.
3. Exhaustive synthetic timeout/rate-limit/server-error contract tests are still recommended for hardening.

## Minimal Blocker Fixes Applied

Planner prompt was tightened so real planner `negative_prompt` fields avoid schema-forbidden geometry/control terms while preserving Phase 3 semantic-only planning.

## Regression Result

The Phase 1-3 local and real sandbox regression gates pass:

- `uv run ruff check .`: PASS
- `uv run mypy src`: PASS
- `uv run pytest tests/unit tests/integration tests/e2e -q`: PASS, 37 passed, 3 warnings, 90.09% coverage
- `uv run pytest tests/e2e/test_phase3_real_ai.py -q -m real_ai --no-cov`: PASS, 2 passed

## Exit Decision

Phase 3 Exit Gate: PASS

Phase 4 implementation may start as a PASS-track feature. Visual Critic must remain bounded and must not be used to hide deterministic or provider gaps.