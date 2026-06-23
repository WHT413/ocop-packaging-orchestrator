# OCOP Packaging Orchestrator

Deterministic Phase 1 core for full-spread OCOP packaging layout prototypes. The system validates structured project input, resolves one of two immutable dielines, generates fold-aware candidates, checks hard constraints, renders PNG/PDF from one scene manifest, and stores local metadata in SQLite.

## Phase 1 Scope
- Pydantic input schemas, two fixed size profiles, millimetre geometry, deterministic candidate generation, text fitting, logo/OCOP/QR checks, internal scene, PNG/PDF renderer, SQLite repositories, CLI, tests, and documentation.

## Out Of Scope
- No LLM, vision model, image generation provider, LangGraph workflow, production print certification, PostgreSQL, MinIO, Redis, queues, or distributed workers.

## Architecture
- `domain`: typed contracts and geometry; no infrastructure imports.
- `engine`: deterministic layout, constraints, text, QR, scene, renderer.
- `infrastructure`: SQLite, local storage, logging/config.
- `services`: application orchestration.
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

## Tests And Quality
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pytest --cov=src/ocop_pack --cov-report=term-missing
```

## Output Folder
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

## Known Limitations
- Renderer is preview-oriented and must not be called printer-ready.
- OCOP lockup verifies rendered star count from input only; it does not verify legal certification.
- Physical fold validation remains a technical geometry check and requires print/vendor review before production.
