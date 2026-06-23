---
id: ADR-014
title: "API-first cho image/vision provider trong pilot"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-014: API-first cho image/vision provider trong pilot

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Provider strategy, cost telemetry và self-host boundary. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-001, ADR-003 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Image generation và vision ranking có thể cần GPU, model serving, safety filtering, upgrades và capacity planning. Trong pilot, volume chưa ổn định và chất lượng model cần thử nghiệm. Self-host sớm có thể làm team dành thời gian cho GPU/Ops thay vì layout engine.

Phase 1 không gọi provider; quyết định này áp dụng từ Phase 3/4. Provider lock-in vẫn cần tránh bằng typed adapter và versioned request/response contract.

## Decision drivers

- Giảm upfront GPU/Ops.
- Thử nhiều model/provider nhanh.
- Đo cost/latency/quality thực trước self-host.
- Giữ deterministic core local.

## Decision

Pilot ưu tiên external API cho image generation và vision critic, thông qua `ImageProvider`/`VisionProvider` interfaces. Không hard-code provider SDK trong domain/application.

Phase 1 sử dụng mock/local fixtures và **không có network/model dependency**. Chỉ xem xét self-host khi telemetry chứng minh API không phù hợp về cost, privacy, latency hoặc reliability và team có năng lực vận hành GPU.

## Quy tắc bắt buộc

- Provider request tối thiểu, không gửi logo/QR nếu không cần.
- Pin model ID/config/prompt version.
- Timeout/retry bounded và idempotency/cache.
- Cost estimate/call count ghi RunManifest.
- Provider output luôn untrusted và schema/content validated.
- Không retry vô hạn vì aesthetic quality.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Self-host image model ngay | Bị loại vì GPU/Ops cost chưa có business volume. |
| Provider-specific code xuyên codebase | Bị loại vì lock-in và khó test. |
| Không dùng image/vision provider | Khả thi cho deterministic MVP nhưng không đạt creative automation target dài hạn. |
| Nhiều provider fallback tự động ngay | Bị loại ở baseline vì complexity/cost unpredictability; có thể thêm sau telemetry. |

## Consequences

### Positive

- Time-to-pilot nhanh.
- Dễ benchmark model.
- Không cần GPU infrastructure.
- Provider replaceable qua adapter.

### Negative / trade-offs

- Chi phí per-call và dependency bên ngoài.
- Data privacy/retention cần review.
- Latency/rate limits.
- Model/version có thể thay đổi.

## Implementation impact

- Define protocol và fake provider trong tests.
- Content-addressed cache theo normalized request + model config.
- Circuit breaker đơn giản/timeout/retry cho transient errors.
- Redact secrets/payload khỏi logs.
- Budget: image <=2 default, hard max3; vision hard max1.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Phase 1 quality gates không cần network/provider SDK.
- Provider adapter contract tests pass bằng fake server/mock.
- Resume không duplicate charged call khi artifact cache tồn tại.
- RunManifest ghi provider/model/request hash/cost.
- Hard call budget được enforce.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Provider outage | Cache, bounded retry và human fallback. |
| Privacy | Minimize payload, review terms/retention, optional self-host trigger. |
| Model drift | Pin version khi có thể, golden evaluation và provider config versioning. |
| Unexpected cost | Hard budget và usage telemetry. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Monthly API cost vượt self-host TCO có bằng chứng.
- Data không được phép rời hạ tầng.
- Latency/SLA không đạt.
- Volume ổn định và GPU Ops team sẵn sàng.

## Rollback / migration strategy

Tắt provider features và dùng pre-supplied artwork/manual selection; deterministic layout/render vẫn hoạt động.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
