---
id: ADR-005
title: "Dùng panel ratio 22/56/22 và fold bands 5/90/5 làm baseline cấu hình được"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-005: Dùng panel ratio 22/56/22 và fold bands 5/90/5 làm baseline cấu hình được

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Dieline geometry, panel regions và fold exclusion. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-004, ADR-006, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Reference cho thấy center panel rộng, hai side panel hẹp và hai fold band ngang. Chưa có khuôn bế được nhà in chứng nhận, nhưng Phase 1 cần geometry cụ thể để xây fold-aware engine, templates và tests.

Một tỷ lệ baseline phải đủ ổn định để implement, đồng thời không được hard-code rải rác vì physical test có thể yêu cầu điều chỉnh.

## Decision drivers

- Cho phép implementation bắt đầu dù printer dieline chưa final.
- Giữ center panel làm focal region.
- Dùng cùng conceptual structure cho hai size.
- Cho phép sửa một nơi nếu physical validation thay đổi.

## Decision

Baseline DielineSpec dùng:

- Panel dọc: **22% / 56% / 22%**.
- Fold bands ngang: **5% / 90% / 5%**.
- Technical `fold_exclusion_mm = 2.0` quanh fold lines.

Tọa độ cụ thể:

| Size | Vertical folds x | Horizontal folds y |
|---|---:|---:|
| 130 × 150 mm | 28.60; 101.40 | 7.50; 142.50 |
| 156 × 180 mm | 34.32; 121.68 | 9.00; 171.00 |

Các giá trị nằm trong versioned config và là immutable trong một run. Đây là design baseline, không phải certified die-cut geometry.

## Quy tắc bắt buộc

- Không hard-code fold coordinates trong template/agent prompt.
- Template tham chiếu panel/region tương đối.
- Critical elements tránh fold exclusion; artwork/background có thể crossing fold.
- Thay đổi ratio hoặc exclusion tạo DielineSpec version mới.
- Physical validation có quyền supersede baseline.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Không có fold geometry cho đến khi nhà in xác nhận | Bị loại vì chặn toàn bộ deterministic core. |
| Hard-code pixel coordinates | Bị loại vì không portable giữa DPI/size và khó audit. |
| Cho agent tự suy luận fold lines | Bị loại vì geometry không deterministic. |
| Dùng equal thirds | Bị loại vì không phù hợp reference/focal center panel. |

## Consequences

### Positive

- Có source of truth rõ.
- Templates scale theo physical geometry.
- Dễ unit test fold intersection.
- Có đường cập nhật sau mockup.

### Negative / trade-offs

- Baseline có thể sai với vật liệu/khuôn thật.
- Fold exclusion 2 mm là engineering guardrail, không phải industry universal.
- Thay profile có thể làm golden images thay đổi.

## Implementation impact

- Dieline loader validate folds ordered và nằm trong canvas.
- Panel coverage phải đúng total width/height với tolerance.
- Geometry functions dùng float tolerance hoặc Decimal khi cần.
- Manifest lưu `dieline_version` và snapshot hash.
- Internal technical overlay render folds; final output không render overlay.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Fold/panel unit tests pass cho cả hai size.
- Critical bbox giao exclusion bị reject.
- Artwork bbox crossing fold vẫn có thể pass nếu non-critical.
- Không có module nào tự tính ratio khác config.
- Profile snapshot đủ để reproduce layout.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Physical fold lệch | Mockup 1:1 và version profile mới. |
| Developer hiểu exclusion là logo clear-space | Documentation phân biệt technical fold guardrail và brand rule. |
| Floating-point edge errors | Tolerance, property tests và boundary fixtures. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Kết quả physical fold test.
- Nhà in cung cấp dieline/cut tolerance chính thức.
- Vật liệu hoặc packaging structure thay đổi.

## Rollback / migration strategy

Tạo `full_spread_v3` thay vì sửa v2; re-render project mới bằng profile mới, giữ run cũ bất biến.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
