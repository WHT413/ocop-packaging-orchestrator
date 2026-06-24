# Phase 3 Implementation Plan

Status: In progress

## Baseline Findings

- Phase 2 workflow exists in `src/ocop_pack/orchestration/runner.py` with persistent local checkpoints and approval/export flow.
- `src/ocop_pack/orchestration/graph.py` compiles a thin LangGraph graph, but runtime uses `WorkflowRunner`.
- Existing provider code is mock-only: `MockDesignPlanner` and `FixtureArtworkProvider`.
- Baseline command `uv run pytest tests/unit tests/integration tests/e2e -q` passed: 33 passed, 3 warnings.

## Files To Add

- `src/ocop_pack/agents/design_planner/*` for strict schemas, prompt registry, agent request builder, immutable validator.
- `src/ocop_pack/providers/common/*` for retry policy and typed provider errors.
- `src/ocop_pack/providers/planner/*` for mock and OpenAI-compatible planner adapters.
- `src/ocop_pack/providers/image/*` for fixture and OpenAI-compatible image adapters.
- `src/ocop_pack/cache/*` for content-addressed cache keys and cache store.
- `src/ocop_pack/provenance/*` for provenance models and recorders.
- Phase 3 docs and reports under `docs/phase-3/` and `docs/reports/`.
- Tests for planner schema/validator/cache/provider contracts/resume.

## Files To Modify

- `src/ocop_pack/application/ports/planner.py`
- `src/ocop_pack/application/ports/artwork_provider.py`
- `src/ocop_pack/infrastructure/config.py`
- `src/ocop_pack/orchestration/state.py`
- `src/ocop_pack/orchestration/status.py`
- `src/ocop_pack/orchestration/runner.py`
- `src/ocop_pack/orchestration/graph.py`
- `src/ocop_pack/cli/app.py`
- `.env.example`, `README.md`, `CLAUDE.md`

## Dependencies

No new runtime dependency is planned. OpenAI-compatible HTTP calls will use Python stdlib `urllib` to avoid lockfile churn.

## Provider Choice

- Offline: deterministic `MockPlannerProvider` and `FixtureArtworkProvider`.
- Sandbox: OpenAI-compatible planner/image adapters configured via environment variables.

## Migration Risks

- Phase 2 runner is not graph-executed despite graph compilation; Phase 3 will preserve runner behavior while updating graph topology names.
- Real image APIs differ in response shapes; adapter supports common base64 response shapes and fails typed otherwise.
- No Phase 3 Visual Critic/text detector; artwork content verification is warning-only.

## Test Plan

- Keep Phase 1/2 tests passing.
- Add unit/contract tests for schemas, validators, cache keys, retry/error mapping, providers, provenance, and resume idempotency.
- Add offline integration E2E through run/approve/export.
- Add sandbox tests behind `provider_sandbox` marker/env configuration.

## Rollback Plan

- Use `--provider-mode offline` to force deterministic mocks.
- Existing deterministic layout/rendering path remains unchanged after artwork/planner artifacts are created.
- Provider-specific failures map to typed statuses before deterministic candidate generation.

## Out Of Scope

Visual Critic, vision calls, revision loops, web UI, GPU/image hosting, CMYK/prepress, generated logos/QR/final text.