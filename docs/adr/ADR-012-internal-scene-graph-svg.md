---
id: ADR-012
title: "Cho phép internal SVG/scene graph nhưng không coi là deliverable"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-012: Cho phép internal SVG/scene graph nhưng không coi là deliverable

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Master composition representation và renderer architecture. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-010, ADR-011 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Geometry dùng mm, logo có thể là vector, text cần font metrics và PNG/PDF phải đồng nhất. Nếu renderer thao tác trực tiếp bằng nhiều lệnh Pillow/ReportLab riêng, hai output dễ lệch và khó audit source_ref/bbox.

Một scene representation trung gian giúp deterministic composition, z-order, transforms và reuse output adapters. Tuy nhiên exposing SVG cho user tạo thêm security/editor expectations không cần thiết.

## Decision drivers

- Một source of truth cho PNG/PDF.
- Bảo toàn vector logo khi khả thi.
- Audit từng element và bbox.
- Dễ golden test và renderer replacement.

## Decision

Engine dùng internal scene graph, có thể serialize thành sanitized SVG (`final.scene.svg`) hoặc representation tương đương. Scene chứa element IDs, source refs, bbox mm, transforms, z-index và metadata.

Internal SVG/scene là artifact kỹ thuật, không phải external deliverable. Mọi external output phải được render từ cùng scene/LayoutManifest.

## Quy tắc bắt buộc

- Scene không chứa script, external URL hoặc active content.
- Mọi element có stable ID/source_ref.
- Transforms explicit; logo aspect ratio locked.
- Units source of truth là mm.
- Renderer adapters không tự thay layout.
- Scene serialization versioned.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Render PNG và PDF bằng code riêng | Bị loại vì layout drift. |
| Pillow-only raster master | Bị loại vì mất vector/text fidelity và physical-unit semantics. |
| Expose SVG trực tiếp | Bị loại vì security và editor compatibility ngoài scope. |
| Canvas JSON không có schema | Bị loại vì khó validation/versioning. |

## Consequences

### Positive

- Output parity tốt.
- Debug/audit rõ.
- Renderer replaceable.
- Có thể giữ vector trong PDF.

### Negative / trade-offs

- Phải thiết kế scene schema.
- SVG renderer/font behavior có thể khác môi trường.
- Cần sanitize nghiêm ngặt.

## Implementation impact

- Định nghĩa `Scene`, `SceneGroup`, `TextElement`, `ImageElement`, `VectorElement`, `QrElement`.
- Build scene từ immutable LayoutManifest.
- Serialize internal file dưới `runs/<id>/internal/`.
- Pin renderer/font manifest.
- Property/integration tests kiểm tra element IDs và bounding boxes.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- PNG và PDF dùng cùng scene hash.
- Không có active SVG content.
- LayoutManifest đủ để rebuild scene.
- Logo/text/QR source refs truy ngược được.
- Golden visual diff ổn định trong tolerance.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| SVG injection | Sanitize input và không copy raw SVG DOM trực tiếp. |
| Font mismatch | Bundled fonts, font manifest và rendering CI. |
| Scene schema churn | Version field và migration/read compatibility. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Renderer technology thay đổi.
- Cần editor/canvas compatibility.
- PDF/X/prepress pipeline yêu cầu representation khác.

## Rollback / migration strategy

Giữ LayoutManifest là canonical; thay scene serializer/renderer adapter mà không đổi domain contract.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
