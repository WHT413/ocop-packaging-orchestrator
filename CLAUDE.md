# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A deterministic OCOP packaging orchestrator, not an AI image-generation service and not a web server. Phase 1 validates structured OCOP product input, resolves one of two immutable full-spread dielines, generates fold-aware layout candidates, checks hard constraints, renders preview PNG/PDF artifacts from a scene manifest, and stores local run metadata in SQLite.

The current baseline is a local modular monolith. It uses typed Python domain models, deterministic geometry in millimetres, local filesystem artifacts, and SQLite repositories. It must remain reproducible: the same project input, size profile, and code path should produce the same candidate/QA behavior.

## Phase 1 boundaries

- Python 3.12 and `uv` only.
- Do not add LLM, agent, LangChain, LangGraph, image/vision provider, Redis, Celery, PostgreSQL, MinIO, queue, or distributed-worker dependencies in Phase 1.
- Do not call external model/provider APIs from Phase 1 code paths.
- Prefer the standard library over new dependencies.
- Every public API must be typed; mypy runs in strict mode.
- Every behavior change needs tests.
- Run the full quality gate before reporting completion when code changes are made.

## Commands

```bash
# Setup
uv python install 3.12
uv sync

# Initialize local SQLite metadata store
uv run ocop-pack init-db

# Example deterministic flow
uv run ocop-pack validate examples/projects/tea_basic/project.yaml
uv run ocop-pack generate-candidates examples/projects/tea_basic/project.yaml --run-id run_demo_001
uv run ocop-pack render-candidate --run-id run_demo_001 --candidate-id C001
uv run ocop-pack qa --run-id run_demo_001 --candidate-id C001
uv run ocop-pack inspect run_demo_001

# Quality gate
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pytest --cov=src/ocop_pack --cov-report=term-missing
```

## Architecture

Layering: `src/ocop_pack` is split into domain, engine, infrastructure, services, and CLI layers.

- `domain`: Pydantic contracts, geometry, layout, QA, artifacts, runs, and dieline models. Domain code must not import infrastructure.
- `engine`: deterministic candidate generation, constraints, scoring, logo/OCOP/QR placement, text fitting, scene construction, and rendering.
- `infrastructure`: local config/logging, SQLite persistence, and filesystem storage adapters.
- `services`: application orchestration around validation, layout, rendering, and QA.
- `cli`: Typer commands exposing the local workflow.

Main CLI flow: `src/ocop_pack/cli/app.py` loads a project YAML, resolves a `DielineSpec` via `load_dieline`, generates candidates with `generate_candidates`, stores run/candidate/artifact metadata through SQLite repositories, renders PNG/PDF/overlay outputs, and writes QA reports under `runs/<run_id>/`.

Dielines are fixed and versioned: `src/ocop_pack/domain/dieline.py` only accepts `OCOP_130X150` and `OCOP_156X180`. Profiles live in `configs/size_profiles/ocop_130x150.v2.yaml` and `configs/size_profiles/ocop_156x180.v2.yaml`. Do not change fixed `DielineSpec` values silently; adding or changing a size requires ADR, config versioning, tests, templates, and physical validation.

Geometry source of truth: all business geometry uses millimetres. Pixel dimensions, PDF pages, and preview coordinates must derive from mm-based canvas, panels, fold lines, and exclusion zones.

Persistence boundary: SQLite belongs only in infrastructure and must stay behind repository classes. Domain and engine code should not depend on SQLAlchemy, sessions, paths to DB files, or storage implementation details.

## ADR baseline

Architecture decisions live in `docs/adr/`. Treat accepted ADRs as the baseline, especially:

- ADR-001: modular monolith over microservices.
- ADR-004: only two fixed full-spread sizes in baseline.
- ADR-005: panel ratio 22/56/22 and fold bands 5/90/5 are the baseline.
- ADR-006: no glue flap or outside region in baseline.
- ADR-007/008/009: logos are immutable assets; max five visible logos including OCOP; OCOP logo/star count are user supplied and rendered deterministically.
- ADR-010: sRGB baseline only; no color-managed prepress.
- ADR-011/012: external deliverables are PNG/PDF; SVG/scene graph is internal only.
- ADR-013: human approval is required before final export in later phases.
- ADR-015: physical fold test remains a required production gate.

Do not rewrite architectural history silently. Important changes to architecture, geometry, providers, outputs, or production gates need a new ADR or an explicit ADR update.

## Product/content rules

- Do not rewrite, summarize, translate, embellish, or auto-fill approved product content.
- Input content from project YAML is the source of truth for rendered text.
- The system may validate/fail text fitting, but must not invent marketing copy to make a layout pass.
- OCOP star count is rendered from input only; the system does not verify legal certification.
- Renderer output is preview-oriented and must not be described as printer-ready.

## Outputs and artifacts

Expected local output shape:

```text
runs/<run_id>/input
runs/<run_id>/geometry/dieline_overlay.pdf
runs/<run_id>/candidates/candidates.json
runs/<run_id>/previews
runs/<run_id>/internal
runs/<run_id>/final/final_preview.png
runs/<run_id>/final/final_design.pdf
runs/<run_id>/qa/qa_report.json
```

Keep external deliverables limited to PNG and PDF in this phase. Internal manifests/scene data may support rendering and QA, but should not become public deliverables without an ADR.

## Conventions

- Python 3.12; package/dependency management through `uv`.
- Ruff line length is 100; enabled lint groups are `E`, `F`, `I`, `UP`, and `B`.
- Use modern typing (`X | None`, built-in generics, `collections.abc` where appropriate).
- Imports are package-absolute from `ocop_pack`, not from `src.ocop_pack`.
- Keep Pydantic models explicit and typed; avoid untyped public dictionaries unless the boundary requires it.
- Prefer deterministic functions with injected inputs over hidden global state.
- Do not use `print` in library code; CLI output through Typer is fine.

## Testing expectations

- Add or update unit tests for any behavior change in domain, engine, services, or infrastructure.
- Preserve golden/property/integration coverage where relevant.
- Geometry changes need tests for folds, panels, exclusion zones, output aspect/page size, and invalid inputs.
- Renderer changes should verify both PNG and PDF behavior when practical.
- Persistence changes should stay covered through repository/integration tests rather than leaking SQL into domain tests.

## Gotchas

- Phase 1 intentionally excludes LLM/agent/provider orchestration even though future ADRs mention planner/critic/provider phases.
- `load_dieline` rejects size IDs outside the allowlist; do not broaden this with free width/height fields.
- `DielineSpec` is frozen; treat profile YAML as versioned configuration, not casual test data.
- QA and constraints are technical checks only; final production still requires human/vendor review and physical fold testing.
- If a finalized run used a config version, that config must remain readable/reproducible.
