# Provider Capability Matrix

Status: BLOCKED for real-provider rows until sandbox credentials are provided. Offline providers are available for CI.

| Capability | Planner provider | Image provider | Evidence | Required? |
|---|---|---|---|---|
| Authentication works | BLOCKED | BLOCKED | No sandbox secrets in repository/session | Yes |
| Model exists | BLOCKED | BLOCKED | No verified model IDs supplied | Yes |
| Structured output / JSON schema | PARTIAL | N/A | Parser validates `DesignPlan`; provider strict JSON schema not probed | Yes |
| Vietnamese input | BLOCKED | N/A | Not probed against real planner | Yes for planner |
| Timeout configurable | PASS | PASS | `PlannerSettings.timeout_seconds`, `ImageSettings.timeout_seconds` | Yes |
| Usage metadata | PARTIAL | NOT_IMPLEMENTED | Planner records usage if returned; image adapter records none | Preferred |
| Request ID | PARTIAL | PARTIAL | Adapters record response `id` when returned | Preferred |
| Image generation | N/A | BLOCKED | Real endpoint not probed | Yes |
| PNG output | N/A | PARTIAL | Adapter validates PNG; real endpoint not probed | Yes |
| Required dimensions/aspect | N/A | PARTIAL | Adapter validates 1024x1024; provider capabilities not discovered | Yes |
| Seed support | N/A | NOT_IMPLEMENTED | No assumption made | Optional |
| Negative prompt | N/A | PARTIAL | Prohibition appended to prompt for OpenAI-compatible APIs | Optional |
| Safety metadata | N/A | NOT_IMPLEMENTED | Not returned by current adapter | Preferred |
| Cost metadata available | PARTIAL | NOT_IMPLEMENTED | Cost remains 0/null equivalent when unavailable | Preferred |