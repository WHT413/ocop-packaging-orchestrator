# OCOP Packaging Orchestrator – AI Service

> Deterministic + AI-assisted OCOP product packaging design system.  
> From structured product input → full-spread layout candidates → AI artwork → visual QA → print-ready PNG/PDF/SVG output.

## Features

| Category | Details |
|---|---|
| **Dieline Sizes** | 8 OCOP full-spread profiles from 100×100 mm to 260×160 mm |
| **Layout Engine** | Template-driven candidate generator with retail-surface styling, visual themes, typography, EAN-13 barcode, QR code |
| **AI Providers** | Pluggable planner, image generation, visual critic, artwork revision (OpenAI-compatible or mock/fixture) |
| **Orchestration** | Workflow runner with checkpoint/resume, bounded revision loop, budget guards, provenance |
| **Outputs** | High-res PNG (600 DPI), PDF, SVG, editable layout JSON, contact sheet, QA report |
| **Review Loop** | Visual critic selects best candidate, QA validates constraints, human approval gate before final export |

## Architecture

```
src/ocop_pack/
├── domain/          # Pydantic contracts, geometry (mm), dieline, layout, QA models
├── engine/          # Candidate generation, barcode, QR, constraints, typography, visual themes, renderer
├── agents/          # Design planner + visual critic prompt registries, guardrails, rubrics
├── providers/       # Mock/fixture (offline) and OpenAI-compatible adapters
├── orchestration/   # Workflow runner, checkpoints, statuses, budgets, idempotency
├── schemas/         # Shared Pydantic schemas for planner/critic I/O
├── services/        # Validation, rendering, layout, SVG, QA helpers
├── provenance/      # Audit trail models
├── infrastructure/  # SQLite, local storage, logging/config
├── cli/             # Typer CLI commands
└── assets/          # Font files, OCOP logo templates
```

**Key design principles:**
- All geometry in millimetres. Pixel/PDF coordinates derive from mm canvas.
- Domain layer has zero infrastructure imports.
- Mock providers are deterministic → safe for CI without API keys.
- Input product text is sacred: never rewritten, summarized, or auto-filled.

## Supported Dieline Sizes

| Size ID | Dimensions (W×H mm) |
|---|---|
| `OCOP_100X100` | 100 × 100 |
| `OCOP_130X130` | 130 × 130 |
| `OCOP_130X150` | 130 × 150 |
| `OCOP_156X180` | 156 × 180 |
| `OCOP_180X120` | 180 × 120 |
| `OCOP_200X150` | 200 × 150 |
| `OCOP_220X140` | 220 × 140 |
| `OCOP_260X160` | 260 × 160 |

Each size has a versioned YAML config in `configs/size_profiles/`.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Install

```bash
uv python install 3.12
uv sync
```

## Quick Start

```bash
# Initialize local SQLite metadata store
uv run ocop-pack init-db

# Validate a project
uv run ocop-pack validate examples/projects/tea_basic/project.yaml

# Full offline pipeline (deterministic, no API keys needed)
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id demo_001

# Inspect run status
uv run ocop-pack inspect demo_001

# Approve and export final outputs
uv run ocop-pack approve --run-id demo_001 --candidate C001 --approved-by reviewer
```

## Example Projects

9 complete OCOP product examples with Vietnamese packaging data:

| Project | OCOP Stars | Category |
|---|---|---|
| `tea_basic` | 3★ | Trà thảo mộc |
| `honey_basic` | 3★ | Mật ong hoa cà phê |
| `matcha_basic` | 3★ | Bột trà xanh matcha |
| `ginger_honey_basic` | 3★ | Trà gừng mật ong |
| `coffee_4star_basic` | 4★ | Cà phê rang xay |
| `lotus_seed_5star_basic` | 5★ | Hạt sen sấy |
| `banana_chip_2star_basic` | 2★ | Chuối sấy giòn |
| `local_jam_1star_basic` | 1★ | Mứt dâu tằm |
| `che_day_landscape` | 3★ | Chè dây (landscape) |

Run any example:

```bash
uv run ocop-pack run examples/projects/coffee_4star_basic/project.yaml --run-id coffee_demo
uv run ocop-pack run examples/projects/lotus_seed_5star_basic/project.yaml --run-id lotus_demo
```

## Online Mode (AI Providers)

Set provider environment variables from `.env.example`, then:

```bash
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id online_demo --online
```

Online mode uses configured OpenAI-compatible endpoints for:
- **Design Planner**: generates visual direction, palette, artwork concepts, layout intents
- **Image Provider**: generates decorative artwork from planner prompts
- **Visual Critic**: evaluates and selects best candidate from contact sheet
- **Revision Provider**: iterates artwork based on critic feedback

## Output Structure

```
runs/<run_id>/
├── input/                        # Copied project input
├── geometry/dieline_overlay.pdf  # Dieline visualization
├── candidates/candidates.json    # All generated layout candidates
├── previews/
│   ├── C001.png ... C006.png     # Individual candidate previews
│   └── contact_sheet.png         # Side-by-side comparison
├── artwork/                      # AI-generated artwork files
├── critic/
│   ├── critic_request.json       # Input sent to visual critic
│   └── critic_decision.json      # Critic selection + rationale
├── final/
│   ├── packaging.png             # High-res raster (600 DPI)
│   ├── packaging.pdf             # Print-ready PDF
│   ├── packaging.svg             # Editable vector
│   ├── editable_layout.json      # UI-editable layout contract
│   └── print_spec.json           # Print metadata
├── qa/qa_report.json             # QA constraint check results
├── internal/                     # Scene manifests
└── run_manifest.json             # Run provenance & status
```

## Edit & Re-render

After editing `editable_layout.json` (manually or via UI):

```bash
uv run ocop-pack render-editable \
  --editable-layout runs/<run_id>/final/editable_layout.json \
  --project-yaml examples/projects/tea_basic/project.yaml \
  --out-dir runs/<run_id>/edited
```

## Barcode & QR Code

- **EAN-13 Barcode**: auto-generated from `project_id` via SHA-256 → valid EAN-13 encoding. Controlled by `packaging.show_barcode` in project YAML.
- **QR Code**: generated from `packaging.qr_payload`. Controlled by `packaging.show_qr`. Defaults to `https://ocop.example.local/product` if not specified.

Both are optional — set `show_barcode: true` and/or `show_qr: true` in the project YAML to include them.

## Operations Report

```bash
# Audit local runs
uv run ocop-pack ops-report --runs-root runs --out runs/ops_report.json

# Fail on issues (CI gate)
uv run ocop-pack ops-report --runs-root runs --out runs/ops_report.json --fail-on-issues
```

## Tests & Quality

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/ocop_pack
uv run pytest -q -m "not real_ai and not provider_sandbox"
```

Provider sandbox tests are opt-in and may call external APIs:

```bash
uv run pytest -m provider_sandbox
```

## Known Limitations

- `packaging.png` is 600 DPI raster preview; use SVG or `editable_layout.json` for editing.
- OCOP star count is rendered from user input only; no legal certification verification.
- Physical fold validation is a geometry check — requires print/vendor review before production.
- Mock/fixture providers are test doubles; production AI needs explicit online configuration.
- No production auth, object storage, or multi-user support yet (Phase 5 future work).

## License

Internal project — Vibecast / FPT University Summer 2026.
