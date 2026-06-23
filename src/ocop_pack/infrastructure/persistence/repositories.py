from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from ocop_pack.domain.artifacts import ArtifactMetadata
from ocop_pack.domain.layout import LayoutCandidate
from ocop_pack.domain.runs import RunRecord, RunStatus
from ocop_pack.infrastructure.persistence.models import ArtifactModel, CandidateModel, RunModel


class RunRepository(Protocol):
    def create(self, run: RunRecord) -> RunRecord: ...
    def get(self, run_id: str) -> RunRecord | None: ...
    def update_status(self, run_id: str, status: RunStatus) -> None: ...


class CandidateRepository(Protocol):
    def save_many(self, run_id: str, candidates: Sequence[LayoutCandidate]) -> None: ...
    def list_by_run(self, run_id: str) -> list[LayoutCandidate]: ...


class ArtifactRepository(Protocol):
    def save(self, artifact: ArtifactMetadata) -> None: ...
    def list_by_run(self, run_id: str) -> list[ArtifactMetadata]: ...


class SqlRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, run: RunRecord) -> RunRecord:
        self.session.add(
            RunModel(
                run_id=run.run_id,
                project_id=run.project_id,
                input_hash=run.input_hash,
                dieline_version=run.dieline_version,
                status=run.status.value,
                meta=run.metadata,
            )
        )
        self.session.commit()
        return run

    def get(self, run_id: str) -> RunRecord | None:
        row = self.session.get(RunModel, run_id)
        return (
            None
            if row is None
            else RunRecord(
                run_id=row.run_id,
                project_id=row.project_id,
                input_hash=row.input_hash,
                dieline_version=row.dieline_version,
                status=RunStatus(row.status),
                metadata=row.meta,
            )
        )

    def update_status(self, run_id: str, status: RunStatus) -> None:
        row = self.session.get(RunModel, run_id)
        if row:
            row.status = status.value
            self.session.commit()


class SqlCandidateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_many(self, run_id: str, candidates: Sequence[LayoutCandidate]) -> None:
        self.session.add_all(
            [
                CandidateModel(
                    run_id=run_id, candidate_id=c.candidate_id, payload=c.model_dump(mode="json")
                )
                for c in candidates
            ]
        )
        self.session.commit()

    def list_by_run(self, run_id: str) -> list[LayoutCandidate]:
        rows = self.session.scalars(
            select(CandidateModel)
            .where(CandidateModel.run_id == run_id)
            .order_by(CandidateModel.candidate_id)
        ).all()
        return [LayoutCandidate.model_validate(r.payload) for r in rows]


class SqlArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, artifact: ArtifactMetadata) -> None:
        self.session.add(
            ArtifactModel(
                artifact_id=artifact.artifact_id,
                run_id=artifact.run_id,
                candidate_id=artifact.candidate_id,
                kind=artifact.kind,
                relative_path=artifact.relative_path,
                sha256=artifact.sha256,
                meta=artifact.metadata,
            )
        )
        self.session.commit()

    def list_by_run(self, run_id: str) -> list[ArtifactMetadata]:
        rows = self.session.scalars(
            select(ArtifactModel).where(ArtifactModel.run_id == run_id)
        ).all()
        return [
            ArtifactMetadata(
                artifact_id=r.artifact_id,
                run_id=r.run_id,
                candidate_id=r.candidate_id,
                kind=cast(Literal["png", "pdf", "overlay", "qa", "manifest"], r.kind),
                relative_path=r.relative_path,
                sha256=r.sha256,
                metadata=r.meta,
            )
            for r in rows
        ]
