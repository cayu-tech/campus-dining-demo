"""Invoke/resume Cayu directly; no application-owned orchestration state machine."""

from cayu import (
    EventType,
    Message,
    ResolutionActor,
    ResolutionActorSource,
    ResumeRequest,
    RetryPolicy,
    RunLimits,
    RunRequest,
)

from policies.budgets import MAX_TOTAL_TOKENS


def run_limits():
    return RunLimits(max_tool_calls=24, max_total_tokens=MAX_TOTAL_TOKENS, max_elapsed_seconds=300)


def resolution_actor():
    return ResolutionActor(subject="local-presenter", source=ResolutionActorSource.REQUEST)


def request(message, session_id=None):
    return RunRequest(
        agent_name="cayu-campus-dining-demo",
        session_id=session_id,
        messages=[Message.text("user", message)],
        max_steps=28,
        limits=run_limits(),
        retry_policy=RetryPolicy(max_attempts=1, max_unknown_attempts=1),
    )


async def run_or_resume(app, message, session_id=None):
    existing = await app.session_store.load(session_id) if session_id else None
    events = (
        app.resume(ResumeRequest(session_id=session_id, messages=[Message.text("user", message)], max_steps=28, limits=run_limits(), retry_policy=RetryPolicy(max_attempts=1, max_unknown_attempts=1)))
        if existing is not None else app.run(request(message, session_id))
    )
    async for event in events:
        yield event


async def print_events(events):
    session_id = None
    failed = False
    expected_pause = False
    async for event in events:
        session_id = event.session_id
        if event.type in {
            EventType.TOOL_CALL_APPROVAL_REQUESTED,
            EventType.SESSION_AWAITING_USER_INPUT,
        }:
            expected_pause = True
        if event.type == EventType.SESSION_FAILED or (
            event.type == EventType.SESSION_INTERRUPTED
            and (event.payload.get("error") or not expected_pause)
        ):
            failed = True
        if event.type in {
            EventType.TOOL_CALL_APPROVAL_REQUESTED,
            EventType.SESSION_AWAITING_USER_INPUT,
        }:
            print(event.type, event.payload)
            if event.type == EventType.SESSION_AWAITING_USER_INPUT:
                print("Inspect `pending` for the protected question and review tag.")
        elif event.type == EventType.MODEL_TEXT_DELTA:
            print(event.payload.get("text", event.payload.get("delta", "")), end="", flush=True)
        elif event.type in {EventType.TOOL_CALL_COMPLETED, EventType.TOOL_CALL_FAILED}:
            print(f"\n{event.type}: {event.tool_name}")
            print(event.payload.get("result", {}).get("content", ""))
        elif event.type in {EventType.SESSION_COMPLETED, EventType.SESSION_FAILED}:
            print(f"\n{event.type}")
    if session_id:
        print(f"\nSession: {session_id}")
    if failed:
        raise RuntimeError(
            f"Session {session_id} did not complete successfully; inspect its evidence"
        )
    return session_id
