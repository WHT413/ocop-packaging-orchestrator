from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_URL = "sqlite:///data/ocop_packaging.db"
DEFAULT_RUNS_DIR = Path("runs")


def _blank_to_none(value: str | None) -> str | None:
    return None if value == "" else value


class PlannerSettings(BaseSettings):
    """
    Loads configuration for the design planner provider.

    Values use the ``OCOP_PLANNER_`` environment prefix and are read from
    ``.env`` when present. These settings control which planner provider is
    used, how it is reached, and which prompt/schema versions are expected.

    Attributes:
        provider: Planner provider identifier. Supported values are ``mock`` and
            ``openai-compatible``.
        model: Model name passed to the planner provider.
        base_url: Optional API base URL for compatible online providers.
        api_key: Optional secret API key for compatible online providers.
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum retry attempts for planner calls.
        temperature: Sampling temperature used for planner generation.
        max_output_tokens: Maximum number of output tokens requested.
        prompt_id: Identifier of the planner prompt template.
        prompt_version: Version of the planner prompt template.
        schema_version: Expected design-plan schema version.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_PLANNER_", env_file=".env", extra="ignore")

    provider: str = "mock"
    model: str = "mock-design-planner-v1"
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout_seconds: float = 60
    max_retries: int = 1
    temperature: float = 0
    max_output_tokens: int = 2000
    prompt_id: str = "design_planner"
    prompt_version: str = "v1"
    schema_version: str = "design-plan.v1"

    @field_validator("provider")
    @classmethod
    def provider_allowlist(cls, value: str) -> str:
        if value not in {"mock", "openai-compatible"}:
            raise ValueError("unsupported planner provider")
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def empty_base_url_as_none(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class ImageSettings(BaseSettings):
    """
    Loads configuration for artwork image generation.

    Values use the ``OCOP_IMAGE_`` environment prefix and are read from ``.env``
    when present. These settings select the image provider and define the output
    image format, target dimensions, and request limits.

    Attributes:
        provider: Image provider identifier. Supported values are ``fixture`` and
            ``openai-compatible``.
        model: Model name passed to the image provider.
        base_url: Optional API base URL for compatible online providers.
        api_key: Optional secret API key for compatible online providers.
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum retry attempts for image calls.
        default_count: Default number of artwork images to generate.
        hard_max_calls: Hard limit for image generation calls.
        output_format: Output image format, such as ``png``.
        target_width_px: Target artwork width in pixels.
        target_height_px: Target artwork height in pixels.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_IMAGE_", env_file=".env", extra="ignore")

    provider: str = "fixture"
    model: str = "fixture-artwork-v1"
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout_seconds: float = 120
    max_retries: int = 1
    default_count: int = 2
    hard_max_calls: int = 3
    output_format: str = "png"
    target_width_px: int = 1024
    target_height_px: int = 1024

    @field_validator("provider")
    @classmethod
    def provider_allowlist(cls, value: str) -> str:
        if value not in {"fixture", "openai-compatible"}:
            raise ValueError("unsupported image provider")
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def empty_base_url_as_none(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class VisionSettings(BaseSettings):
    """
    Loads configuration for the visual critic provider.

    Values use the ``OCOP_VISION_`` environment prefix and are read from
    ``.env`` when present. These settings control how contact sheets and layout
    candidates are evaluated by the visual critic.

    Attributes:
        provider: Vision provider identifier. Supported values are ``mock`` and
            ``openai-compatible``.
        model: Model name passed to the visual critic provider.
        base_url: Optional API base URL for compatible online providers.
        api_key: Optional secret API key for compatible online providers.
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum retry attempts for visual critic calls.
        prompt_version: Version of the visual critic prompt template.
        schema_version: Expected visual critic response schema version.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_VISION_", env_file=".env", extra="ignore")

    provider: str = "mock"
    model: str = "mock-critic-v1"
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout_seconds: float = 60
    max_retries: int = 1
    prompt_version: str = "v1"
    schema_version: str = "v1"

    @field_validator("provider")
    @classmethod
    def provider_allowlist(cls, value: str) -> str:
        if value not in {"mock", "openai-compatible"}:
            raise ValueError("unsupported vision provider")
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def empty_base_url_as_none(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class RevisionSettings(BaseSettings):
    """
    Loads configuration for artwork or layout revision providers.

    Values use the ``OCOP_REVISION_`` environment prefix and are read from
    ``.env`` when present. These settings select the revision provider and define
    the connection and retry behavior for revision calls.

    Attributes:
        provider: Revision provider identifier. Supported values are ``fixture``
            and ``openai-compatible``.
        model: Model name passed to the revision provider.
        base_url: Optional API base URL for compatible online providers.
        api_key: Optional secret API key for compatible online providers.
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum retry attempts for revision calls.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_REVISION_", env_file=".env", extra="ignore")

    provider: str = "fixture"
    model: str = "fixture-editor-v1"
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout_seconds: float = 120
    max_retries: int = 1

    @field_validator("provider")
    @classmethod
    def provider_allowlist(cls, value: str) -> str:
        if value not in {"fixture", "openai-compatible"}:
            raise ValueError("unsupported revision provider")
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def empty_base_url_as_none(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class WorkflowBudgetSettings(BaseSettings):
    """
    Loads workflow budget and candidate-selection settings.

    Values use the ``OCOP_`` environment prefix and are read from ``.env`` when
    present. The settings provide the default limits used by ``WorkflowRunner``
    when creating a ``BudgetPolicy`` for visual critic calls, revision cycles,
    image edits, and contact sheet candidate selection.

    The class is named ``WorkflowBudgetSettings`` instead of
    ``Phase4BudgetSettings`` because the values describe workflow-level budget
    controls. The previous name tied the class to an implementation phase, while
    the new name describes its current responsibility more clearly.

    Attributes:
        max_vision_calls: Maximum visual critic calls allowed for a run.
        max_revision_count: Maximum revision cycles allowed for a run.
        max_image_edit_calls: Maximum image edit calls allowed for a run.
        contact_sheet_top_k: Number of top candidates to include in contact sheets.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_", env_file=".env", extra="ignore")

    max_vision_calls: int = 1
    max_revision_count: int = 1
    max_image_edit_calls: int = 1
    contact_sheet_top_k: int = 6


class ExecutionSettings(BaseSettings):
    """
    Loads runtime execution flags for the workflow.

    Values use the ``OCOP_`` environment prefix and are read from ``.env`` when
    present. These settings decide whether the workflow may use online providers
    instead of deterministic mock or fixture providers.

    Attributes:
        online: Whether online providers are enabled for execution.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_", env_file=".env", extra="ignore")

    online: bool = False

    @property
    def use_online_providers(self) -> bool:
        return self.online


class RealAITestSettings(BaseSettings):
    """
    Loads flags for tests that exercise real AI providers.

    Values use the ``OCOP_E2E_`` environment prefix and are read from ``.env``
    when present. These settings keep real-provider tests opt-in so normal test
    runs do not depend on external services or credentials.

    Attributes:
        real_ai: Whether end-to-end tests may call real AI providers.

    """

    model_config = SettingsConfigDict(env_prefix="OCOP_E2E_", env_file=".env", extra="ignore")

    real_ai: bool = False
