---
id: ADR-003
title: "Giới hạn baseline ở hai agent: Design Planner và Visual Critic"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-003: Giới hạn baseline ở hai agent: Design Planner và Visual Critic

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Agent topology, responsibility boundary và model-call budget. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-002, ADR-007, ADR-013, ADR-014 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Bài toán gồm phần mơ hồ/sáng tạo và phần chính xác/deterministic. LLM/vision có giá trị ở việc đề xuất visual direction, artwork prompt và đánh giá thẩm mỹ tổng thể. Ngược lại, logo integrity, fold geometry, QR, text, star count và export cần code deterministic.

Một agent swarm hoặc supervisor + nhiều subagent sẽ tăng số call, context duplication, latency và khó xác định trách nhiệm khi kết quả sai. Dữ liệu pilot chưa chứng minh lợi ích của các agent chuyên biệt như compliance agent, typography agent hoặc logo placement agent.

## Decision drivers

- Giảm cost và latency.
- Giữ trách nhiệm agent rõ ràng.
- Ngăn agent can thiệp domain truth/geometry.
- Dễ đo contribution của từng model call.
- Không tạo autonomous loop không giới hạn.

## Decision

Baseline có tối đa hai agent:

1. **Design Planner Agent**: nhận dữ liệu đã validate và trả `DesignPlan` structured gồm visual direction, palette, artwork concepts và semantic layout intents; không trả tọa độ cuối.
2. **Visual Critic Agent**: nhận contact sheet Top-K đã pass hard constraints, chấm thẩm mỹ và chọn candidate hoặc trả tối đa một targeted artwork revision.

Visual Critic là optional/feature-flag trong MVP và chỉ trở thành mặc định khi pilot chứng minh giá trị. Không có agent-to-agent conversation hoặc supervisor agent trong baseline.

## Quy tắc bắt buộc

- Planner không sửa ProductSpec, DielineSpec, approved text, logo hoặc star count.
- Critic không trả direct coordinates và không override hard constraints.
- Một planner call mặc định; hard max hai khi structured repair.
- Một vision critic call hard max.
- Tối đa một targeted revision.
- Không cấp filesystem/shell/network tools cho agent baseline.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Agent swarm nhiều vai trò | Bị loại vì chi phí, context duplication và khó audit. |
| End-to-end multimodal agent tạo final package | Bị loại vì text/logo/geometry không đáng tin cậy. |
| Không dùng agent nào | Khả thi cho Phase 1; nhưng không đáp ứng mục tiêu tạo visual direction/artwork tự động ở phase sau. |
| Một agent duy nhất làm planner + critic | Bị loại vì self-evaluation bias và contract trách nhiệm mơ hồ. |

## Consequences

### Positive

- Call budget rõ.
- Dễ evaluate planner và critic độc lập.
- Giảm hallucination surface.
- Không làm phức tạp deterministic engine.

### Negative / trade-offs

- Có thể bỏ lỡ một số specialized reasoning.
- Visual Critic có thể không tốt hơn human.
- Planner output vẫn cần schema repair và guardrail.

## Implementation impact

- Pydantic structured output cho `DesignPlan` và `CriticDecision`.
- Agent payload chỉ chứa dữ liệu tối thiểu đã sanitize.
- Prompt/version/model/cost được ghi vào RunManifest.
- Visual Critic nhận contact sheet IDs và rubric, không nhận full workflow transcript.
- Thiết kế evaluation để so critic selection với designer selection.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Không có hơn hai agent class/role trong baseline production path.
- Không có loop agent-agent.
- Model call counters enforce hard max.
- Agent output invalid bị reject/repair có giới hạn.
- Critical correctness vẫn pass khi tắt toàn bộ agent bằng fixtures/mock plan.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Planner bịa product fact | Schema chỉ chứa creative fields; product text không nằm trong writable fields. |
| Critic chọn candidate sai | Human approval bắt buộc; critic không là compliance gate. |
| Prompt injection từ product text | JSON data separation, system instruction và allowlist output. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Pilot cho thấy một nhiệm vụ mới có measurable value và không giải tốt bằng code.
- Agent call cost/latency giảm đủ để mở rộng nhưng vẫn phải có evaluation.
- Có labeled dataset chứng minh specialized critic cải thiện outcome.

## Rollback / migration strategy

Tắt Visual Critic và giữ human selection; hoặc thay Planner bằng deterministic preset. Core rendering/QA không thay đổi.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
