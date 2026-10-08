from __future__ import annotations

import asyncio

from cayu import (
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
    Message,
    ModelStreamEvent,
    RunRequest,
    ScriptedModelProvider,
    run_to_completion,
)

from app import build_app


def test_agent_runs_through_the_runtime() -> None:
    provider = ScriptedModelProvider(
        [
            ModelStreamEvent.text_delta("Agent result."),
            ModelStreamEvent.completed({"finish_reason": "stop"}),
        ]
    )
    app = build_app(
        provider=provider,
        session_store=InMemorySessionStore(),
        task_store=InMemoryTaskStore(),
        knowledge_store=InMemoryKnowledgeStore(),
    )

    outcome = asyncio.run(
        run_to_completion(
            app,
            RunRequest(
                agent_name="cayu-campus-dining-demo",
                messages=[Message.text("user", "Handle this request")],
            ),
        )
    )

    assert outcome.ok
    assert outcome.final_text == "Agent result."
    assert len(provider.requests) == 1
