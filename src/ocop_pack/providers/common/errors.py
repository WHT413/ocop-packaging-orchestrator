from __future__ import annotations


class ProviderError(Exception):
    code = "PROVIDER_ERROR"
    retryable = False

    def __init__(self, message: str = "provider error") -> None:
        super().__init__(message)


class ProviderTimeoutError(ProviderError):
    code = "PROVIDER_TIMEOUT"
    retryable = True


class ProviderRateLimitError(ProviderError):
    code = "PROVIDER_RATE_LIMIT"
    retryable = True


class ProviderAuthenticationError(ProviderError):
    code = "PROVIDER_AUTHENTICATION"


class ProviderSchemaError(ProviderError):
    code = "PROVIDER_SCHEMA"


class ProviderSafetyError(ProviderError):
    code = "PROVIDER_SAFETY"


class ProviderUnavailableError(ProviderError):
    code = "PROVIDER_UNAVAILABLE"
    retryable = True


class ProviderConfigurationError(ProviderError):
    code = "PROVIDER_CONFIGURATION"
