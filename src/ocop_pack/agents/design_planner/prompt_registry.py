from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ocop_pack.agents.design_planner.prompts.v1 import PROMPTS


@dataclass(frozen=True)
class PromptDescriptor:
    prompt_id: str
    version: str
    schema_version: str
    sha256: str
    content: str


def load_prompt(name: str, version: str = "v2") -> PromptDescriptor:
    content = PROMPTS[(name, version)]
    return PromptDescriptor(
        prompt_id=f"design_planner.{name}",
        version=version,
        schema_version="design-plan.v2",
        sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
    )
