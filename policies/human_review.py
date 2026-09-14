"""Local trusted-presenter disclosure; never attach this policy to a public service."""

from cayu import (
    HumanReviewContext,
    HumanReviewDisclosure,
    HumanReviewField,
    HumanReviewPolicy,
)

from domain.store import PortalStore
from tools.preference import PREFERENCE_TOOL, QUESTIONS


def review_context(settings, session_id):
    return HumanReviewContext(
        recipient="local-presenter", tenant=settings.customer, purpose=f"order-review:{session_id}"
    )


class OrderReview(HumanReviewPolicy):
    version = "campus-order-review-2026-09-09.1"

    def __init__(self, settings):
        self.settings = settings
        self.store = PortalStore(settings.portal_database)
        self._key = (settings.data_dir / "human-review.key").read_bytes()

    @property
    def binding_key(self):
        return self._key

    def authorize(self, context, *, session_id, session_metadata, action):
        # Each app uses a separate customer SQLite store. All callers here are
        # the local trusted presenter; no request body or model supplies context.
        return (
            bool(session_id)
            and context == review_context(self.settings, session_id)
            and action in {"inspect", "decide"}
        )

    def project(self, context, source):
        # Never attest model text by a known-secret scan. Only an exact declared
        # question or a complete match to an application-owned proposal is allowed.
        if len(source.calls) != 1:
            return HumanReviewDisclosure(status="redacted")
        call = source.calls[0]
        args = source.arguments_by_call.get(call.tool_call_id)
        if source.kind == "user_input":
            if (
                call.tool_name != PREFERENCE_TOOL
                or not isinstance(args, dict)
                or set(args) != {"question"}
                or args["question"] not in QUESTIONS
            ):
                return HumanReviewDisclosure(status="redacted")
            fields = (HumanReviewField(label="Question", text=args["question"]),)
        else:
            session_id = context.purpose.removeprefix("order-review:")
            proposal = self.store.current_proposal(self.settings.customer, session_id)
            if (
                call.tool_name != "submit_proposal"
                or proposal is None
                or args != {"proposal_id": proposal["proposal_id"], "digest": proposal["digest"]}
            ):
                return HumanReviewDisclosure(status="redacted")
            fields = tuple(
                HumanReviewField(label=label, text=str(value))
                for label, value in (
                    ("Action", "Record one synthetic order after approval"),
                    ("Customer", self.settings.customer),
                    ("SKU", proposal["sku"]),
                    ("Product", proposal["product"]["name"]),
                    ("Cases", proposal["cases"]),
                    ("Meal", proposal["plan"]["name"]),
                    ("Plan revision", proposal["plan"]["revision"]),
                    ("Portions", proposal["plan"]["portions"]),
                    ("Budget cents", proposal["plan"]["budget_cents"]),
                    ("Preparation minutes", proposal["assessment"]["prep_minutes"]),
                    ("Kitchen capacity minutes", proposal["plan"]["prep_minutes_available"]),
                    (
                        "Usable cooked kilograms",
                        proposal["assessment"]["usable_cooked_grams"] / 1000,
                    ),
                    (
                        "Delivery",
                        f"{proposal['product']['delivery_date']} {proposal['product']['delivery_minute'] // 60:02d}:{proposal['product']['delivery_minute'] % 60:02d}",
                    ),
                    ("Total cents", proposal["assessment"]["total_cents"]),
                    ("Proposal", proposal["proposal_id"]),
                    ("Fingerprint", proposal["digest"]),
                )
            )
        return HumanReviewDisclosure(
            status="permitted", sensitive_content="application_attested", fields=fields
        )


async def inspect_review(app, settings, session_id):
    return await app.inspect_human_review(session_id, context=review_context(settings, session_id))


async def reviewed_reference(app, settings, session_id, tag):
    view = await inspect_review(app, settings, session_id)
    if not tag or view.reference is None or view.reference.content_tag != tag:
        raise ValueError("Inspect `pending` and pass its current --review-tag before deciding")
    return view.reference
