---
id: ADR-011
title: "External deliverables chỉ gồm PNG và PDF"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-011: External deliverables chỉ gồm PNG và PDF

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | User-facing output contract và artifact naming. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-010, ADR-012, ADR-013 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

User không cần output tương thích công cụ designer. Cung cấp SVG/AI/CorelDRAW editable sẽ mở thêm yêu cầu font embedding, linked assets, layer semantics và cross-tool fidelity. Mục tiêu hiện tại là preview và final design document theo full-spread size.

Dù internal engine có thể dùng scene graph/SVG, deliverable cần đơn giản và ổn định.

## Decision drivers

- Giảm output surface và support burden.
- Đáp ứng nhu cầu xem/chia sẻ và file physical-size.
- Cho phép renderer dùng một manifest cho hai format.
- Không cam kết editor compatibility.

## Decision

User-facing output baseline gồm:

- `final_preview.png`: high-resolution sRGB preview, không fold lines.
- `final_design.pdf`: một page đúng full-spread physical size, không fold lines.

Internal artifacts như `layout_manifest.json`, scene SVG và `dieline_overlay.pdf` được giữ để audit/debug nhưng không phải external deliverables mặc định.

## Quy tắc bắt buộc

- PNG/PDF phải sinh từ cùng LayoutManifest/Scene.
- Final output không chứa technical fold overlay.
- PDF page size khớp DielineSpec.
- Output path immutable sau approval/finalization.
- Không quảng bá editable vector compatibility.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| SVG là external deliverable | Bị loại vì user không cần và tăng security/font/editor compatibility. |
| Chỉ PNG | Bị loại vì thiếu physical page size và document format. |
| Chỉ PDF | Bị loại vì preview/share nhanh kém thuận tiện. |
| AI/PSD/CDR output | Bị loại vì proprietary format và ngoài scope. |

## Consequences

### Positive

- Contract đơn giản.
- Dễ test dimensions và visual parity.
- Giảm support cross-tool.
- Phù hợp CLI workflow.

### Negative / trade-offs

- Designer không chỉnh trực tiếp bằng vector editor.
- PDF baseline chưa phải printer-ready universal.
- Internal SVG vẫn cần bảo trì nhưng không public.

## Implementation impact

- Tên file cố định trong `runs/<run_id>/final/`.
- Artifact metadata chứa SHA-256, dimensions, renderer version.
- QA rasterize PDF để so/QR test khi cần.
- Export chỉ xảy ra sau QA + approval.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Cả PNG và PDF được tạo cho happy path.
- Page/pixel dimensions đúng theo DPI/size.
- Visual layout giữa hai output nhất quán trong tolerance.
- Không có fold overlay trong final.
- CLI trả paths và checksums.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| User hiểu PDF là print-ready | Disclaimers và ADR-015. |
| PNG quá nặng | Configurable DPI với minimum quality gate. |
| Renderer divergence | Single scene/manifest source và integration tests. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- User cần editable output.
- Printer yêu cầu PDF/X hoặc prepress profile.
- Web editor được đưa vào scope.

## Rollback / migration strategy

Thêm output adapter mới như optional artifact; không đổi hai deliverables baseline hoặc phá existing consumers.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
