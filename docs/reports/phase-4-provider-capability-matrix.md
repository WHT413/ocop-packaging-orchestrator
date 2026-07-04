# Phase 4 Provider Capability Matrix

Date tested: 2026-06-25 (Asia/Saigon)

| Capability | Result |
|---|---|
| Provider | OpenAI-compatible chat completions endpoint |
| Endpoint | `${OCOP_VISION_BASE_URL}/chat/completions` |
| Model ID | `gemini/gemini-3.1-flash-image-preview` |
| Streaming mode observed | SSE response from provider; adapter supports SSE and non-stream chat completions |
| `response_format` support | JSON object mode accepted (`{"type":"json_object"}`) |
| JSON Schema support | Not verified/supported in this run; adapter does not claim provider-side strict schema |
| structured_output_mode | `prompt_json` |
| Probe A - Minimal JSON | PASS after SSE/content extraction |
| Probe B - Full CriticDecision schema | PASS after prompt clarified score ranges and confidence range |
| Raw response form | SSE chunks with chat-completion choices; content must be assembled from `choices[].delta.content`; `[DONE]` terminates stream |
| Limitations | Provider may emit 100-point totals/confidence unless prompt explicitly states `total_score` 0-10 and `confidence` 0-1; no provider-side strict JSON Schema guarantee |
| Evidence | Real E2E `tests/e2e/test_phase3_real_ai.py::test_phase3_full_e2e_generates_real_ai_artwork_and_final_packaging` passed and generated critic provenance/request ID |
| Secret handling | Raw failed response captured only as redacted debug artifact; no Authorization/API key persisted |