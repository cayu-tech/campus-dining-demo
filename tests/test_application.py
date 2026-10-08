"""Composition-root contract tests."""

from cayu import (
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
    ScriptedModelProvider,
)

from app import build_app


def test_factory_returns_fresh_apps_and_preserves_injected_stores() -> None:
    sessions = InMemorySessionStore()
    tasks = InMemoryTaskStore()
    knowledge = InMemoryKnowledgeStore()
    first = build_app(
        provider=ScriptedModelProvider([]),
        session_store=sessions,
        task_store=tasks,
        knowledge_store=knowledge,
    )
    second = build_app(
        provider=ScriptedModelProvider([]),
        session_store=InMemorySessionStore(),
        task_store=InMemoryTaskStore(),
        knowledge_store=InMemoryKnowledgeStore(),
    )

    assert first is not second
    assert first.session_store is sessions
    assert first.task_store is tasks
    assert first.knowledge_store is knowledge
