"""Campus dining demo commands: setup, a conversation turn, and recorded orders.

    python demo.py setup
    python demo.py run --message "..." [--session SESSION_ID]
    python demo.py orders

Answer questions and approve or deny orders in the dashboard (python serve.py).
"""

import argparse
import asyncio
import json
import os
import secrets

from cayu import EventType, Message, ResumeRequest, RetryPolicy, RunLimits, RunRequest

from app import build_app
from configuration.providers import validate_run_configuration
from configuration.settings import CUSTOMER, configured_dining_database
from configuration.storage import LOCAL_DATABASE_PATH, build_stores
from domain.store import DiningStore
from knowledge.curation import publish_purchasing_policy
from knowledge.retrieval import build_knowledge_scope

AGENT = "cayu-campus-dining-demo"


def _private_file(name, content):
    path = LOCAL_DATABASE_PATH.parent / name
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)


async def setup():
    """Create local keys, the dining fixture and the published purchasing policy."""

    LOCAL_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if "CAYU_MEMORY_EVIDENCE_KEY" not in os.environ:
        _private_file("memory-evidence.key", secrets.token_hex(32).encode() + b"\n")
    if "CAMPUS_HUMAN_REVIEW_KEY" not in os.environ:
        _private_file("human-review.key", secrets.token_bytes(32))
    DiningStore(configured_dining_database()).initialize()
    stores = build_stores(knowledge_scope=build_knowledge_scope())
    try:
        await publish_purchasing_policy(stores.knowledge_store)
    finally:
        if stores.configured is not None:
            await stores.configured.close()
    print(f"Ready: dining records in {configured_dining_database()}")


def limits():
    return {
        "max_steps": 28,
        "limits": RunLimits(
            max_tool_calls=24, max_total_tokens=10_000_000, max_elapsed_seconds=300
        ),
        "retry_policy": RetryPolicy(max_attempts=1, max_unknown_attempts=1),
    }


async def turn(message, session_id=None):
    """Start a session, or continue one with a new message."""

    async with build_app() as app:
        validate_run_configuration(app, AGENT)
        existing = await app.session_store.load(session_id) if session_id else None
        events = (
            app.resume(
                ResumeRequest(
                    session_id=session_id, messages=[Message.text("user", message)], **limits()
                )
            )
            if existing is not None
            else app.run(
                RunRequest(
                    agent_name=AGENT,
                    session_id=session_id,
                    messages=[Message.text("user", message)],
                    **limits(),
                )
            )
        )
        session = None
        async for event in events:
            session = event.session_id
            if event.type == EventType.MODEL_TEXT_DELTA:
                print(event.payload.get("text", event.payload.get("delta", "")), end="", flush=True)
            elif event.type in {EventType.TOOL_CALL_COMPLETED, EventType.TOOL_CALL_FAILED}:
                print(f"\n[{event.type}: {event.tool_name}]")
            elif event.type == EventType.TOOL_CALL_APPROVAL_REQUESTED:
                print("\n[Waiting for approval: review and decide in the dashboard]")
            elif event.type == EventType.SESSION_AWAITING_USER_INPUT:
                print("\n[Waiting for an answer: reply in the dashboard]")
            elif event.type in {EventType.SESSION_COMPLETED, EventType.SESSION_FAILED}:
                print(f"\n[{event.type}]")
        print(f"\nSession: {session}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Create keys, fixture data and the purchasing policy.")
    run = commands.add_parser("run", help="Send a message; pass --session to continue a session.")
    run.add_argument("--message", required=True)
    run.add_argument("--session")
    commands.add_parser("orders", help="Print recorded order receipts.")
    args = parser.parse_args()
    if args.command == "setup":
        asyncio.run(setup())
    elif args.command == "run":
        asyncio.run(turn(args.message, args.session))
    else:
        orders = DiningStore(configured_dining_database()).orders(CUSTOMER)
        print(json.dumps(orders, indent=2))


if __name__ == "__main__":
    main()
