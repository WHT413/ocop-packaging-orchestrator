from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ocop_pack.agents.design_planner.agent import (
    build_planner_input,
    default_prompts,
    planner_input_hash,
)
from ocop_pack.application.ports.planner import PlannerRequest
from ocop_pack.orchestration.runner import WorkflowRunner
from ocop_pack.orchestration.status import RunStatus
from ocop_pack.provenance.models import ProviderContext
from ocop_pack.providers.common.errors import ProviderSchemaError
from ocop_pack.providers.planner.openai_compatible import OpenAICompatiblePlannerProvider


def _valid_plan_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "design-plan.v2",
        "visual_direction": "warm premium honey packaging",
        "palette": ["warm amber", "golden brown", "soft ivory"],
        "decorative_motifs": ["honeycomb geometry", "wildflowers"],
        "artwork_density": "balanced",
        "negative_space_intent": "balanced",
        "creative_assumptions": [],
        "conflicts_or_unsupported_preferences": [],
        "artwork_concepts": [
            {
                "concept_id": "A01",
                "description": "decorative honey-inspired background",
                "prompt": "amber glow, honeycomb geometry, wildflowers, decorative artwork layer",
                "negative_prompt": "no letters, no numbers, no symbols, no marks, no codes",
                "artwork_strategy": "softened_full_background",
            }
        ],
        "layout_intents": [
            {
                "panel_strategy": "center_lockup_balanced_sides",
                "side_text_mode": "mixed",
                "artwork_strategy": "softened_full_background",
                "panel_roles": "center_primary_left_info_right_traceability",
                "content_hierarchy": "title_first",
                "title_block_intent": "hero_label_card",
                "info_block_intent": "side_label_cards",
                "protected_zone_strategy": "guard_all_critical_text",
                "contrast_strategy": "semi_opaque_warm_scrims",
            }
        ],
        "prohibited_content": ["text", "logo", "QR"],
        "rationale": "Brief reflected in safe visual fields only.",
    }
    payload.update(overrides)
    return payload


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _planner_request(example_project) -> PlannerRequest:
    prompts = default_prompts()
    planner_input = build_planner_input(example_project)
    return PlannerRequest(
        planner_input=planner_input,
        prompt_id="design_planner",
        prompt_version="v1",
        prompt_hash="test-prompt-hash",
        input_hash=planner_input_hash(planner_input, prompts),
        model_config_payload={"temperature": 0},
    )


def test_openai_planner_schema_error_reports_validation_location(
    monkeypatch: pytest.MonkeyPatch, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")

    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": "design-plan.v1",
                            "visual_direction": "warm botanical premium tea",
                            "palette": ["#0F5132", "#F7E7B7"],
                            "artwork_concepts": [
                                {
                                    "concept_id": "A01",
                                    "description": "tea leaves background",
                                    "prompt": "botanical tea leaves background",
                                    "negative_prompt": "no text, no logos",
                                    "artwork_strategy": "unsupported_strategy",
                                }
                            ],
                            "layout_intents": [],
                            "rationale": "Pick a calm botanical direction.",
                        }
                    )
                }
            }
        ],
    }

    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    provider = OpenAICompatiblePlannerProvider()

    with pytest.raises(ProviderSchemaError) as exc_info:
        provider.create_design_plan(
            _planner_request(example_project),
            ProviderContext(run_id="run", thread_id="run", node="plan_design"),
        )

    message = str(exc_info.value)
    assert "planner returned invalid schema" in message
    assert "artwork_concepts.0.artwork_strategy" in message
    assert "layout_intents" in message
    assert "raw_response_hash=" in message


def test_openai_planner_accepts_markdown_wrapped_json(
    monkeypatch: pytest.MonkeyPatch, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")
    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [
            {"message": {"content": "```json\n" + json.dumps(_valid_plan_payload()) + "\n```"}}
        ],
    }
    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    result = OpenAICompatiblePlannerProvider().create_design_plan(
        _planner_request(example_project),
        ProviderContext(run_id="run", thread_id="run", node="plan_design"),
    )

    assert result.design_plan.schema_version == "design-plan.v2"
    assert "honeycomb geometry" in result.design_plan.decorative_motifs


def test_openai_planner_rejects_trailing_prose(
    monkeypatch: pytest.MonkeyPatch, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")
    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [{"message": {"content": json.dumps(_valid_plan_payload()) + "\nDone."}}],
    }
    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    with pytest.raises(ProviderSchemaError, match="trailing prose"):
        OpenAICompatiblePlannerProvider().create_design_plan(
            _planner_request(example_project),
            ProviderContext(run_id="run", thread_id="run", node="plan_design"),
        )


def test_openai_planner_rejects_stale_v1_schema_version(
    monkeypatch: pytest.MonkeyPatch, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")
    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps(_valid_plan_payload(schema_version="design-plan.v1"))
                }
            }
        ],
    }
    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    with pytest.raises(ProviderSchemaError) as exc_info:
        OpenAICompatiblePlannerProvider().create_design_plan(
            _planner_request(example_project),
            ProviderContext(run_id="run", thread_id="run", node="plan_design"),
        )

    assert "schema_version" in str(exc_info.value)


def test_openai_planner_rejects_truncated_json(
    monkeypatch: pytest.MonkeyPatch, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")
    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [{"message": {"content": '{"schema_version"'}}],
    }
    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    with pytest.raises(ProviderSchemaError, match="invalid JSON"):
        OpenAICompatiblePlannerProvider().create_design_plan(
            _planner_request(example_project),
            ProviderContext(run_id="run", thread_id="run", node="plan_design"),
        )


def test_workflow_records_planner_schema_failure_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path, example_project
) -> None:
    monkeypatch.setenv("OCOP_PLANNER_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_PLANNER_MODEL", "cx/gpt-5.5")
    monkeypatch.setenv("OCOP_PLANNER_BASE_URL", "https://planner.invalid/v1")
    monkeypatch.setenv("OCOP_PLANNER_API_KEY", "test-key")

    provider_payload = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": "design-plan.v1",
                            "visual_direction": "warm botanical premium tea",
                            "palette": ["#0F5132", "#F7E7B7"],
                            "artwork_concepts": [],
                            "layout_intents": [],
                            "rationale": "Pick a calm botanical direction.",
                        }
                    )
                }
            }
        ],
    }

    monkeypatch.setattr(
        "ocop_pack.providers.planner.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(provider_payload),
    )

    state = WorkflowRunner(tmp_path, online=True).start(
        Path("examples/projects/tea_basic/project.yaml"), "run"
    )

    assert state["status"] == RunStatus.PLANNING_FAILED
    assert state["errors"]
    assert state["errors"][-1].code == "PROVIDER_SCHEMA"
    assert "artwork_concepts" in state["errors"][-1].message
