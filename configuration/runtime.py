"""Runtime configuration and private memory-attribution key."""

from dataclasses import dataclass

from cayu import CayuConfig, RequestFootprintConfig


@dataclass(frozen=True)
class RuntimeOptions:
    config: CayuConfig
    enable_logging: bool
    knowledge_review_namespace: str
    request_footprint: RequestFootprintConfig


def build_runtime_options(settings):
    return RuntimeOptions(
        config=CayuConfig(),
        enable_logging=True,
        knowledge_review_namespace=settings.namespace,
        request_footprint=RequestFootprintConfig(
            fingerprint_key_id="campus-demo-v1", fingerprint_key=settings.evidence_key()
        ),
    )
