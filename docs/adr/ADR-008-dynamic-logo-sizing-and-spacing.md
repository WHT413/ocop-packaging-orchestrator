---
id: ADR-008
title: "Không áp fixed logo minimum size/clear-space; dùng dynamic scoring và readability gate"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-008: Không áp fixed logo minimum size/clear-space; dùng dynamic scoring và readability gate

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Logo sizing, separation và candidate selection. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-007, ADR-005, ADR-013 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

User không yêu cầu min size hoặc clear space brand-level cố định và ưu tiên output đẹp. Các logo có shape, padding và visual weight khác nhau; một con số universal có thể quá chặt với logo này nhưng quá lỏng với logo khác.

Tuy nhiên “không có fixed min size” không được hiểu là có thể thu nhỏ vô hạn. Engine vẫn cần technical guardrail để đảm bảo logo nhìn thấy, có pixel density đủ và không dính nhau/fold.

## Decision drivers

- Giữ composition linh hoạt.
- Không giả mạo brand guideline không được cung cấp.
- Ngăn logo unreadable.
- Cho phép optimize theo actual logo geometry/contrast.

## Decision

Baseline không khai báo một official `min_width_mm` hoặc `clear_space_ratio` dùng chung cho mọi logo. Candidate generator sinh scale/spacing variants trong region khả dụng; scorer áp penalty cho logo quá nhỏ, thiếu separation, low contrast hoặc dominance không phù hợp.

Một candidate chỉ hợp lệ nếu vượt technical readability gate cấu hình được. Nếu không candidate nào đạt gate, run trả `TOO_MANY_LOGOS_FOR_READABLE_LAYOUT` hoặc `NO_VALID_LAYOUT`. Technical gate không được mô tả là brand compliance.

## Quy tắc bắt buộc

- Không hard-code một brand rule universal.
- Logo separation kiểm tra overlap, visual gap và fold avoidance.
- Backplate trung tính có thể dùng để tăng contrast.
- Scale range phụ thuộc panel/role/asset aspect ratio.
- Primary/OCOP không được nhỏ hơn partner theo role policy trừ explicit exception.
- Readability gate versioned trong scoring config.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Fixed min width cho mọi logo | Bị loại vì logo geometry khác nhau và không có guideline nguồn. |
| Không có gate nào | Bị loại vì engine sẽ thu nhỏ vô hạn. |
| Vision model tự đánh giá duy nhất | Bị loại vì không deterministic và khó test. |
| Hard clear-space ratio từ một brand guideline bên ngoài | Bị loại vì không áp dụng phổ quát cho asset của user. |

## Consequences

### Positive

- Flexible layout đúng mục tiêu sản phẩm.
- Không áp tiêu chuẩn giả.
- Có failure rõ thay vì output kém.
- Có thể tune bằng pilot telemetry.

### Negative / trade-offs

- Scoring/readability threshold cần calibration.
- Không thể tuyên bố tuân thủ guideline của từng brand.
- Một số logo phức tạp có thể cần manual review.

## Implementation impact

- Scoring config chứa min rendered pixel height, contrast threshold, gap token và dominance ratio như technical parameters.
- Tách hard validity (không overlap/fold) và soft aesthetics.
- Log score breakdown cho từng logo cluster.
- Golden dataset gồm logo ngang, dọc, tròn, có padding và low contrast.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Không logo nào bị scale dưới technical threshold trong candidate pass.
- No-overlap và fold avoidance luôn là hard constraints.
- Scorer trả explainable penalties.
- 5-logo stress fixture fail closed nếu không readable.
- Documentation không gọi threshold là official brand clear space.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Threshold arbitrary | Pilot calibration, versioning và designer review. |
| Vision/scorer bias theo shape | Diverse golden assets và role-aware normalization. |
| Backplate làm sai brand feel | Chỉ neutral backplate và cho phép disable per asset. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- User cung cấp official brand guideline.
- Pilot data cho thấy threshold quá chặt/lỏng.
- Có automated legibility metric tốt hơn được validated.

## Rollback / migration strategy

Pin scoring policy version theo run; thay đổi threshold chỉ áp dụng run mới hoặc explicit re-evaluation.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
