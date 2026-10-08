"""Hermetic acceptance for scoped automatic knowledge recall."""

import asyncio

from cayu import (
    ContextExposureState,
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
    KnowledgeAccessScope,
    KnowledgeEntry,
    KnowledgeStatus,
    Message,
    ModelStreamEvent,
    RecallEvidenceQuery,
    RunRequest,
    ScriptedModelProvider,
    TextPart,
    run_to_completion,
)

from app import build_app
from knowledge.retrieval import KNOWLEDGE_NAMESPACE


def test_active_scoped_knowledge_affects_a_later_run_with_exposure_evidence() -> None:
    async def exercise() -> None:
        sessions = InMemorySessionStore()
        knowledge = InMemoryKnowledgeStore()
        maintenance = KnowledgeAccessScope.privileged()
        await knowledge.create_entry(
            KnowledgeEntry(
                id="atlas-active",
                namespace=KNOWLEDGE_NAMESPACE,
                text="Atlas launch code ATLAS_ACTIVE_FRIDAY is the reviewed answer.",
            ),
            access_scope=maintenance,
        )
        await knowledge.create_entry(
            KnowledgeEntry(
                id="atlas-pending",
                namespace=KNOWLEDGE_NAMESPACE,
                text="Atlas launch code PENDING_MUST_NOT_APPEAR.",
                status=KnowledgeStatus.PENDING,
            ),
            access_scope=maintenance,
        )
        await knowledge.create_entry(
            KnowledgeEntry(
                id="atlas-archived",
                namespace=KNOWLEDGE_NAMESPACE,
                text="Atlas launch code ARCHIVED_MUST_NOT_APPEAR.",
                status=KnowledgeStatus.ARCHIVED,
            ),
            access_scope=maintenance,
        )
        await knowledge.create_entry(
            KnowledgeEntry(
                id="atlas-other-agent",
                namespace="project:other:agent:other",
                text="Atlas launch code OUT_OF_SCOPE_MUST_NOT_APPEAR.",
            ),
            access_scope=maintenance,
        )
        provider = ScriptedModelProvider(
            [
                [
                    ModelStreamEvent.text_delta("Friday."),
                    ModelStreamEvent.completed({"finish_reason": "stop"}),
                ]
            ]
        )
        app = build_app(
            provider=provider,
            session_store=sessions,
            task_store=InMemoryTaskStore(),
            knowledge_store=knowledge,
        )

        outcome = await run_to_completion(
            app,
            RunRequest(
                agent_name="cayu-campus-dining-demo",
                session_id="later-memory-run",
                messages=[Message.text("user", "What is the Atlas launch code?")],
            ),
        )

        assert outcome.ok
        provider_text = "\n".join(
            part.text
            for message in provider.requests[0].messages
            for part in message.content
            if type(part) is TextPart
        )
        assert "ATLAS_ACTIVE_FRIDAY" in provider_text
        assert "PENDING_MUST_NOT_APPEAR" not in provider_text
        assert "ARCHIVED_MUST_NOT_APPEAR" not in provider_text
        assert "OUT_OF_SCOPE_MUST_NOT_APPEAR" not in provider_text

        query = RecallEvidenceQuery(session_id="later-memory-run")
        receipts = (await sessions.list_recall_receipts(query)).items
        exposures = (await sessions.list_context_exposures(query)).items
        assert len(receipts) == 1 and receipts[0].admitted_count == 1
        assert len(exposures) == 1
        assert exposures[0].receipt_ids == (receipts[0].receipt_id,)
        assert exposures[0].state is ContextExposureState.COMPLETED

    asyncio.run(exercise())
