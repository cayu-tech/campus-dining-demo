"""Provider selection uses explicit environment credentials and the public API."""

import asyncio
import json

import httpx
import pytest
from cayu import Message, ModelRequest

from configuration import providers
from configuration.settings import configured_api_key, configured_provider_name


@pytest.fixture(autouse=True)
def isolated_provider_environment(monkeypatch):
    monkeypatch.delenv("CAYU_BASE_URL", raising=False)
    monkeypatch.delenv("CAYU_API_KEY", raising=False)


@pytest.mark.parametrize("compatible", [False, True])
def test_presenter_forwards_only_selected_provider_environment(monkeypatch, tmp_path, compatible):
    from operations import viewer_host

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-openai-key")
    if compatible:
        monkeypatch.setenv("CAYU_BASE_URL", "https://codex-lb.cayu.ai/v1")
        monkeypatch.setenv("CAYU_API_KEY", "synthetic-cayu-key")
    observed = []

    def capture_launch(*args):
        observed.extend(args)
        raise RuntimeError("captured before Docker launch")

    monkeypatch.setattr(viewer_host, "docker", capture_launch)
    with pytest.raises(RuntimeError, match="captured before Docker launch"):
        viewer_host.start_host(tmp_path / "presenter")
    forwarded = [observed[i + 1] for i, arg in enumerate(observed[:-1]) if arg == "--env"]
    assert ("CAYU_BASE_URL" in forwarded) is compatible
    assert ("CAYU_API_KEY" in forwarded) is compatible
    assert ("OPENAI_API_KEY" in forwarded) is not compatible
    assert all("synthetic-" not in arg for arg in observed)


def test_openai_environment_selects_public_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    observed = {}

    def provider(**kwargs):
        observed.update(kwargs)
        return "configured"

    monkeypatch.setattr(providers, "OpenAIProvider", provider)
    assert providers.configured_provider() == "configured"
    assert observed["api_key"] == "synthetic-test-key"
    assert "base_url" not in observed  # Use the native adapter's public default.
    assert observed["name"] == configured_provider_name() == "openai"
    assert observed["streaming"] is False


def test_missing_key_refuses_live_execution(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CAMPUS_VIEWER_STATE", str(tmp_path))
    (tmp_path / "provider.key").write_text("stale-credential-must-not-be-read")
    assert configured_api_key() is None
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.configured_provider().preflight_model_target(model="gpt-5.6-sol")


def test_chat_completions_endpoint_uses_cayu_credentials(monkeypatch):
    monkeypatch.setenv("CAYU_BASE_URL", "https://codex-lb.cayu.ai/v1")
    monkeypatch.setenv("CAYU_API_KEY", "synthetic-cayu-key")
    observed = {}

    def provider(**kwargs):
        observed.update(kwargs)
        return "configured"

    monkeypatch.setattr(providers, "ChatCompletionsProvider", provider)
    assert providers.configured_provider() == "configured"
    assert observed == {
        "name": "codex-lb",
        "api_key": "synthetic-cayu-key",
        "base_url": "https://codex-lb.cayu.ai/v1",
        "timeout_s": 90,
    }
    assert configured_api_key() == "synthetic-cayu-key"
    assert configured_provider_name() == "codex-lb"


def test_chat_completions_endpoint_requires_cayu_key(monkeypatch):
    monkeypatch.setenv("CAYU_BASE_URL", "https://codex-lb.cayu.ai/v1")
    monkeypatch.delenv("CAYU_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-provider-boundary")
    with pytest.raises(RuntimeError, match="CAYU_API_KEY"):
        providers.configured_provider().preflight_model_target(model="gpt-5.6-sol")


def test_presenter_missing_key_does_not_consume_state_directory(monkeypatch, tmp_path):
    from operations.viewer_host import start_host

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    directory = tmp_path / "new-presenter"
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        start_host(directory)
    assert not directory.exists()


def test_native_adapter_targets_exact_openai_responses_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    urls = []

    async def offline_send(self, request, **kwargs):
        urls.append(str(request.url))
        assert json.loads(request.content)["stream"] is False
        raise httpx.ConnectError("offline endpoint probe", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", offline_send)

    async def run():
        provider = providers.configured_provider()
        request = ModelRequest(model="gpt-5.6-sol", messages=[Message.text("user", "Hello")])
        async for _event in provider.stream(request):
            pass

    asyncio.run(run())
    assert urls == ["https://api.openai.com/v1/responses"]
