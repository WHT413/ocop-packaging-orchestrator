---
id: ADR-001
title: "Sử dụng modular monolith thay vì microservices"
status: Accepted
date: 2026-06-23
project: ocop-packaging-orchestrator
owners: "Project team; architecture changes require repository review"
source: "OCOP Packaging Agent Orchestrator — System Design Document v2.0"
---

# ADR-001: Sử dụng modular monolith thay vì microservices

## Metadata

| Thuộc tính | Giá trị |
|---|---|
| Status | **Accepted** |
| Ngày quyết định | 2026-06-23 |
| Phạm vi | Application architecture, deployment boundary và module ownership. |
| Decision owner | Project team; architecture changes require repository review |
| Related ADRs | ADR-002, ADR-003, ADR-014 |
| Nguồn baseline | OCOP Packaging Agent Orchestrator — System Design Document v2.0 |

## Context

Hệ thống hiện chỉ hỗ trợ hai full-spread size, một packaging structure, CLI workflow và số lượng job nhỏ trong giai đoạn MVP/production pilot. Các thành phần geometry, candidate generation, rendering, QA và orchestration có quan hệ dữ liệu chặt chẽ; chúng cùng sử dụng `ProjectSpec`, `DielineSpec`, `LayoutManifest` và artifact lineage.

Tách từng node thành microservice ở thời điểm này sẽ buộc dự án phải giải quyết service discovery, distributed tracing, network retry, contract versioning, message ordering, partial failure và distributed transaction trước khi có bằng chứng về nhu cầu scale. Độ phức tạp vận hành sẽ lớn hơn giá trị nhận được.

Dự án vẫn cần modularity để có thể thay renderer, persistence hoặc provider. Vì vậy lựa chọn không phải là “một file monolith”, mà là modular monolith với boundaries rõ giữa domain, engine, application và infrastructure.

## Decision drivers

- Giảm chi phí vận hành và thời gian triển khai Phase 1–5.
- Giữ transaction, checkpoint và artifact lineage trong một process boundary.
- Tạo codebase dễ test bằng pure function và repository abstraction.
- Không chặn khả năng tách worker/provider ở tương lai.
- Tránh distributed-system failure modes khi volume chưa chứng minh nhu cầu.

## Decision

Repository triển khai một **modular monolith Python 3.12**. CLI/application, orchestration, domain models, deterministic engine và infrastructure adapters nằm trong cùng repository và cùng deployable unit ở baseline.

Module giao tiếp qua typed interfaces; domain và engine không phụ thuộc trực tiếp vào SQLAlchemy, filesystem implementation, LangGraph hoặc provider SDK. Phase 1 dùng `uv` làm package manager và SQLite/local filesystem cho local development, nhưng persistence vẫn được đặt sau repository interfaces.

## Quy tắc bắt buộc

- Một deployable application container/process ở baseline.
- Không tạo network API giữa các module nội bộ.
- Domain layer không import infrastructure hoặc orchestration framework.
- Side effects đi qua adapter/repository interface.
- Module boundary phải được enforce bằng import rules hoặc architecture tests.
- Chỉ tách service khi có telemetry về concurrency, isolation hoặc independent scaling.

## Alternatives considered

| Phương án | Lý do không chọn |
|---|---|
| Microservices theo từng workflow node | Bị loại vì tạo network hops, contract duplication và distributed failure modes trong khi load mục tiêu chỉ 2–5 active jobs. |
| Serverless function cho từng node | Bị loại vì cold start, artifact transfer, local rendering dependency và checkpoint complexity. |
| Một script monolith không phân lớp | Bị loại vì khó test, provider lock-in và không có đường nâng cấp persistence/deployment. |
| Plugin-based distributed architecture ngay từ đầu | Bị loại vì abstraction cost cao và chưa có extension ecosystem thực tế. |

## Consequences

### Positive

- Debug và local development đơn giản.
- Transaction và idempotency dễ kiểm soát.
- Giảm boilerplate deployment, networking và observability.
- Cho phép refactor nhanh khi ProductSpec/DielineSpec còn đang ổn định.

### Negative / trade-offs

- Một process có blast radius lớn hơn nếu module lỗi.
- Không scale độc lập renderer và provider call ở baseline.
- Cần discipline để modular monolith không biến thành tightly coupled codebase.

## Implementation impact

- Dùng package boundaries: `domain/`, `engine/`, `application/`, `agents/`, `infrastructure/`, `cli/`.
- Tạo protocol/interface cho persistence, storage, image provider và renderer.
- Phase 1 chạy bằng Python 3.12, `uv`, SQLite và local artifact storage.
- Không thêm queue, Redis, PostgreSQL hoặc MinIO trước production hardening trừ khi có requirement mới.
- Ghi Architecture Decision Record mới trước khi tách worker/service.

## Validation và acceptance criteria

Quyết định này được xem là được triển khai đúng khi:

- Repository có một deployable unit và không có internal HTTP/RPC.
- Domain tests chạy không cần database, filesystem thật hoặc network.
- Infrastructure implementation có thể thay bằng test double.
- Architecture/import test phát hiện domain import từ infrastructure.
- Một run có thể hoàn tất trong cùng application process ở baseline.

## Risks và mitigations

| Rủi ro | Mitigation |
|---|---|
| Coupling tăng dần | Enforce module ownership, typed contracts và architecture tests. |
| Long-running image call block process | Dùng bounded timeout; chỉ tách worker khi có concurrency evidence. |
| Khó tách về sau | Giữ state contract, artifact references và idempotency key độc lập với process. |

## Revisit triggers

ADR này phải được mở lại khi có một trong các điều kiện sau:

- Sustained concurrency vượt 5 active jobs.
- Renderer hoặc provider cần scale độc lập.
- Security/compliance yêu cầu isolation process hoặc network zone.
- Deployment cadence giữa module khác biệt đáng kể.
- Một module gây resource contention không thể giải quyết bằng worker pool nội bộ.

## Rollback / migration strategy

Nếu cần scale-out, tách theo capability lớn (ví dụ rendering worker hoặc provider worker), không tách theo từng graph node. Giữ nguyên domain contracts và artifact store để migration không thay đổi ProductSpec/LayoutManifest.

## Compliance note

- Mọi thay đổi làm khác decision hoặc mandatory rules phải có ADR mới hoặc cập nhật trạng thái ADR này thành `Superseded`.
- Run đã final phải giữ nguyên config/model/artifact hash để bảo đảm reproducibility.
- Các từ **MUST**, **SHOULD**, **MAY** được hiểu theo quy ước của System Design Document v2.0.
