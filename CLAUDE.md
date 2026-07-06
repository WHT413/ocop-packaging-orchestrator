# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A deterministic + AI-assisted OCOP packaging orchestrator. The system validates structured OCOP product input, resolves one of eight immutable full-spread dielines, plans safe design intent (optionally via AI planner), generates artwork-backed layout candidates, runs visual QA critique, supports bounded artwork revision, and renders auditable PNG/PDF/SVG outputs from scene manifests.

The current baseline is a local modular monolith. It uses typed Python domain models, deterministic geometry in millimetres, local filesystem artifacts, and SQLite repositories. It must remain reproducible: the same project input, size profile, and code path should produce the same candidate/QA behavior.

## Phase boundaries

- Phase 1–4 are complete: deterministic core, orchestration, AI provider integration, review/edit/export loop.
- Phase 5 is in progress: local ops reporting is done, production hardening remains.
- Python 3.12 and `uv` only.
- Mock/fixture providers are the default offline mode; real AI calls require `--online` flag and env config.
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

# Full pipeline (offline)
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id local_demo

# Full pipeline (online with AI providers)
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id online_demo --online

# Approve and export
uv run ocop-pack approve --run-id online_demo --candidate C001 --approved-by reviewer

# Re-render after edits
uv run ocop-pack render-editable --editable-layout runs/online_demo/final/editable_layout.json --project-yaml examples/projects/tea_basic/project.yaml --out-dir runs/online_demo/edited

# Quality gate
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pytest --cov=src/ocop_pack --cov-report=term-missing
```

## Architecture

Layering: `src/ocop_pack` is split into domain, engine, agents, providers, schemas, orchestration, services, provenance, infrastructure, and CLI layers.

- `domain`: Pydantic contracts, geometry, layout, QA, artifacts, runs, and dieline models. Domain code must not import infrastructure.
- `engine`: deterministic candidate generation, constraints, scoring, logo/OCOP/QR placement, EAN-13 barcode encoding, text fitting, visual themes, scene construction, contact sheet, and rendering.
- `agents`: design planner input assembly, prompt registries, visual critic guardrails, and rubrics.
- `providers`: mock/fixture (deterministic offline) and OpenAI-compatible adapters for planner, image, vision critic, and revision flows.
- `schemas`: shared Pydantic schemas for design planner and critic I/O.
- `orchestration`: workflow runner, checkpointing, statuses, budgets, idempotency, and approval gates.
- `provenance`: audit trail models.
- `services`: validation, rendering, SVG export, layout, and QA helpers.
- `infrastructure`: local config/logging, SQLite persistence, and filesystem storage adapters.
- `cli`: Typer commands exposing the local workflow.

Main CLI flow: `src/ocop_pack/cli/app.py` loads a project YAML, resolves a `DielineSpec` via `load_dieline`, generates candidates with `generate_candidates`, stores run/candidate/artifact metadata through SQLite repositories, renders PNG/PDF/SVG outputs, and writes QA reports under `runs/<run_id>/`.

## Dieline sizes

Eight fixed sizes are supported, loaded from `configs/size_profiles/`:

- `OCOP_100X100`, `OCOP_130X130`, `OCOP_130X150`, `OCOP_156X180`
- `OCOP_180X120`, `OCOP_200X150`, `OCOP_220X140`, `OCOP_260X160`

All profiles live in `configs/size_profiles/ocop_<dims>.v2.yaml`. Do not change fixed `DielineSpec` values silently; adding or changing a size requires ADR, config versioning, tests, templates, and physical validation.

Geometry source of truth: all business geometry uses millimetres. Pixel dimensions, PDF pages, and preview coordinates must derive from mm-based canvas, panels, fold lines, and exclusion zones.

## Barcode and QR

- `engine/barcode.py` implements EAN-13 encoding with proper left-odd, left-even, right, and parity tables. Barcode value is derived from `project_id` via SHA-256.
- `engine/qr.py` handles QR code rendering with payload hashing and quiet zone metadata.
- Both are controlled by `packaging.show_barcode` and `packaging.show_qr` boolean fields in project YAML. They default to `false`.

## Visual themes and retail surface

- `engine/visual_theme.py` resolves theme tokens (colors, fonts, opacities) from product data and planner intent.
- `candidate_generator.py` uses `_retail_surface()` to select product-category-aware frame styles (kraft_card for coffee, vellum_overlay for tea, soft_scrim for honey, paper_label as fallback).
- Card fills, opacities, and border radii are theme-driven for retail-reference layouts.

## Persistence boundary

SQLite belongs only in infrastructure and must stay behind repository classes. Domain and engine code should not depend on SQLAlchemy, sessions, paths to DB files, or storage implementation details.

## ADR baseline

Architecture decisions live in `docs/adr/`. Treat accepted ADRs as the baseline, especially:

- ADR-001: modular monolith over microservices.
- ADR-004: fixed full-spread sizes (now 8) in baseline.
- ADR-005: panel ratio 22/56/22 and fold bands 5/90/5 are the baseline.
- ADR-006: no glue flap or outside region in baseline.
- ADR-007/008/009: logos are immutable assets; max five visible logos including OCOP; OCOP logo/star count are user supplied and rendered deterministically.
- ADR-010: sRGB baseline only; no color-managed prepress.
- ADR-011/012: external deliverables are PNG/PDF/SVG; scene graph is internal only.
- ADR-013: human approval is required before final export.
- ADR-014: API-first image and vision providers.
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
runs/<run_id>/previews/
runs/<run_id>/artwork/
runs/<run_id>/critic/
runs/<run_id>/internal
runs/<run_id>/final/packaging.png
runs/<run_id>/final/packaging.pdf
runs/<run_id>/final/packaging.svg
runs/<run_id>/final/editable_layout.json
runs/<run_id>/final/print_spec.json
runs/<run_id>/qa/qa_report.json
runs/<run_id>/run_manifest.json
```

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
- Provider sandbox tests are opt-in (`-m provider_sandbox` or `-m real_ai`) and may spend bounded external calls.

## Gotchas

- Mock/fixture providers are the default; `--online` activates real AI calls.
- `load_dieline` rejects size IDs outside the allowlist; do not broaden this with free width/height fields.
- `DielineSpec` is frozen; treat profile YAML as versioned configuration, not casual test data.
- QA and constraints are technical checks only; final production still requires human/vendor review and physical fold testing.
- If a finalized run used a config version, that config must remain readable/reproducible.
- Barcode/QR are optional and default to hidden. Set `show_barcode: true` / `show_qr: true` in project YAML.
