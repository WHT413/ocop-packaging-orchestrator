---
id: ADR-013
title: "Bắt buộc human approval trước final export"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-013: Bắt buộc human approval trước final export

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Accountability, CLI workflow và export gate. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-003, ADR-009, ADR-011, ADR-015 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Hệ thống có creative model output, không tự xác minh legal claims/OCOP certification và chưa có certified print dieline. Deterministic QA chỉ bắt lỗi kỹ thuật như fold intersection, overflow, logo transform và QR decode; nó không thay thế đánh giá thẩm mỹ, nội dung hoặc trách nhiệm pháp lý.

Do đó autonomous export không phù hợp production pilot.

## Decision drivers

- Giữ con người chịu trách nhiệm final decision.
- Bắt lỗi semantic/aesthetic ngoài automated QA.
- Ngăn model output được dùng ngay mà không review.
- Tạo audit record gắn với exact candidate/hash.

## Decision

Sau khi candidate được render và deterministic QA pass, workflow chuyển `WAITING_APPROVAL`. Operator/designer phải approve một candidate qua CLI trước khi `export_bundle` tạo/finalize external PNG/PDF.

ApprovalRecord gắn với run ID, candidate ID, LayoutManifest hash, QA report hash, timestamp và reviewer identifier. Nếu input/layout thay đổi, approval cũ không còn hợp lệ.

## Quy tắc bắt buộc

- QA critical fail không được đưa sang approval.
- Approve exact candidate/hash, không approve “run chung chung”.
- Reject cần reason.
- Export verify approval hash match current manifest.
- Không có auto-approve baseline.
- Approval không đồng nghĩa legal/printer certification.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Auto-export khi QA pass | Bị loại vì QA không đánh giá legal/aesthetic. |
| Visual Critic là final approver | Bị loại vì model không accountable và có thể sai. |
| Approval ngoài hệ thống không ghi record | Bị loại vì mất audit lineage. |
| Web UI approval ngay từ đầu | Bị loại vì CLI-only scope; CLI interrupt đủ cho pilot. |

## Consequences

### Positive

- Accountability rõ.
- Ngăn lỗi semantic/aesthetic phát hành tự động.
- Có traceability.
- Phù hợp bounded autonomy.

### Negative / trade-offs

- Tăng manual step và latency.
- CLI có thể bất tiện khi volume lớn.
- Cần identity/record handling tối thiểu.

## Implementation impact

- CLI commands `inspect`, `approve`, `reject`, `export`.
- Phase 1 có thể dùng manual candidate selection; Phase 2 thêm graph interrupt/resume.
- Approval persisted SQLite/local ở dev, PostgreSQL ở future production.
- Final path chỉ atomic finalize sau approval verification.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Export không chạy khi thiếu approval.
- Approval invalid khi manifest hash đổi.
- ApprovalRecord tồn tại cho 100% final runs.
- Reject không tạo final artifacts.
- CLI hiển thị QA, logo count, stars và preview paths.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Reviewer approve nhầm | Hiển thị candidate ID/hash/preview rõ và confirmation. |
| Shared identity yếu ở CLI | Pilot ghi reviewer string; production mở rộng authentication/RBAC. |
| Bottleneck manual | Chỉ xem xét auto-approve sau labeled evidence và risk review. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Volume khiến manual approval không đáp ứng SLA.
- Có validated quality/legal automation và risk acceptance.
- Web UI/RBAC vào scope.

## Rollback / migration strategy

Không nên bỏ gate trực tiếp; nếu cần batch approval, vẫn tạo explicit ApprovalRecord cho từng manifest.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
