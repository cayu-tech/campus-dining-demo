"""Construct durable Cayu state; business records live in domain.store."""

from dataclasses import dataclass

from cayu import SQLiteKnowledgeStore, SQLiteSessionStore, SQLiteTaskStore


@dataclass
class ApplicationStores:
    session_store: object
    task_store: object
    knowledge_store: object


def build_stores(settings, scope, *, session_store=None, task_store=None, knowledge_store=None):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return ApplicationStores(
        session_store if session_store is not None else SQLiteSessionStore(settings.database),
        task_store if task_store is not None else SQLiteTaskStore(settings.database),
        knowledge_store
        if knowledge_store is not None
        else SQLiteKnowledgeStore(settings.database, access_scope=scope),
    )
