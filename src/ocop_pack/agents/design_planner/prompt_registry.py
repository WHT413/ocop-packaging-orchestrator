from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files


@dataclass(frozen=True)
class PromptDescriptor:
    prompt_id: str
    version: str
    schema_version: str
    sha256: str
    content: str


def load_prompt(name: str, version: str = "v1") -> PromptDescriptor:
    file_name = f"{name}.{version}.md"
    content = (
        files("ocop_pack.agents.design_planner.prompts")
        .joinpath(file_name)
        .read_text(encoding="utf-8")
    )
    return PromptDescriptor(
        prompt_id=f"design_planner.{name}",
        version=version,
        schema_version="design-plan.v1",
        sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
    )
