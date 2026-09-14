"""Provider selection uses explicit environment credentials and the public API."""

import asyncio
import json

import httpx
import pytest
from cayu import Message, ModelRequest

from configuration import providers
from configuration.settings import configured_api_key, configured_provider_name


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
