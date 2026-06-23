---
id: ADR-006
title: "Không có glue flap hoặc outside region trong baseline"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-006: Không có glue flap hoặc outside region trong baseline

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Canvas boundary, packaging structure và export geometry. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-004, ADR-005, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

User xác nhận hai kích thước đã cho là toàn bộ bản trải, không có mép dán hoặc vùng ngoài. Thêm glue flap giả định sẽ làm thay đổi panel width, vị trí folds và vùng printable, đồng thời có thể tạo thiết kế không khớp quy trình gia công thực tế.

Hệ thống không có nhiệm vụ tự phát minh packaging structure. Nếu sản xuất thực tế cần flap/bleed/cut region, thông số phải đến từ nhà in hoặc packaging engineer.

## Decision drivers

- Tuân thủ input contract đã chốt.
- Không tự tạo geometry thiếu bằng chứng.
- Giảm lỗi panel mapping.
- Giữ scope Phase 1 khả thi.

## Decision

`DielineSpec.glue_flap` luôn là `null` trong hai baseline profile. Canvas boundary chính là full-spread design area; không có outside region, bleed region hoặc auto-generated adhesive flap.

Renderer không thêm vùng ngoài page size. Candidate engine không dành region cho glue. Nếu future profile cần flap, đó là packaging structure mới và phải có ADR/profile riêng.

## Quy tắc bắt buộc

- Mọi element phải nằm trong full-spread canvas.
- Không tự cộng bleed hoặc crop marks vào final output.
- Không có template region tên `glue_flap`.
- Input yêu cầu flap bị reject hoặc báo unsupported profile.
- Technical overlay chỉ hiển thị folds đã định nghĩa.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Thêm glue flap mặc định 8–12 mm | Bị loại vì không có production evidence và làm sai kích thước. |
| Cho user nhập flap tùy ý | Bị loại trong baseline vì làm nổ test matrix và risk geometry. |
| Tự suy luận flap theo size | Bị loại vì packaging engineering không thể suy luận an toàn từ canvas size. |
| Thêm bleed mặc định | Bị loại vì chưa có printer tolerance/workflow. |

## Consequences

### Positive

- Geometry đơn giản và minh bạch.
- Không thay đổi dimensions user cung cấp.
- Giảm khả năng xuất file có vùng giả.

### Negative / trade-offs

- Output có thể chưa đủ cho nhà in cần bleed/flap.
- Không hỗ trợ nhiều cấu trúc bao bì thực tế.
- Cần manual prepress nếu printer yêu cầu thêm vùng.

## Implementation impact

- Schema enforce `glue_flap: None`.
- Renderer page size đúng canvas, không margin phụ.
- QA kiểm tra element ngoài canvas và final page size.
- README/disclaimer nêu đây không phải universal printer-ready dieline.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Hai size profile có `glue_flap == null`.
- Final PNG/PDF không có outside region.
- Không có candidate element ngoài canvas.
- Unsupported flap request tạo explicit error thay vì im lặng bỏ qua.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Business dùng file để in trực tiếp | Human/printer review và physical gate ADR-015. |
| Nhà in yêu cầu bleed | Tạo printer-specific profile mới, không patch output ad hoc. |
| User nghĩ fold bands là glue flap | Naming/documentation rõ top/bottom fold bands. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Nhà in cung cấp certified dieline có flap/bleed.
- Packaging structure thay đổi.
- Pilot chứng minh cần printer-specific export profile.

## Rollback / migration strategy

Không sửa baseline profile; thêm DielineSpec family mới có explicit flap/outside regions.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
