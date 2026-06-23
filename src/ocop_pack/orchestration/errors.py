from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowError(BaseModel):
    code: str
    message: str
    node: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowException(Exception):
    def __init__(self, error: WorkflowError) -> None:
        super().__init__(error.message)
        self.error = error
