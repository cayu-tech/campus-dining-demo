"""Scoped reviewed knowledge configuration for this project."""

from cayu import KnowledgeAccessScope, KnowledgeStatus

KNOWLEDGE_NAMESPACE = "project:campus-dining-demo:agent:cayu-campus-dining-demo"


def build_knowledge_scope() -> KnowledgeAccessScope | None:
    """Admit active recall and pending proposals only inside this agent namespace."""

    return KnowledgeAccessScope(
        allowed_namespaces=[KNOWLEDGE_NAMESPACE],
        allowed_statuses=[KnowledgeStatus.ACTIVE, KnowledgeStatus.PENDING],
    )
