# OCOP Packaging Orchestrator

Deterministic OCOP packaging orchestration for full-spread layout prototypes. The system validates structured project input, resolves immutable dielines, plans safe design intent, generates artwork-backed candidates, runs deterministic QA, supports optional sandbox AI providers, and renders auditable PNG/PDF outputs from scene manifests.

## Current Scope
- Pydantic input schemas, fixed size profiles, millimetre geometry, deterministic candidate generation, typography, visual themes, logo/OCOP/QR checks, internal scene, PNG/PDF renderer, local artifacts, CLI, tests, and documentation.
- Phase 3/4 provider workflow with offline mock/fixture providers by default and opt-in OpenAI-compatible planner, image, vision critic, and artwork revision ports.
- Contact sheet review, critic decisions, bounded revision loop, provenance, retry/error handling, budget guards, checkpoint/resume support, and acceptance evidence helpers.

## Out Of Scope
- No production print certification, PostgreSQL, MinIO, Redis, queues, distributed workers, or unbounded AI spend.
- Real provider tests are opt-in and require sandbox credentials; default CI/local validation stays offline and deterministic.

## Architecture
- `domain`: typed contracts and geometry; no infrastructure imports.
- `engine`: deterministic layout, constraints, typography, visual themes, QR, contact sheets, scene, renderer.
- `agents`: prompt registries, planner input assembly, visual critic guardrails, and rubrics.
- `providers`: mock/fixture and OpenAI-compatible adapters for planner, image, vision critic, and revision flows.
- `orchestration`: workflow runner, checkpointing, statuses, budgets, idempotency, and approval gates.
- `infrastructure`: SQLite, local storage, logging/config.
- `services`: validation, rendering, layout, and QA helpers.
- `cli`: Typer commands.

## Repository Structure
See `src/ocop_pack`, `configs`, `examples`, `tests`, `scripts`, and `docs`.

## Prerequisites
- Python 3.12 managed by uv.
- uv package manager.

## Install
```bash
uv python install 3.12
uv sync
```

## SQLite
```bash
uv run ocop-pack init-db
```

## Example
```bash
uv run ocop-pack validate examples/projects/tea_basic/project.yaml
uv run ocop-pack generate-candidates examples/projects/tea_basic/project.yaml --run-id run_demo_001
uv run ocop-pack render-candidate --run-id run_demo_001 --candidate-id C001
uv run ocop-pack qa --run-id run_demo_001 --candidate-id C001
```

## Workflow Runner
Offline mode is deterministic and uses mock/fixture providers, so it is safe for CI and local development without API keys.

```bash
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id phase4_demo
uv run ocop-pack status phase4_demo
uv run ocop-pack approve phase4_demo --candidate-id C001 --approved-by reviewer
```

Set provider environment variables from `.env.example` and pass the CLI online flag only for sandbox runs that should call configured providers.

## Providers
- `mock` / `fixture`: deterministic offline providers used by default for planner, artwork, visual critic, and revision tests.
- `openai-compatible`: opt-in HTTP adapters for configured planner, image, and vision endpoints.
- Provider sandbox tests are marked with `provider_sandbox` or `real_ai` and may spend one bounded external call.

## Tests And Quality
```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/ocop_pack
uv run pytest -q -m "not real_ai and not provider_sandbox"
```

## Output Folder
```text
runs/<run_id>/input
runs/<run_id>/geometry/dieline_overlay.pdf
runs/<run_id>/candidates/candidates.json
runs/<run_id>/previews/contact_sheet.png
runs/<run_id>/critic/critic_request.json
runs/<run_id>/critic/critic_decision.json
runs/<run_id>/artwork
runs/<run_id>/internal
runs/<run_id>/final/packaging.png
runs/<run_id>/final/packaging.pdf
runs/<run_id>/qa/qa_report.json
runs/<run_id>/run_manifest.json
```

## Known Limitations
- Renderer is preview-oriented and must not be called printer-ready.
- OCOP lockup verifies rendered star count from input only; it does not verify legal certification.
- Physical fold validation remains a technical geometry check and requires print/vendor review before production.
- Mock and fixture providers are intentional test doubles; production-like AI calls require explicit online configuration.
