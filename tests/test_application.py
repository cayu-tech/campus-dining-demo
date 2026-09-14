"""Real Cayu pauses and authorization, using a deterministic provider."""

import asyncio

import pytest
from cayu import (
    EventType,
    Message,
    ModelStreamEvent,
    RunRequest,
    ScriptedModelProvider,
    ToolApprovalDecision,
    ToolApprovalRequest,
)

from app import build_app
from domain.store import PortalStore
from operations.lifecycle import close_app
from policies.human_review import inspect_review


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


@pytest.mark.parametrize("allow", [True, False])
def test_exact_order_waits_for_real_runtime_approval(settings, allow):
    async def run():
        store = PortalStore(settings.portal_database)
        p = store.prepare(settings.customer, "approval", "dinner", "POT-PEELED-10KG", 7, 1)
        provider = ScriptedModelProvider(
            [
                call("submit_proposal", {"proposal_id": p["proposal_id"], "digest": p["digest"]}),
                call("verify_submission", {"proposal_id": p["proposal_id"]}, "verify"),
                stop(),
            ]
        )
        app = build_app(settings=settings, provider=provider)
        try:
            events = [
                e
                async for e in app.run(
                    RunRequest(
                        agent_name="cayu-campus-dining-demo",
                        session_id="approval",
                        messages=[Message.text("user", "Place the reviewed order.")],
                    )
                )
            ]
            assert store.orders(settings.customer) == []
            approval = next(
                e for e in events if e.type == EventType.TOOL_CALL_APPROVAL_REQUESTED
            ).payload["approval"]
            review = await inspect_review(app, settings, "approval")
            assert review.status == "permitted"
            fields = {f.label: f.text for f in review.fields}
            assert fields["Total cents"] == "17500" and fields["Preparation minutes"] == "35"
            follow = [
                e
                async for e in app.resolve_tool_approval(
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
            ]
            assert len(store.orders(settings.customer)) == int(allow)
            assert any(e.type == EventType.SESSION_COMPLETED for e in follow)
        finally:
            await close_app(app)

    asyncio.run(run())


def test_revision_tool_uses_runtime_idempotency_identity(settings):
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
        app = build_app(settings=settings, provider=provider)
        try:
            events = [
                e
                async for e in app.run(
                    RunRequest(
                        agent_name="cayu-campus-dining-demo",
                        session_id="staff",
                        messages=[Message.text("user", "We now have the full team.")],
                    )
                )
            ]
            assert not any(
                e.type in {EventType.TOOL_CALL_FAILED, EventType.SESSION_FAILED} for e in events
            )
            assert (
                PortalStore(settings.portal_database).plan(settings.customer, "staff")[
                    "prep_minutes_available"
                ]
                == 240
            )
        finally:
            await close_app(app)

    asyncio.run(run())


def test_protected_clarification_displays_only_declared_question(settings):
    from tools.preference import QUESTIONS

    async def run():
        app = build_app(
            settings=settings,
            provider=ScriptedModelProvider([call("ask_user", {"question": QUESTIONS[2]})]),
        )
        try:
            events = [
                e
                async for e in app.run(
                    RunRequest(
                        agent_name="cayu-campus-dining-demo",
                        session_id="question",
                        messages=[Message.text("user", "Ask how many people.")],
                    )
                )
            ]
            assert any(e.type == EventType.SESSION_AWAITING_USER_INPUT for e in events)
            review = await inspect_review(app, settings, "question")
            assert review.status == "permitted" and review.fields[0].text == QUESTIONS[2]
        finally:
            await close_app(app)

    asyncio.run(run())


def test_read_only_supplier_pages(settings):
    from fastapi.testclient import TestClient

    from integrations.portal import build_portal

    with TestClient(build_portal(settings)) as client:
        assert "Russet potatoes" in client.get("/?q=potatoes").text
        details = client.get("/products/POT-PEELED-10KG").text
        assert "95.0%" in details and "9.5 kg usable" in details
        assert "240" not in client.get("/planning").text  # starting plan remains short-staffed
        for path in ["/orders", "/proposals", "/submit"]:
            assert client.post(path, json={}).status_code == 405
