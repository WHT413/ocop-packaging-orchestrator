from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ocop_pack.agents.visual_critic.prompts.v1 import PROMPTS


@dataclass(frozen=True)
class CriticPromptDescriptor:
    prompt_id: str
    version: str
    schema_version: str
    sha256: str
    content: str


def load_prompt(name: str, version: str = "v1") -> CriticPromptDescriptor:
    content = PROMPTS[(name, version)]
    return CriticPromptDescriptor(
        prompt_id=f"visual_critic.{name}",
        version=version,
        schema_version="v1",
        sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
    )


def default_prompts() -> list[CriticPromptDescriptor]:
    return [load_prompt("system"), load_prompt("task")]
