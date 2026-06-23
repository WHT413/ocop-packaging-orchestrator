---
id: ADR-007
title: "Logo là immutable asset; tối đa 5 logo hiển thị tính cả OCOP"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-007: Logo là immutable asset; tối đa 5 logo hiển thị tính cả OCOP

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Brand asset integrity, logo count và layout search space. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-003, ADR-008, ADR-009 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Bao bì có thể chứa primary brand, producer, partner và OCOP logo. Generative model dễ làm biến dạng, thay màu hoặc hallucinate logo. Quá nhiều logo cũng tạo “logo soup”, phá hierarchy và buộc engine thu nhỏ logo đến mức không đọc được.

User mong placement linh hoạt nhưng không yêu cầu AI tạo lại logo. Vì vậy flexibility phải nằm ở region/anchor/scale cluster, không nằm ở việc biến đổi source asset.

## Decision drivers

- Bảo toàn brand/certification asset.
- Giới hạn combinatorial search space.
- Ngăn logo mất nhận diện.
- Tạo hard constraint có thể test.

## Decision

Logo được xem là immutable source asset. Hệ thống được phép reposition, uniform scale và đặt neutral backplate khi policy cho phép; không được crop, stretch, recolor, rotate hoặc regenerate.

Tổng số visible logo tối đa là **5**, tính cả logo OCOP. Star icons của OCOP lockup không tính là logo. Preferred range là 2–4. Nếu 5 logo không thể fit với readability/hierarchy hợp lý, hệ thống trả `NEEDS_INPUT` thay vì thu nhỏ vô hạn.

## Quy tắc bắt buộc

- Mỗi logo có source hash và role/priority.
- Aspect ratio luôn locked.
- Rotation logo = 0.
- Visible logo count <= 5.
- OCOP logo bắt buộc và được tính trong count.
- Partner logo priority thấp hơn primary/OCOP.
- Asset sanitizer áp dụng trước render.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Cho image model đặt hoặc vẽ lại logo | Bị loại vì hallucination và brand violation. |
| Không giới hạn số logo | Bị loại vì layout quality và search space không kiểm soát. |
| Hard-code vị trí logo | Bị loại vì trái yêu cầu flexible composition. |
| Thu nhỏ mọi logo để fit | Bị loại vì mất readability/recognition. |

## Consequences

### Positive

- Brand integrity có thể audit bằng hash/transform.
- Candidate generation bounded.
- Error rõ khi content overload.
- Placement vẫn linh hoạt qua template variants.

### Negative / trade-offs

- Một số project 5 logo có thể bị reject.
- Không hỗ trợ creative logo treatment/recolor.
- Cần asset chất lượng tốt từ user.

## Implementation impact

- `LogoAssetSpec` lưu role, path, MIME, dimensions, aspect ratio và SHA-256.
- Transform validator so sánh aspect ratio và crop policy.
- Candidate generator thử cluster modes theo priority.
- QA report liệt kê logo source_ref, bbox và transform.
- SVG phải sanitize active content; raster kiểm tra pixel count.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Logo >5 bị reject trước model call.
- Golden tests 1–5 logo pass theo expected result.
- Không có logo bbox crossing fold.
- Logo output giữ aspect ratio trong tolerance.
- Manifest source hash khớp asset input.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Logo file có padding lớn | Cho phép asset preprocessing chỉ khi explicit và không sửa logo content; lưu derived artifact. |
| 5 logo không fit | NEEDS_INPUT hoặc user giảm logo. |
| SVG độc hại | Sanitize/remove script/external refs và verify magic bytes. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Business case bắt buộc >5 logo.
- Có co-branding specification chính thức.
- Cần support monochrome/recolor được brand owner phê duyệt.

## Rollback / migration strategy

Policy change phải versioning; không mutate run cũ. Có thể thêm manual exception path ngoài automated baseline.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
