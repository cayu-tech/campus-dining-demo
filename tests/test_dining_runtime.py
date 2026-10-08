"""Real Cayu pauses and review, driven by a deterministic provider."""

import asyncio
import secrets

import pytest
from cayu import (
    EventType,
    HumanReviewDenied,
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
    Message,
    ModelStreamEvent,
    RunRequest,
    ScriptedModelProvider,
    ToolApprovalDecision,
    ToolApprovalRequest,
)

from app import build_app
from configuration.settings import CUSTOMER
from policies.human_review import review_context
from tools.questions import QUESTIONS

AGENT = "cayu-campus-dining-demo"


def call(name, args, identity="call"):
    return [
        ModelStreamEvent.tool_call(id=identity, name=name, arguments=args),
        ModelStreamEvent.completed({"finish_reason": "tool_calls"}),
    ]


def stop():
    return [
        ModelStreamEvent.text_delta("Done."),
        ModelStreamEvent.completed({"finish_reason": "stop"}),
    ]


def dining_app(store, provider):
    return build_app(
        provider=provider,
        session_store=InMemorySessionStore(),
        task_store=InMemoryTaskStore(),
        knowledge_store=InMemoryKnowledgeStore(),
        dining_store=store,
        human_review_key=secrets.token_bytes(32),
    )


async def collect(events):
    return [event async for event in events]


def request(session_id, text):
    return RunRequest(
        agent_name=AGENT, session_id=session_id, messages=[Message.text("user", text)]
    )


@pytest.mark.parametrize("allow", [True, False])
def test_exact_order_waits_for_reviewed_approval(store, allow):
    async def run():
        p = store.prepare(CUSTOMER, "approval", "dinner", "POT-PEELED-10KG", 7, 1)
        provider = ScriptedModelProvider(
            [
                call("submit_proposal", {"proposal_id": p["proposal_id"], "digest": p["digest"]}),
                call("verify_submission", {"proposal_id": p["proposal_id"]}, "verify"),
                stop(),
            ]
        )
        async with dining_app(store, provider) as app:
            events = await collect(app.run(request("approval", "Place the reviewed order.")))
            assert store.orders(CUSTOMER) == []
            approval = next(
                e for e in events if e.type == EventType.TOOL_CALL_APPROVAL_REQUESTED
            ).payload["approval"]
            review = await app.inspect_human_review("approval", context=review_context(CUSTOMER))
            assert review.status == "permitted"
            fields = {f.label: f.text for f in review.fields}
            assert fields["Total cents"] == "17500" and fields["Preparation minutes"] == "35"
            follow = await collect(
                app.resolve_tool_approval(
                    ToolApprovalRequest(
                        session_id="approval",
                        approval_id=approval["approval_id"],
                        tool_round_id=approval["tool_round_id"],
                        tool_call_id=approval["tool_call_id"],
                        review_reference=review.reference,
                        decision=ToolApprovalDecision.APPROVE
                        if allow
                        else ToolApprovalDecision.DENY,
                    )
                )
            )
            assert len(store.orders(CUSTOMER)) == int(allow)
            assert any(e.type == EventType.SESSION_COMPLETED for e in follow)

    asyncio.run(run())


def test_review_is_refused_outside_the_customer_or_purpose(store):
    async def run():
        provider = ScriptedModelProvider([call("ask_user", {"question": QUESTIONS[2]})])
        async with dining_app(store, provider) as app:
            await collect(app.run(request("question", "Ask how many people.")))
            for context in (
                review_context("south-campus"),
                review_context(CUSTOMER).model_copy(update={"purpose": "other"}),
            ):
                with pytest.raises(HumanReviewDenied):
                    await app.inspect_human_review("question", context=context)

    asyncio.run(run())


def test_plan_revision_uses_the_runtime_idempotency_key(store):
    async def run():
        provider = ScriptedModelProvider(
            [
                call(
                    "revise_dining_plan",
                    {
                        "meal_id": "dinner",
                        "expected_revision": 1,
                        "changes": {"staffing": "full-team"},
                    },
                ),
                stop(),
            ]
        )
        async with dining_app(store, provider) as app:
            events = await collect(app.run(request("staff", "We now have the full team.")))
            assert not any(
                e.type in {EventType.TOOL_CALL_FAILED, EventType.SESSION_FAILED} for e in events
            )
            assert store.plan(CUSTOMER, "staff")["prep_minutes_available"] == 240

    asyncio.run(run())


def test_clarification_shows_only_a_declared_question(store):
    async def run():
        provider = ScriptedModelProvider([call("ask_user", {"question": QUESTIONS[2]})])
        async with dining_app(store, provider) as app:
            events = await collect(app.run(request("question", "Ask how many people.")))
            assert any(e.type == EventType.SESSION_AWAITING_USER_INPUT for e in events)
            review = await app.inspect_human_review("question", context=review_context(CUSTOMER))
            assert review.status == "permitted" and review.fields[0].text == QUESTIONS[2]

    asyncio.run(run())
