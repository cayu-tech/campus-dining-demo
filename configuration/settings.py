"""Validated source-controlled defaults and environment overrides."""

import os
from pathlib import Path

from cayu import (
    AgentSpec,
    PublicAuthorityAliasCodec,
    public_authority_alias_codec_from_environment,
)

_PROJECT_ROOT = Path(__file__).parents[1]
_LOCAL_MEMORY_KEY = _PROJECT_ROOT / "data" / "memory-evidence.key"
_SCAFFOLDED_PROVIDER = "openai"
_SUPPORTED_PROVIDERS = {
    "openai",
    "anthropic",
    "openrouter",
    "cayu-gateway",
    "openai-subscription",
}
_PROVIDER_NAMES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "openrouter": "openrouter",
    "cayu-gateway": "cayu_gateway",
    "openai-subscription": "openai_subscription",
}
_DEFAULT_MODELS = {
    "openai": "gpt-5.6-luna",
    "anthropic": "claude-sonnet-4-6",
    "openai-subscription": "gpt-6-luna",
}


def configured_provider_choice() -> str | None:
    """Return explicit project or environment selection, never credential inference."""

    selected = os.environ.get("CAYU_PROVIDER", _SCAFFOLDED_PROVIDER)
    if selected is None:
        return None
    if selected not in _SUPPORTED_PROVIDERS:
        choices = ", ".join(sorted(_SUPPORTED_PROVIDERS))
        raise RuntimeError(f"CAYU_PROVIDER must be one of: {choices}")
    return selected


def configured_provider_name() -> str | None:
    selected = configured_provider_choice()
    return None if selected is None else _PROVIDER_NAMES[selected]


def configured_model() -> str:
    override = configured_model_override()
    if override:
        return override
    selected = configured_provider_choice()
    if selected in {"openrouter", "cayu-gateway"}:
        return f"{selected}-model-unconfigured"
    if selected is None:
        return "provider-model-unconfigured"
    return _DEFAULT_MODELS[selected]


_UNCONFIGURED_MODELS = (
    "provider-model-unconfigured",
    "openrouter-model-unconfigured",
    "cayu-gateway-model-unconfigured",
)


def resolve_configured_agent(agent: AgentSpec) -> AgentSpec:
    """Apply provider and model settings that were set after the agent was imported.

    Agent modules are imported before the application is built. An agent declared
    while no provider was selected carries a placeholder model; resolving it again
    at build time makes CAYU_PROVIDER and CAYU_MODEL set before build_app() apply.
    """

    if agent.model not in _UNCONFIGURED_MODELS:
        return agent
    return agent.model_copy(
        update={
            "model": configured_model(),
            "provider_name": configured_provider_name(),
        }
    )


def configured_model_override() -> str:
    return (os.environ.get("CAYU_MODEL") or "").strip()


def configured_openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def configured_anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def configured_gateway_api_key() -> str | None:
    return os.environ.get("CAYU_GATEWAY_API_KEY")


def configured_gateway_base_url() -> str | None:
    return os.environ.get("CAYU_GATEWAY_BASE_URL")


def configured_openrouter_api_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY")


def configured_openrouter_http_referer() -> str | None:
    return os.environ.get("OPENROUTER_HTTP_REFERER")


def configured_openrouter_app_title() -> str | None:
    return os.environ.get("OPENROUTER_APP_TITLE")


def configured_openrouter_router_metadata_enabled() -> bool:
    value = os.environ.get("OPENROUTER_ROUTER_METADATA")
    if value is None or value.lower() == "disabled":
        return False
    if value.lower() == "enabled":
        return True
    message = "OPENROUTER_ROUTER_METADATA must be 'enabled' or 'disabled' when set"
    raise RuntimeError(message)


def configured_public_authority_alias_codec() -> PublicAuthorityAliasCodec | None:
    return public_authority_alias_codec_from_environment()


def configured_memory_evidence_key() -> str:
    """Resolve private memory-key material at the configuration boundary.

    Deployments must set CAYU_MEMORY_EVIDENCE_KEY: the local key file is
    git-ignored and never reaches a deployed copy of the project.
    """

    key = os.environ.get("CAYU_MEMORY_EVIDENCE_KEY")
    if key is not None:
        return key
    try:
        return _LOCAL_MEMORY_KEY.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(
            "automatic memory requires CAYU_MEMORY_EVIDENCE_KEY or the private "
            "data/memory-evidence.key created by `cayu new`"
        ) from exc


# Campus dining demo settings. The demo serves one synthetic customer; the
# dining store still scopes every record by customer.
CUSTOMER = "north-campus"
CUSTOMER_NAME = "North Campus Dining"
_LOCAL_DINING_DATABASE = _PROJECT_ROOT / "data" / "dining.db"
_LOCAL_REVIEW_KEY = _PROJECT_ROOT / "data" / "human-review.key"


def configured_dining_database() -> Path:
    """The dining business records: meal plans, proposals and order receipts."""

    value = os.environ.get("CAMPUS_DINING_DATABASE")
    return Path(value).resolve() if value else _LOCAL_DINING_DATABASE


def configured_human_review_key() -> bytes:
    """Private key that binds an operator's approval to the exact reviewed proposal.

    Deployments set CAMPUS_HUMAN_REVIEW_KEY (64+ hex characters). Local
    development uses the git-ignored data/human-review.key that `demo.py setup`
    creates.
    """

    value = os.environ.get("CAMPUS_HUMAN_REVIEW_KEY")
    if value is not None:
        key = bytes.fromhex(value)
    else:
        try:
            key = _LOCAL_REVIEW_KEY.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                "human review requires CAMPUS_HUMAN_REVIEW_KEY or the private "
                "data/human-review.key created by `python demo.py setup`"
            ) from exc
    if len(key) < 32:
        raise RuntimeError("the human review key must contain at least 32 bytes")
    return key
