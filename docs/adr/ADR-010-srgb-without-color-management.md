---
id: ADR-010
title: "Dùng sRGB baseline; không triển khai color-managed prepress"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-010: Dùng sRGB baseline; không triển khai color-managed prepress

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Color pipeline, PDF claims và print boundary. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-011, ADR-012, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Baseline không có yêu cầu CMYK, ICC profile, spot color hoặc printer-specific prepress. Không có thông tin về máy in, vật liệu, mực hoặc quy trình nhà in. Tự chuyển CMYK bằng profile chung có thể tạo cảm giác “print-ready” sai và vẫn không đảm bảo màu thực tế.

Hệ thống cần consistency giữa artwork, preview PNG và PDF, vì vậy cần một working color space đơn giản và phổ biến.

## Decision drivers

- Giảm complexity và dependency prepress.
- Giữ preview nhất quán trên màn hình.
- Tránh tuyên bố chất lượng màu không có bằng chứng.
- Phù hợp MVP/pilot.

## Decision

Toàn pipeline baseline dùng **sRGB** cho raster artwork và preview. Không thực hiện ICC conversion, CMYK separation, spot color, total ink limit hoặc printer profile validation.

`final_design.pdf` là design PDF theo physical size và sRGB, không được tự gắn nhãn printer-ready. Color-managed export chỉ được thêm khi có printer profile và acceptance workflow cụ thể.

## Quy tắc bắt buộc

- Normalize raster inputs về sRGB khi cần và ghi transformation metadata.
- PNG final có sRGB profile/chunk nếu renderer hỗ trợ.
- PDF không tuyên bố CMYK compliance.
- Không tự chuyển logo color.
- README/output manifest chứa color boundary disclaimer.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| CMYK mặc định bằng generic profile | Bị loại vì không khớp printer/material và tạo false confidence. |
| Giữ mọi input profile hỗn hợp | Bị loại vì preview inconsistency. |
| Spot color extraction tự động | Bị loại vì ngoài scope và khó validate. |
| Không quản lý color space nào | Bị loại vì renderer output có thể không nhất quán. |

## Consequences

### Positive

- Pipeline đơn giản, predictable trên màn hình.
- Không phát sinh prepress claims sai.
- Dễ test render/golden images.

### Negative / trade-offs

- Màu in có thể lệch so với màn hình.
- Không đáp ứng printer cần CMYK/spot.
- Cần bước prepress ngoài hệ thống.

## Implementation impact

- Pillow/renderer convert raster to sRGB; preserve original hash và derived hash.
- Manifest ghi `working_color_space: sRGB`.
- PDF metadata/disclaimer không ghi printer-ready.
- Golden tests chạy trong controlled rendering environment.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- PNG/PDF render không lỗi profile.
- Input profile khác được normalize hoặc reject có lý do.
- No CMYK/ICC dependency trong baseline.
- Documentation nêu rõ color limitation.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| User in trực tiếp và phàn nàn màu | Physical proof và printer review ADR-015. |
| Color conversion làm thay đổi logo | Không recolor; conversion chỉ color-space normalization có audit. |
| Golden diff khác môi trường | Pin renderer/version/fonts và tolerance. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Nhà in cung cấp ICC/profile và color acceptance criteria.
- Khách hàng yêu cầu CMYK/spot.
- Có prepress owner và test proof workflow.

## Rollback / migration strategy

Giữ sRGB export làm preview; thêm printer-specific export profile như output variant riêng, không thay silent baseline.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
