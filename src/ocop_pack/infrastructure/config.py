from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_URL = "sqlite:///data/ocop_packaging.db"
DEFAULT_RUNS_DIR = Path("runs")


class PlannerSettings(BaseSettings):
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


class ImageSettings(BaseSettings):
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

    @field_validator("provider")
    @classmethod
    def provider_allowlist(cls, value: str) -> str:
        if value not in {"fixture", "openai-compatible"}:
            raise ValueError("unsupported image provider")
        return value


class ExecutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCOP_", env_file=".env", extra="ignore")

    online: bool = False

    @property
    def use_online_providers(self) -> bool:
        return self.online


class RealAITestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCOP_E2E_", env_file=".env", extra="ignore")

    real_ai: bool = False
