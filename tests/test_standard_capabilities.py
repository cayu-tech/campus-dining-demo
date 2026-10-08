"""Hermetic acceptance for the standard local collaborators."""

import asyncio

from cayu import (
    EventType,
    IncompleteSessionRecoveryAction,
    IncompleteSessionRecoveryRequest,
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
    KnowledgeQuery,
    KnowledgeStatus,
    Message,
    ModelStreamEvent,
    PendingToolApprovalEventView,
    RunRequest,
    ScriptedModelProvider,
    ToolApprovalDecision,
    ToolApprovalRequest,
)

from app import build_app
from knowledge.retrieval import KNOWLEDGE_NAMESPACE, build_knowledge_scope
from configuration.settings import CUSTOMER
from policies.human_review import review_context
from tools.questions import QUESTIONS


def test_manifest_exposes_real_collaborators_without_runner_or_network_authority() -> (
    None
):
    app = build_app(
        provider=ScriptedModelProvider([]),
        session_store=InMemorySessionStore(),
        task_store=InMemoryTaskStore(),
        knowledge_store=InMemoryKnowledgeStore(),
    )
    manifest = app.describe()
    assert manifest.stores.task == "InMemoryTaskStore"
    assert manifest.stores.knowledge == "InMemoryKnowledgeStore"
    assert manifest.runtime.event_sinks
    environment = manifest.environments[0]
    assert environment.artifact_store == "LocalArtifactStore"
    assert environment.knowledge_store == "InMemoryKnowledgeStore"
    assert environment.runner is None
    assert environment.vault is None
    assert environment.credential_proxy is None
    assert environment.mcp_servers == ()
    agent = manifest.agents[0]
    assert agent.context_policy == "AutomaticRecallContextPolicy"
    assert agent.tool_policy == "ParameterConstrainedToolPolicy"
    assert {tool.name for tool in agent.tools} >= {"ask_user", "remember_knowledge"}


def test_human_input_and_approval_pause_with_recoverable_durable_state() -> None:
    async def exercise() -> None:
        input_provider = ScriptedModelProvider(
            [
                [
                    ModelStreamEvent.tool_call(
                        id="ask-call",
                        name="ask_user",
                        arguments={"question": QUESTIONS[0]},
                    ),
                    ModelStreamEvent.completed({"finish_reason": "tool_calls"}),
                ]
            ]
        )
        input_app = build_app(
            provider=input_provider,
            session_store=InMemorySessionStore(),
            task_store=InMemoryTaskStore(),
            knowledge_store=InMemoryKnowledgeStore(),
        )
        input_events = [
            event
            async for event in input_app.run(
                RunRequest(
                    agent_name="cayu-campus-dining-demo",
                    session_id="standard-input-pause",
                    messages=[Message.text("user", "Ask before continuing")],
                )
            )
        ]
        assert EventType.SESSION_AWAITING_USER_INPUT in {
            event.type for event in input_events
        }
        input_recovery = await input_app.recover_incomplete_session(
            IncompleteSessionRecoveryRequest(session_id="standard-input-pause")
        )
        assert (
            IncompleteSessionRecoveryAction.PENDING_USER_INPUT in input_recovery.actions
        )

        invalid_app = build_app(
            provider=ScriptedModelProvider(
                [
                    [
                        ModelStreamEvent.tool_call(
                            id="invalid-question", name="ask_user", arguments={}
                        ),
                        ModelStreamEvent.completed({"finish_reason": "tool_calls"}),
                    ],
                    [
                        ModelStreamEvent.text_delta("Correct the question."),
                        ModelStreamEvent.completed(),
                    ],
                ]
            ),
            session_store=InMemorySessionStore(),
            task_store=InMemoryTaskStore(),
            knowledge_store=InMemoryKnowledgeStore(),
        )
        invalid_events = [
            event
            async for event in invalid_app.run(
                RunRequest(
                    agent_name="cayu-campus-dining-demo",
                    session_id="invalid-input",
                    messages=[Message.text("user", "Ask a question")],
                )
            )
        ]
        assert EventType.TOOL_CALL_BLOCKED in {event.type for event in invalid_events}
        assert EventType.TOOL_CALL_APPROVAL_REQUESTED not in {
            event.type for event in invalid_events
        }
        assert EventType.SESSION_AWAITING_USER_INPUT not in {
            event.type for event in invalid_events
        }

        approval_provider = ScriptedModelProvider(
            [
                [
                    ModelStreamEvent.tool_call(
                        id="remember-call",
                        name="remember_knowledge",
                        arguments={"text": "Stable project preference"},
                    ),
                    ModelStreamEvent.completed({"finish_reason": "tool_calls"}),
                ]
            ]
        )
        approval_sessions = InMemorySessionStore()
        approval_tasks = InMemoryTaskStore()
        approval_knowledge = InMemoryKnowledgeStore()
        approval_app = build_app(
            provider=approval_provider,
            session_store=approval_sessions,
            task_store=approval_tasks,
            knowledge_store=approval_knowledge,
        )
        approval_events = [
            event
            async for event in approval_app.run(
                RunRequest(
                    agent_name="cayu-campus-dining-demo",
                    session_id="standard-approval-pause",
                    messages=[Message.text("user", "Remember this preference")],
                )
            )
        ]
        assert EventType.TOOL_CALL_APPROVAL_REQUESTED in {
            event.type for event in approval_events
        }
        approval_recovery = await approval_app.recover_incomplete_session(
            IncompleteSessionRecoveryRequest(session_id="standard-approval-pause")
        )
        assert (
            IncompleteSessionRecoveryAction.PENDING_APPROVAL
            in approval_recovery.actions
        )
        durable_events = await approval_sessions.load_events("standard-approval-pause")
        approval_event = next(
            event
            for event in durable_events
            if event.type is EventType.TOOL_CALL_APPROVAL_REQUESTED
        )
        approval = PendingToolApprovalEventView.from_event(approval_event)
        recovered_app = build_app(
            provider=ScriptedModelProvider(
                [
                    [
                        ModelStreamEvent.text_delta("Knowledge proposal recorded."),
                        ModelStreamEvent.completed({"finish_reason": "stop"}),
                    ]
                ]
            ),
            session_store=approval_sessions,
            task_store=approval_tasks,
            knowledge_store=approval_knowledge,
        )
        # The demo's review policy shows only dining questions and orders, so a
        # knowledge proposal's review is redacted: it can be denied, not approved.
        review = await recovered_app.inspect_human_review(
            "standard-approval-pause", context=review_context(CUSTOMER)
        )
        assert review.status == "redacted" and review.reference is not None
        recovered_events = [
            event
            async for event in recovered_app.resolve_tool_approval(
                ToolApprovalRequest(
                    session_id="standard-approval-pause",
                    approval_id=approval.approval_id,
                    tool_round_id=approval.tool_round_id,
                    tool_call_id=approval.tool_call_id,
                    decision=ToolApprovalDecision.DENY,
                    review_reference=review.reference,
                )
            )
        ]
        assert EventType.TOOL_CALL_COMPLETED not in {
            event.type for event in recovered_events
        }
        pending = await approval_knowledge.search(
            KnowledgeQuery(
                text="Stable project preference",
                namespace=KNOWLEDGE_NAMESPACE,
                statuses=[KnowledgeStatus.PENDING],
            ),
            access_scope=build_knowledge_scope(),
        )
        assert pending.hits == []

    asyncio.run(exercise())
