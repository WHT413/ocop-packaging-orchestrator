---
id: ADR-004
title: "Chỉ hỗ trợ hai full-spread size cố định trong baseline"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-004: Chỉ hỗ trợ hai full-spread size cố định trong baseline

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Product boundary, input allowlist và DielineSpec registry. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-005, ADR-006, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Yêu cầu sản phẩm hiện tại chỉ cần hai kích thước toàn bộ bản trải: 130 × 150 mm và 156 × 180 mm. Mở input cho width/height tùy ý sẽ làm tăng không gian layout, số token cấu hình, edge cases text/QR/logo và nhu cầu physical validation.

Hai size cùng tỷ lệ tổng thể nhưng không được xem là chỉ scale pixel, vì readability của text/logo/QR cần physical units và independent fitting.

## Decision drivers

- Giảm search space và test matrix.
- Cho phép golden fixtures và physical mockup có ý nghĩa.
- Ngăn unsupported geometry đi vào pipeline.
- Tập trung chất lượng thay vì breadth.

## Decision

Baseline chỉ chấp nhận hai `size_id`:

- `OCOP_130X150`: canvas 130 × 150 mm.
- `OCOP_156X180`: canvas 156 × 180 mm.

Kích thước là toàn bộ full-spread canvas, không phải front panel. Mọi project ngoài allowlist bị reject với `UNSUPPORTED_SIZE`. Size profile được versioning bằng YAML/Pydantic và snapshot vào mỗi run.

## Quy tắc bắt buộc

- Input dùng `size_id`, không nhận width/height tự do trong public contract.
- Mỗi run giữ immutable size profile version.
- Renderer dùng mm làm source of truth.
- Text/QR/logo fitting chạy độc lập cho từng profile.
- Thêm size mới cần ADR, DielineSpec, templates, tests và physical gate.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Cho phép mọi width/height | Bị loại vì không thể đảm bảo template/fold/readability trên không gian vô hạn. |
| Chỉ hỗ trợ một size cho MVP | Đơn giản hơn nhưng không đáp ứng scope kinh doanh đã chốt. |
| Scale tuyệt đối từ một master size | Bị loại vì text, QR và logo không scale tuyến tính về readability. |
| Auto-discover size từ ảnh reference | Bị loại vì không đáng tin và không phải source of truth. |

## Consequences

### Positive

- Scope rõ và dễ nghiệm thu.
- Giảm candidate explosion.
- Test physical print có thể lặp lại.
- Dễ kiểm soát PDF page size.

### Negative / trade-offs

- Không phục vụ SKU ngoài hai size.
- Thêm size mới cần engineering và QA.
- Có nguy cơ business hiểu nhầm size là front panel.

## Implementation impact

- Đặt profile ở `configs/size_profiles/ocop_130x150.v2.yaml` và `ocop_156x180.v2.yaml`.
- Pydantic Literal/registry validate allowlist.
- Golden tests kiểm tra folds, panels, PNG pixel size và PDF page size.
- CLI hiển thị rõ “full-spread size”.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Size ngoài allowlist luôn bị reject trước model/provider call.
- Hai profile load đúng dimensions và version.
- PNG/PDF có physical aspect/page size đúng.
- Cùng project có thể render trên cả hai profile mà text fitter chạy lại.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Sai hiểu size | Đặt field/documentation là `full_spread_size_id` hoặc mô tả rõ. |
| Profile bị sửa âm thầm | Versioned config, hash snapshot và review ADR. |
| Tưởng hai size chỉ scale | Tests readability/QR riêng cho từng size. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Có business case SKU mới được phê duyệt.
- Có dieline được nhà in xác nhận.
- Template và golden dataset mới đã sẵn sàng.

## Rollback / migration strategy

Không cần migration với run cũ; thêm profile version mới và giữ profile cũ để reproducibility.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
