"""Provider selection; credentials and compatible endpoints stay environment-only."""

from cayu import ChatCompletionsProvider, OpenAIProvider, ScriptedModelProvider

from configuration.settings import configured_api_key, configured_base_url, configured_provider_name


class UnconfiguredProvider(ScriptedModelProvider):
    def __init__(self, *, name, credential_name):
        super().__init__([], name=name)
        self.credential_name = credential_name

    def preflight_model_target(self, *, model):
        raise RuntimeError(f"Set {self.credential_name}; no paid call was dispatched")


def configured_provider():
    base_url = configured_base_url()
    provider_name = configured_provider_name()
    key = configured_api_key()
    if not key:
        return UnconfiguredProvider(
            name=provider_name,
            credential_name="CAYU_API_KEY" if base_url else "OPENAI_API_KEY",
        )
    if base_url:
        return ChatCompletionsProvider(
            name=provider_name,
            api_key=key,
            base_url=base_url,
            timeout_s=90,
        )
    # The browser preview streams independently. Deliver final text together so
    # SQLite-backed presentation does not persist hundreds of tiny text chunks.
    return OpenAIProvider(name="openai", api_key=key, timeout_s=90, streaming=False)


def validate_run_configuration(app, agent_name):
    agent = next(a for a in app.describe().agents if a.name == agent_name)
    app.get_provider(agent.resolved_provider).preflight_model_target(model=agent.model)
