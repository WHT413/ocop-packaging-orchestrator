# Architecture Decision Records — ocop-packaging-orchestrator

Thư mục này chứa 15 ADR được tách từ **OCOP Packaging Agent Orchestrator — System Design Document v2.0** và mở rộng thành decision records có thể dùng trực tiếp trong repository.

## Quy ước trạng thái

- `Proposed`: đang review.
- `Accepted`: đã chấp thuận và là baseline hiện hành.
- `Superseded`: đã được ADR khác thay thế.
- `Deprecated`: không còn áp dụng cho implementation mới nhưng giữ để audit.
- `Rejected`: đã xem xét nhưng không chấp thuận.

## Quy trình thay đổi

1. Không sửa lịch sử quyết định âm thầm.
2. Thay đổi kiến trúc/geometry/provider/output quan trọng phải tạo ADR mới hoặc cập nhật ADR cũ kèm lý do.
3. Khi supersede, liên kết ADR mới và giữ file cũ.
4. Mọi config version đã dùng trong finalized run phải tiếp tục đọc/reproduce được.

## Index

| ADR | Decision | Status | File |
|---|---|---|---|
| ADR-001 | Sử dụng modular monolith thay vì microservices | Accepted | [ADR-001-modular-monolith-over-microservices.md](./ADR-001-modular-monolith-over-microservices.md) |
| ADR-002 | LangGraph chỉ quản lý orchestration; business rules nằm ngoài graph | Accepted | [ADR-002-langgraph-for-orchestration-only.md](./ADR-002-langgraph-for-orchestration-only.md) |
| ADR-003 | Giới hạn baseline ở hai agent: Design Planner và Visual Critic | Accepted | [ADR-003-two-bounded-agents-only.md](./ADR-003-two-bounded-agents-only.md) |
| ADR-004 | Chỉ hỗ trợ hai full-spread size cố định trong baseline | Accepted | [ADR-004-two-fixed-full-spread-sizes.md](./ADR-004-two-fixed-full-spread-sizes.md) |
| ADR-005 | Dùng panel ratio 22/56/22 và fold bands 5/90/5 làm baseline cấu hình được | Accepted | [ADR-005-configurable-panel-and-fold-ratios.md](./ADR-005-configurable-panel-and-fold-ratios.md) |
| ADR-006 | Không có glue flap hoặc outside region trong baseline | Accepted | [ADR-006-no-glue-flap-or-outside-region.md](./ADR-006-no-glue-flap-or-outside-region.md) |
| ADR-007 | Logo là immutable asset; tối đa 5 logo hiển thị tính cả OCOP | Accepted | [ADR-007-immutable-logos-max-five.md](./ADR-007-immutable-logos-max-five.md) |
| ADR-008 | Không áp fixed logo minimum size/clear-space; dùng dynamic scoring và readability gate | Accepted | [ADR-008-dynamic-logo-sizing-and-spacing.md](./ADR-008-dynamic-logo-sizing-and-spacing.md) |
| ADR-009 | User cung cấp logo OCOP và số sao; hệ thống chỉ render deterministic | Accepted | [ADR-009-user-supplied-ocop-logo-and-star-count.md](./ADR-009-user-supplied-ocop-logo-and-star-count.md) |
| ADR-010 | Dùng sRGB baseline; không triển khai color-managed prepress | Accepted | [ADR-010-srgb-without-color-management.md](./ADR-010-srgb-without-color-management.md) |
| ADR-011 | External deliverables chỉ gồm PNG và PDF | Accepted | [ADR-011-png-and-pdf-external-deliverables.md](./ADR-011-png-and-pdf-external-deliverables.md) |
| ADR-012 | Cho phép internal SVG/scene graph nhưng không coi là deliverable | Accepted | [ADR-012-internal-scene-graph-svg.md](./ADR-012-internal-scene-graph-svg.md) |
| ADR-013 | Bắt buộc human approval trước final export | Accepted | [ADR-013-human-approval-before-export.md](./ADR-013-human-approval-before-export.md) |
| ADR-014 | API-first cho image/vision provider trong pilot | Accepted | [ADR-014-api-first-image-and-vision-providers.md](./ADR-014-api-first-image-and-vision-providers.md) |
| ADR-015 | Physical fold test là production gate bắt buộc | Accepted | [ADR-015-physical-fold-test-production-gate.md](./ADR-015-physical-fold-test-production-gate.md) |

## Phase mapping

- **Phase 1 — Deterministic Core:** ADR-001, 004, 005, 006, 007, 008, 009, 010, 011, 012, 015.
- **Phase 2 — Orchestration & CLI:** ADR-002, 013.
- **Phase 3–4 — Planner, Artwork, Critic:** ADR-003, 014.
- **Phase 5 — Production hardening & pilot:** tất cả ADR, đặc biệt ADR-013 và ADR-015.

## Local development baseline

- Repository: `ocop-packaging-orchestrator`
- Python: 3.12
- Package manager: `uv`
- Local metadata/test persistence: SQLite
- Local artifacts: filesystem
- Phase 1 không gọi LLM/image/vision provider
