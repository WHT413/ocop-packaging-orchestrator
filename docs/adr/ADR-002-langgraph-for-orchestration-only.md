---
id: ADR-002
title: "LangGraph chỉ quản lý orchestration; business rules nằm ngoài graph"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-002: LangGraph chỉ quản lý orchestration; business rules nằm ngoài graph

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Workflow state machine, routing, checkpoint, retry và human interrupt. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-001, ADR-003, ADR-013 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Workflow cần conditional routing, checkpoint, bounded retry, human approval và resume theo `run_id`. LangGraph phù hợp với stateful orchestration, nhưng nếu geometry, scoring, validation hoặc rendering logic được viết trực tiếp trong graph node, business rules sẽ bị khóa vào framework và khó unit test.

Các quy tắc như fold intersection, logo count, text overflow và QR decode phải tái sử dụng được ngoài orchestration: CLI command riêng, test suite, batch evaluation hoặc future API. Chúng cũng phải deterministic và không phụ thuộc graph history.

## Decision drivers

- Giữ LangGraph có thể thay thế mà không viết lại deterministic core.
- Cho phép unit test rules như pure functions.
- Tách workflow failure semantics khỏi domain validity.
- Hỗ trợ resume/human interrupt mà không để graph trở thành business layer.

## Decision

LangGraph được dùng từ Phase 2 cho **orchestration only**: quản lý state transition, routing, checkpoint, retry budget, interrupt/resume và node execution order.

Mỗi graph node gọi application service hoặc engine function đã được typed. Geometry, validation, candidate generation, scoring, rendering, QA và persistence rules không được implement trực tiếp trong `graph.py` hoặc routing expressions.

## Quy tắc bắt buộc

- `graph.py` chỉ khai báo nodes, edges, state và routing.
- Node body phải mỏng, gọi service và chuyển đổi error thành workflow status.
- Domain error có structured code; graph không parse message string để route.
- Graph state lưu references/metadata, không nhét binary artifact.
- Side-effect node có idempotency key và checkpoint sau thành công.
- Không dùng LLM để quyết định routing khi deterministic condition tồn tại.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Custom finite-state machine hoàn toàn | Có thể dùng nhưng baseline chọn LangGraph vì checkpoint/interrupt tooling; vẫn giữ khả năng thay thế nhờ service boundaries. |
| Đưa toàn bộ logic vào graph nodes | Bị loại vì coupling, khó test và khó tái sử dụng. |
| Agent tự quyết định next step | Bị loại vì routing không reproducible và dễ tạo unbounded loop. |
| Workflow engine phân tán ngay từ đầu | Bị loại vì scope nhỏ và tăng vận hành. |

## Consequences

### Positive

- Workflow dễ quan sát và resume.
- Deterministic core test độc lập framework.
- Có thể thay LangGraph bằng custom FSM nếu dependency trở thành rủi ro.
- Routing rule rõ, auditable và bounded.

### Negative / trade-offs

- Cần thêm application service layer và mapping code.
- Developers phải hiểu ranh giới giữa domain failure và workflow failure.
- Checkpoint schema cần versioning cẩn thận.

## Implementation impact

- Phase 1 không cần LangGraph; hoàn thiện deterministic core trước.
- Phase 2 tạo `PackagingState` TypedDict/Pydantic model với schema version.
- Node wrapper ghi start/success/failure event và latency.
- Error mapping dùng enum/code như `NEEDS_INPUT`, `FAILED_LAYOUT`, `FAILED_QA`.
- Graph tests dùng mock services; service tests không import LangGraph.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- `engine/` và `domain/` không import LangGraph.
- Graph node trung bình chỉ orchestration, không chứa geometry calculation.
- Routing dựa trên typed status/constraint summary.
- Crash/resume E2E không gọi lặp side effect đã checkpoint.
- Core pipeline có thể chạy trực tiếp trong test không cần graph.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Graph state trở thành god object | Chỉ lưu state cần routing và artifact refs; version schema. |
| Node wrapper che mất lỗi gốc | Giữ structured error details và causal exception trong logs. |
| Framework lock-in qua annotations/checkpointer | Cô lập integration trong `application/orchestration/`. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- LangGraph không đáp ứng checkpoint durability hoặc operational needs.
- Workflow trở nên tuyến tính và custom FSM đơn giản hơn.
- Cần distributed workflow engine do volume/SLA.

## Rollback / migration strategy

Thay graph adapter bằng FSM/queue orchestrator, giữ nguyên application services, state contract và error codes.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
