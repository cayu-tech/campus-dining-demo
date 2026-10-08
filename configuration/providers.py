"""Explicit provider construction for this application."""

from cayu import (
    AnthropicProvider,
    CayuApp,
    ChatCompletionsProvider,
    GatewayProvider,
    ModelProvider,
    OpenAIProvider,
    OpenAISubscriptionProvider,
    ScriptedModelProvider,
)

from configuration.settings import (
    configured_anthropic_api_key,
    configured_gateway_api_key,
    configured_gateway_base_url,
    configured_model_override,
    configured_openai_api_key,
    configured_openrouter_api_key,
    configured_openrouter_app_title,
    configured_openrouter_http_referer,
    configured_openrouter_router_metadata_enabled,
    configured_provider_choice,
)


class _ScaffoldPlaceholderProvider(ScriptedModelProvider):
    """Credential-free placeholder rejected by every runtime entry point."""

    def __init__(self, *, name: str, setup_error: str) -> None:
        super().__init__([], name=name)
        self._setup_error = setup_error

    def preflight_model_target(self, *, model: str) -> None:
        del model
        raise RuntimeError(self._setup_error)


def configured_provider() -> ModelProvider:
    """Construct only the explicitly selected provider without dispatching it."""

    choice = configured_provider_choice()
    if choice is None:
        return _ScaffoldPlaceholderProvider(
            name="unconfigured",
            setup_error=(
                "no provider is selected; set CAYU_PROVIDER to openai, anthropic, "
                "openrouter, cayu-gateway, or openai-subscription (credentials do not select a provider)"
            ),
        )
    if choice == "openai-subscription":
        return OpenAISubscriptionProvider()
    if choice == "openai":
        api_key = configured_openai_api_key()
        return (
            OpenAIProvider(api_key=api_key)
            if api_key
            else _ScaffoldPlaceholderProvider(
                name="openai",
                setup_error="provider 'openai' is selected but OPENAI_API_KEY is not set",
            )
        )
    if choice == "cayu-gateway":
        api_key = configured_gateway_api_key()
        base_url = configured_gateway_base_url()
        if not (configured_model_override() and api_key and base_url):
            return _ScaffoldPlaceholderProvider(
                name="cayu_gateway",
                setup_error=(
                    "provider 'cayu-gateway' requires CAYU_MODEL, "
                    "CAYU_GATEWAY_API_KEY, and CAYU_GATEWAY_BASE_URL"
                ),
            )
        return GatewayProvider(api_key=api_key, base_url=base_url)
    if choice == "openrouter":
        router_metadata_enabled = configured_openrouter_router_metadata_enabled()
        model = configured_model_override()
        if not model:
            return _ScaffoldPlaceholderProvider(
                name="openrouter",
                setup_error="provider 'openrouter' requires an explicit CAYU_MODEL model slug",
            )
        api_key = configured_openrouter_api_key()
        return (
            ChatCompletionsProvider(
                name="openrouter",
                api_key=api_key,
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
                openrouter_http_referer=configured_openrouter_http_referer(),
                openrouter_app_title=configured_openrouter_app_title(),
                openrouter_router_metadata=router_metadata_enabled,
            )
            if api_key
            else _ScaffoldPlaceholderProvider(
                name="openrouter",
                setup_error=(
                    "provider 'openrouter' is selected but OPENROUTER_API_KEY is not set"
                ),
            )
        )
    api_key = configured_anthropic_api_key()
    return (
        AnthropicProvider(api_key=api_key)
        if api_key
        else _ScaffoldPlaceholderProvider(
            name="anthropic",
            setup_error="provider 'anthropic' is selected but ANTHROPIC_API_KEY is not set",
        )
    )


def validate_run_configuration(app: CayuApp, agent_name: str) -> None:
    """Run the target and adapter preflight used by live entry points."""

    manifest_agent = next(
        agent for agent in app.describe().agents if agent.name == agent_name
    )
    if manifest_agent.resolved_provider is None:
        raise RuntimeError(
            f"agent {agent_name!r} does not resolve to exactly one model provider"
        )
    provider = app.get_provider(manifest_agent.resolved_provider)
    provider.preflight_model_target(model=manifest_agent.model)
