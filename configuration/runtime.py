"""Application-wide runtime policy and collaborator construction seam."""

from dataclasses import dataclass

from cayu import CayuConfig, RequestFootprintConfig

from configuration.settings import (
    configured_memory_evidence_key,
)


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    config: CayuConfig
    enable_logging: bool
    knowledge_review_namespace: str | None
    request_footprint: RequestFootprintConfig


def build_runtime_options() -> RuntimeOptions:
    """Construct the selected event-sink profile without starting lifecycle work."""

    return RuntimeOptions(
        config=CayuConfig(),
        enable_logging=True,
        knowledge_review_namespace="project:campus-dining-demo:agent:cayu-campus-dining-demo",
        request_footprint=_request_footprint_config(),
    )


def _request_footprint_config() -> RequestFootprintConfig:
    key = configured_memory_evidence_key()
    if len(key.encode("utf-8")) < 32:
        raise RuntimeError("the memory evidence key must contain at least 32 bytes")
    return RequestFootprintConfig(
        fingerprint_key_id="standard-local-v1",
        fingerprint_key=key,
    )
