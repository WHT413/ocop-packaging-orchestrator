# Phase 3 Model Selection

Status: BLOCKED. No exact real planner or image model can be pinned without successful capability probes.

- Models considered: none verified in this session.
- Selected planner model: not selected; offline default is `mock-design-planner-v1`.
- Selected image model: not selected; offline default is `fixture-artwork-v1`.
- Endpoint type: OpenAI-compatible adapters are implemented for `/chat/completions` and `/images/generations`.
- SDK version: no provider SDK pinned; adapters use Python stdlib `urllib` plus Pillow validation.
- Limitations: strict provider JSON schema, image dimensions, cost metadata, safety metadata, and request IDs require provider-specific probes.
- Fallback provider: mock planner and fixture artwork provider for offline CI.
- Date tested: 2026-06-24 local offline only.