# Phase 3 Sandbox Evidence

Status: BLOCKED for real sandbox evidence because no provider credentials/model IDs were available in the session.

Offline evidence should be regenerated after code changes with:

```bash
uv run ocop-pack providers check
uv run ocop-pack run examples/projects/tea_basic/project.yaml --run-id phase3_offline_e2e --provider-mode offline
uv run ocop-pack approve --run-id phase3_offline_e2e --candidate C001
uv run ocop-pack inspect phase3_offline_e2e --json
```

Real sandbox evidence must not include API keys and must include provider/model IDs, request IDs if returned, artifact hashes, final PNG/PDF paths, call counters, cache hits, and QA status.