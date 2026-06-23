---
id: ADR-015
title: "Physical fold test là production gate bắt buộc"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-015: Physical fold test là production gate bắt buộc

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Production readiness, dieline validation và print claims. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-004, ADR-005, ADR-006, ADR-010, ADR-011, ADR-013 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Dieline baseline được suy ra từ reference và yêu cầu, chưa được nhà in chứng nhận. Rendering và geometry tests chỉ chứng minh consistency với DielineSpec, không chứng minh vật liệu thực tế sẽ gấp đúng, không lệch, không co giãn hoặc đáp ứng cut/bleed tolerance.

PDF cũng đang ở sRGB và không có printer-specific prepress. Vì vậy production pilot cần một gate vật lý trước khi dùng output cho in hàng loạt.

## Decision drivers

- Phát hiện sai fold/panel alignment mà software test không thấy.
- Ngăn false claim “printer-ready”.
- Xác minh readability sau gấp.
- Tạo feedback để version DielineSpec.

## Decision

Trước production pilot/in hàng loạt, team phải in mockup 1:1 cho **cả hai size**, gấp theo fold lines baseline và review với designer/QA/nhà in khi có thể.

Gate kiểm tra: physical dimensions, fold alignment, critical content distance, panel visibility, QR scan, text/logo readability, artwork continuity và nhu cầu bleed/cut tolerance. Nếu fail, sửa DielineSpec/profile/template và chạy lại tests; không sửa agent prompt để “bù” geometry.

## Quy tắc bắt buộc

- Mockup tỷ lệ 1:1, không fit-to-page.
- Test cả 130×150 và 156×180.
- Ghi measurement, ảnh và sign-off record.
- Fail gate chặn production status.
- Mọi thay đổi fold tạo profile version mới và regression tests.
- Approval thiết kế không thay thế physical gate.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Chỉ dựa vào PDF dimensions | Bị loại vì không kiểm tra vật liệu/gấp/cắt. |
| Dựa vào vision model/mockup 3D | Bị loại vì simulation không đủ production evidence. |
| Để nhà in tự xử lý không ghi nhận | Bị loại vì mất feedback/audit và có thể thay đổi layout ngoài hệ thống. |
| Bỏ gate vì hai size đơn giản | Bị loại vì fold baseline chưa certified. |

## Consequences

### Positive

- Giảm rủi ro in sai hàng loạt.
- Tạo evidence thực cho geometry.
- Phân biệt design output và production readiness.
- Giúp calibrate fold exclusion/templates.

### Negative / trade-offs

- Tốn thời gian/vật liệu và cần phối hợp.
- Có thể phát hiện muộn nếu thực hiện sau nhiều development.
- Mỗi cấu trúc/vật liệu mới có thể cần retest.

## Implementation impact

- Tạo checklist `docs/qa/physical-fold-validation.md` trong phase hardening.
- Lưu record gồm profile version, printer settings, actual measurements, pass/fail và reviewer.
- Không đổi v2 config in-place; tạo v3 nếu cần.
- Acceptance production pilot yêu cầu physical gate pass.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Có mockup/sign-off cho cả hai size.
- Critical text/logo không nằm trên nếp gấp thực tế.
- QR scan được sau in/gấp.
- Panel alignment trong tolerance được team/nhà in chấp nhận.
- Run/documentation không gọi printer-ready trước gate.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Máy in văn phòng không đại diện production | Dùng làm early gate; printer proof vẫn cần khi chọn vendor/material. |
| Fit-to-page làm sai scale | Checklist bắt buộc actual-size và đo ruler. |
| Thay material làm thay geometry | Re-run gate khi material/print process thay đổi. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Nhà in cung cấp certified dieline và proof process.
- Packaging material/structure thay đổi.
- Thêm size/profile mới.

## Rollback / migration strategy

Nếu baseline fail, mark profile superseded, tạo version mới, regenerate golden fixtures và repeat physical validation.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
