# Phase 3 Sandbox Evidence

Status: PASS

Audit date: 2026-06-24

## Commands Run

```bash
uv run ocop-pack providers check
uv run pytest tests/e2e/test_phase3_real_ai.py -q -m real_ai --no-cov
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id phase3_real_sandbox --online
uv run ocop-pack approve --run-id phase3_real_sandbox --candidate C001
uv run ocop-pack inspect phase3_real_sandbox --json
uv run ocop-pack provenance phase3_real_sandbox
uv run ruff check .
uv run mypy src
uv run pytest tests/unit tests/integration tests/e2e -q
```

## Results

- Provider configuration check: PASS.
- Real AI E2E: PASS, 2 passed.
- Workflow run: `phase3_real_sandbox` reached `EXPORTED`.
- Regression gate: Ruff PASS, Mypy PASS, Pytest PASS with 37 passed, 3 warnings.
- Coverage: 90.09%, above the 80% threshold.

## Provider Evidence

| Capability | Provider | Model | Request ID |
|---|---|---|---|
| Design planner | openai-compatible | `cx/gpt-5.5` | `resp_033acab72ea8bbf9016a3b8543661c81918b31ff1cfae6bf41` |
| Image generation A01 | openai-compatible | `gemini/gemini-3.1-flash-image-preview` | Not returned by provider response |
| Image generation A02 | openai-compatible | `gemini/gemini-3.1-flash-image-preview` | Not returned by provider response |

## Artifact Evidence

| Artifact | Path | SHA-256 | Notes |
|---|---|---|---|
| Design plan | `runs\phase3_real_sandbox\plan\design_plan.json` | `4b424e9a2569ee74138cb5931931ce0360ca83c7c982947a819467811e5a6c66` | Schema `design-plan.v1` |
| Artwork A01 | `runs\phase3_real_sandbox\artwork\A01.png` | `869294784fd1760c3b5b081da2727c24051e361097538d16c9aad4510bdd0551` | PNG, 1024x1024 |
| Artwork A02 | `runs\phase3_real_sandbox\artwork\A02.png` | `fe57ba928b3060f5ce559099ff00fe8954d58b34f6784f5b8030eb48bd97ca41` | PNG, 1024x1024 |
| Final PNG | `runs\phase3_real_sandbox\final\packaging.png` | Recorded in run artifacts | Deterministic renderer output |
| Final PDF | `runs\phase3_real_sandbox\final\packaging.pdf` | Recorded in run artifacts | Deterministic renderer output |
| QA report | `runs\phase3_real_sandbox\qa\qa_report.json` | Recorded in run artifacts | Final QA passed before export |

## Run Counters

- `llm_calls`: 1
- `image_calls`: 2
- `vision_calls`: 0
- `revision_count`: 0
- `provider_attempts`: 3
- `cache_hits`: 0
- `token_usage`: input 758, output 536, total 1294

## Provenance Notes

- Planner provenance includes provider, model, prompt hash, prompt version `v1`, schema version `design-plan.v1`, input hash, raw response hash, usage, latency, and provider request ID.
- Artwork provenance includes provider, model, artifact hash, prompt hash, negative prompt hash, dimensions, format, input hash, latency, and warning `ARTWORK_CONTENT_NOT_VERIFIED`.
- Image provider responses did not return request IDs; this is recorded as unavailable rather than omitted.
- No API keys or secret values are recorded in this evidence.