"""Local presenter commands. Run --help for the complete workflow."""

import argparse
import asyncio
import json

from cayu import (
    PendingActionKind,
    PendingActionQuery,
    RecallEvidenceQuery,
    ToolApprovalDecision,
    ToolApprovalRequest,
    UserInputResponse,
)

from app import build_app
from configuration.providers import validate_run_configuration
from configuration.settings import settings_from_environment
from domain.store import PortalStore
from operations.initialize import initialize
from operations.interaction import print_events, resolution_actor, run_or_resume
from operations.lifecycle import close_app
from policies.human_review import inspect_review, reviewed_reference


async def execute(args):
    settings = settings_from_environment()
    if args.command == "init":
        await initialize(settings)
        print(f"Initialized synthetic fixtures in {settings.data_dir}")
        return
    if args.command == "orders":
        print(json.dumps(PortalStore(settings.portal_database).orders(settings.customer), indent=2))
        return
    app = build_app(settings=settings)
    try:
        if args.command == "run":
            validate_run_configuration(app, "cayu-campus-dining-demo")
            await print_events(run_or_resume(app, args.message, args.session))
        elif args.command == "pending":
            page = await app.session_store.query_pending_actions(PendingActionQuery())
            display = page.model_dump(mode="json")
            for row in display["actions"]:
                view = await inspect_review(app, settings, row["session"]["id"])
                row["human_review"] = view.model_dump(mode="json")
            print(json.dumps(display, indent=2))
        elif args.command == "answer":
            await print_events(
                app.resolve_user_input(
                    UserInputResponse(
                        session_id=args.session,
                        input_id=args.input_id,
                        review_reference=await reviewed_reference(
                            app, settings, args.session, args.review_tag
                        ),
                        answer=args.answer,
                        resolved_by=resolution_actor(),
                    )
                )
            )
        elif args.command == "approve":
            page = await app.session_store.query_pending_actions(
                PendingActionQuery(session_id=args.session)
            )
            # Read exact durable identities, never infer IDs from user-facing text.
            rows = [
                item
                for item in page.actions
                if item.session.id == args.session and item.kind == PendingActionKind.TOOL_APPROVAL
            ]
            if len(rows) != 1:
                raise SystemExit("Expected exactly one pending tool approval; inspect `pending`")
            item = rows[0]
            await print_events(
                app.resolve_tool_approval(
                    ToolApprovalRequest(
                        session_id=args.session,
                        approval_id=item.approval_id,
                        review_reference=await reviewed_reference(
                            app, settings, args.session, args.review_tag
                        ),
                        tool_round_id=item.round_id,
                        tool_call_id=item.tool_call_id,
                        decision=ToolApprovalDecision.DENY
                        if args.deny
                        else ToolApprovalDecision.APPROVE,
                        resolved_by=resolution_actor(),
                    )
                )
            )
        elif args.command == "evidence":
            session = await app.session_store.load(args.session)
            if session is None:
                raise SystemExit("Unknown session")
            print(session.model_dump_json(indent=2))
            print((await app.get_session_usage(args.session)).model_dump_json(indent=2))
            query = RecallEvidenceQuery(session_id=args.session)
            print((await app.session_store.list_recall_receipts(query)).model_dump_json(indent=2))
            print((await app.session_store.list_context_exposures(query)).model_dump_json(indent=2))
    finally:
        await close_app(app)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "pending", "orders"):
        commands.add_parser(name)
    run = commands.add_parser("run")
    run.add_argument("--message", required=True)
    run.add_argument("--session")
    answer = commands.add_parser("answer")
    answer.add_argument("--session", required=True)
    answer.add_argument("--input-id", required=True)
    answer.add_argument("--answer", required=True)
    answer.add_argument("--review-tag", required=True)
    approval = commands.add_parser("approve")
    approval.add_argument("--session", required=True)
    approval.add_argument("--deny", action="store_true")
    approval.add_argument("--review-tag", required=True)
    evidence = commands.add_parser("evidence")
    evidence.add_argument("--session", required=True)
    portal = commands.add_parser("portal")
    portal.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if args.command == "portal":
        import uvicorn

        from integrations.portal import build_portal

        uvicorn.run(build_portal(), host="127.0.0.1", port=args.port)
    else:
        asyncio.run(execute(args))


if __name__ == "__main__":
    main()
