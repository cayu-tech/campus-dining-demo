"""Scope derives from trusted process configuration, never model arguments."""

from cayu import KnowledgeAccessScope, KnowledgeStatus

from configuration.settings import settings_from_environment


def build_knowledge_scope(settings=None):
    selected = settings or settings_from_environment()
    return KnowledgeAccessScope(
        allowed_namespaces=[selected.namespace],
        allowed_statuses=[KnowledgeStatus.ACTIVE, KnowledgeStatus.PENDING],
    )
