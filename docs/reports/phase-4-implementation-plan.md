# Phase 4 Implementation Plan

Status: READY pending Phase 4 provider capability probes

Created: 2026-06-24

## Decision

Phase 3 exit is PASS in `docs/reports/phase-3-exit-audit.md`, with real planner and image sandbox evidence recorded in `docs/reports/phase-3-sandbox-evidence.md`. Phase 4 implementation may start, but real Visual Critic and artwork revision providers must remain disabled until Phase 4 capability probes pass.

No Accepted ADR is modified. Current ADR-003 and ADR-014 already permit a bounded Visual Critic and API-first provider abstraction, so no new ADR is required for the requested Phase 4 scope unless provider behavior forces a new architectural decision.

## Files To Add

- `src/ocop_pack/agents/visual_critic/schemas.py`
- `src/ocop_pack/agents/visual_critic/guard.py`
- `src/ocop_pack/agents/visual_critic/rubric.py`
- `src/ocop_pack/agents/visual_critic/prompt_registry.py`
- `src/ocop_pack/agents/visual_critic/prompts/system.v1.md`
- `src/ocop_pack/agents/visual_critic/prompts/task.v1.md`
- `src/ocop_pack/agents/visual_critic/prompts/README.md`
- `src/ocop_pack/application/ports/vision_critic.py`
- `src/ocop_pack/application/ports/artwork_revision.py`
- `src/ocop_pack/engine/contact_sheet.py`
- `src/ocop_pack/providers/vision/mock.py`
- `src/ocop_pack/providers/vision/openai_compatible.py`
- `src/ocop_pack/providers/revision/fixture.py`
- `src/ocop_pack/providers/revision/openai_compatible.py`
- `src/ocop_pack/orchestration/phase4_routing.py`
- `tests/unit/agents/test_visual_critic_schema.py`
- `tests/unit/agents/test_visual_critic_guard.py`
- `tests/unit/engine/test_contact_sheet.py`
- `tests/unit/orchestration/test_phase4_budget_routing.py`
- `tests/integration/test_phase4_offline_paths.py`
- `tests/e2e/test_phase4_provider_sandbox.py`
- `docs/phase-4/visual-critic-design.md`
- `docs/phase-4/critic-schema.md`
- `docs/phase-4/critic-prompt-contract.md`
- `docs/phase-4/contact-sheet-contract.md`
- `docs/phase-4/aesthetic-rubric.md`
- `docs/phase-4/artwork-revision-contract.md`
- `docs/phase-4/phase-4-routing.md`
- `docs/phase-4/provider-setup.md`
- `docs/phase-4/caching-and-provenance.md`
- `docs/phase-4/evaluation-protocol.md`
- `docs/phase-4/sandbox-e2e-guide.md`
- `docs/reports/phase-4-provider-capability-matrix.md`
- `docs/reports/phase-4-model-selection.md`
- `docs/reports/phase-4-sandbox-evidence.md`
- `docs/reports/phase-4-evaluation-report.md`
- `docs/reports/phase-4-completion-report.md`

## Files To Modify

- `src/ocop_pack/infrastructure/config.py`: add typed vision/revision settings and Phase 4 budget settings.
- `src/ocop_pack/orchestration/state.py`: add contact sheet, critic, revision, provider, budget, and human-selection fields.
- `src/ocop_pack/orchestration/status.py`: add Phase 4 ready/running/completed/failure statuses.
- `src/ocop_pack/orchestration/budgets.py`: support max one vision call, max one revision, max one image-edit call, Top-K caps.
- `src/ocop_pack/orchestration/runner.py`: insert contact-sheet, critic, revision, revised-candidate, deterministic-rerank, and human-fallback nodes.
- `src/ocop_pack/cli/app.py`: add `critic`, `critic-show`, `revision-show`, `select`, expanded `candidates`, expanded `provenance`, and provider checks.
- `src/ocop_pack/observability/events.py`: add Phase 4 event names and fields.
- `src/ocop_pack/provenance/models.py`: add critic and revision provenance models.
- `.env.example`: add Visual Critic, Artwork Revision, and budget variables.
- `README.md` and `CLAUDE.md`: update current phase, CLI docs, provider setup, limitations, and test commands.
- `pyproject.toml`: add `provider_sandbox` marker.

## Provider Dependencies

Vision Critic:

- Required: image input, contact-sheet size support, strict JSON or reliable parser, timeout, no tools.
- Preferred: usage metadata, request ID, temperature/config control, cost estimate.
- Default offline provider: `mock` / `mock-critic-v1`.
- Real provider: exact provider/model ID must be pinned only after capability probe passes.

Artwork Revision:

- Required: source image input, edit instruction, PNG output, timeout, dimension/aspect preservation or deterministic resize.
- Default offline provider: `fixture` / `fixture-editor-v1`.
- Real provider: exact edit-capable provider/model ID must be pinned only after capability probe passes.

## Implementation Sequence

1. Keep Phase 4 real provider calls disabled until Phase 4 capability probes pass.
2. Implement deterministic contact-sheet renderer and manifest/hash first.
3. Implement strict critic schema, rubric scoring helper, prompt registry, and guard validation.
4. Implement mock vision provider and contract tests.
5. Implement revision request/result contracts, fixture revision provider, post-validation, and cache key.
6. Add settings, budgets, statuses, and routing without enabling real calls by default.
7. Integrate graph nodes after hard-constraint candidate filtering and deterministic ranking.
8. Add CLI inspection/show/select/provenance commands.
9. Add crash/resume tests for all Phase 4 interruption points.
10. Run real sandbox probes and write capability/model-selection/sandbox-evidence reports.

## Routing Policy

- If valid candidate count is 0: route `FAILED_LAYOUT`.
- If valid candidate count is 1: skip vision and route to human approval/review with `vision_calls = 0`.
- If a critic decision exists for the exact contact-sheet hash: resume from cached decision without a provider call.
- If `vision_calls >= 1`: route to human review, not second critic.
- If critic returns `PASS`: select candidate only after hash/hard-constraint validation.
- If critic returns `REVISE_ARTWORK`: perform at most one artwork-layer edit, regenerate candidates, deterministic-rerank, and do not call critic again.
- If critic returns `HUMAN_REVIEW` or guard validation fails twice: stop for human selection.

## Migration Risk

- Workflow state schema expands; checkpoint load must provide backward-compatible defaults.
- Contact-sheet rendering may write previews for multiple candidates, increasing disk usage.
- Real provider adapters may differ in structured-output and edit-image API shape.
- Provider nondeterminism may make sandbox tests require tolerant assertions around content while preserving strict schema/guard checks.
- Existing Phase 1-3 commands must continue to work without enabling Phase 4.

## Rollback

- Keep `OCOP_VISION_PROVIDER=mock`, `OCOP_REVISION_PROVIDER=fixture`, and Phase 4 disabled until capability evidence exists.
- If Phase 4 causes regressions, route directly from `DRAFT_QA_PASSED` to `WAITING_APPROVAL` as current behavior.
- Do not change deterministic candidate generation, QA, rendering, or accepted ADRs during rollback.

## Test Plan

- Unit: contact sheet ordering/hash/ID rendering, critic schema/guard/rubric/cache keys, revision cache key, budget and routing boundaries, provenance serialization.
- Contract: vision PASS/REVISE/HUMAN paths, invalid JSON, extra fields, unknown candidate, timeout, 429, 5xx, auth failures, unknown model, malformed image.
- Contract: revision success, invalid/corrupt image, unsupported edit, timeout, 429, 5xx, auth failures, dimension mismatch.
- Offline integration: PASS, REVISE_ARTWORK, HUMAN_REVIEW, single-candidate, and no-valid-candidate paths with no network.
- Crash/resume: after contact sheet, provider response, decision write, revision request, revised artwork write, revised candidates, before approval.
- Sandbox: marked `provider_sandbox`, records real vision and real image-edit evidence without secrets.
- Regression: full Phase 1-3 quality gate remains green.

## Budget Impact

Default Phase 4 budget:

```yaml
max_vision_calls: 1
max_revision_count: 1
max_image_edit_calls: 1
default_top_k: 6
hard_max_top_k: 8
max_critic_attempts: 2
```

Cache hits must not increment provider call counters. Structured-output retry may retry the same logical vision call once, but must not create a second independent aesthetic decision.

## Current Blockers

1. Real vision provider and real image-edit provider cannot be selected without capability probes.
2. Phase 4 final PASS cannot be claimed from mock/offline tests alone.
3. Artwork content verification remains warning-only from Phase 3 and must not be hidden by Visual Critic.