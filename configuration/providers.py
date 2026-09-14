"""OpenAI uses Cayu's public Responses adapter; no fallback provider."""

from cayu import OpenAIProvider, ScriptedModelProvider

from configuration.settings import configured_api_key


class UnconfiguredProvider(ScriptedModelProvider):
    def __init__(self):
        super().__init__([], name="openai")

    def preflight_model_target(self, *, model):
        raise RuntimeError("Set OPENAI_API_KEY; no paid call was dispatched")


def configured_provider():
    key = configured_api_key()
    if not key:
        return UnconfiguredProvider()
    # The browser preview streams independently. Deliver final text together so
    # SQLite-backed presentation does not persist hundreds of tiny text chunks.
    return OpenAIProvider(name="openai", api_key=key, timeout_s=90, streaming=False)


def validate_run_configuration(app, agent_name):
    agent = next(a for a in app.describe().agents if a.name == agent_name)
    app.get_provider(agent.resolved_provider).preflight_model_target(model=agent.model)
