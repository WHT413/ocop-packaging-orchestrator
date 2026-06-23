---
id: ADR-009
title: "User cung cấp logo OCOP và số sao; hệ thống chỉ render deterministic"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-009: User cung cấp logo OCOP và số sao; hệ thống chỉ render deterministic

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | OCOP certification input, legal boundary và star lockup. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-007, ADR-013, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Logo OCOP và số sao là thông tin chứng nhận có ý nghĩa pháp lý/brand. Hệ thống không có source of truth để tự xác minh một sản phẩm được công nhận bao nhiêu sao, và không nên suy luận từ ảnh, text hoặc web.

Mục tiêu kỹ thuật chỉ là bảo toàn input được user/content owner cung cấp và render đúng lockup.

## Decision drivers

- Ngăn hallucination hoặc chứng nhận sai.
- Phân định trách nhiệm pháp lý.
- Cho phép deterministic assertion.
- Không phụ thuộc external registry/scraping.

## Decision

User bắt buộc upload logo OCOP và nhập `star_count` từ 1 đến 5. System render logo và star icons bằng deterministic code; không OCR, không generate bằng image model, không tự xác minh quyền sử dụng hoặc trạng thái chứng nhận.

Manifest ghi `source = user_provided` và `verified_by_system = false`. “Verified by system” chỉ có thể thay đổi trong future ADR có authoritative data source và legal review.

## Quy tắc bắt buộc

- Thiếu logo OCOP hoặc star_count thì `NEEDS_INPUT`.
- Star count ngoài 1–5 bị reject.
- Stars render từ bundled/approved asset hoặc deterministic vector.
- Stars không tính vào max logo count.
- Agent không được sửa star_count.
- Output/CLI không tuyên bố legal verification.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Tự suy luận sao từ filename/ảnh | Bị loại vì sai số và legal risk. |
| Tra cứu web/registry tự động | Bị loại ở baseline vì nguồn/định danh/pháp lý chưa được xác nhận. |
| Cho image model tạo OCOP badge | Bị loại vì hallucination và asset integrity. |
| Không hỗ trợ OCOP lockup | Không đáp ứng product scope. |

## Consequences

### Positive

- Correctness có thể kiểm thử 100%.
- Legal boundary rõ.
- Không phụ thuộc network.
- Không tạo fake certification asset.

### Negative / trade-offs

- User có thể nhập sai và system vẫn render đúng input.
- Cần content owner review.
- Không tự phát hiện logo hết hiệu lực/sai version.

## Implementation impact

- `OcopSpec` có `logo_path`, `star_count`, optional metadata.
- `compose_ocop_lockup` tạo logical SceneGroup.
- Manifest lưu source_ref/hash/count/provenance.
- QA đếm star elements và so input.
- Approval screen hiển thị explicit star count.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- 1–5 stars render đúng trong golden tests.
- Invalid count bị reject trước candidate generation.
- Manifest có provenance fields.
- Không có model/provider call để tạo OCOP asset.
- Human approval hiển thị OCOP summary.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| User nhập sai | Approval responsibility và input confirmation. |
| Asset giả/méo | Logo integrity checks nhưng không legal verification. |
| Star asset style không đúng | Dùng approved system asset và versioning. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Có official API/registry và legal approval.
- Business yêu cầu automated verification.
- OCOP lockup guideline chính thức yêu cầu spacing/variant mới.

## Rollback / migration strategy

Giữ input-driven path làm fallback ngay cả khi future verification được thêm; run cũ không thay đổi provenance.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
