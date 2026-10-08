"""What a reviewer sees before answering a question or approving an order.

Cayu keeps a paused tool call's arguments private. This policy decides who may
review a pause and which application-checked fields they see. The packaged
dashboard shows these fields when the server sets the same purpose (serve.py).
"""

from cayu import (
    HumanReviewContext,
    HumanReviewDisclosure,
    HumanReviewField,
    HumanReviewPolicy,
)

from tools.questions import QUESTION_TOOL, QUESTIONS

REVIEW_PURPOSE = "order-review"


def review_context(customer, recipient="operator"):
    return HumanReviewContext(recipient=recipient, tenant=customer, purpose=REVIEW_PURPOSE)


class OrderReview(HumanReviewPolicy):
    # Change the version whenever authorization or the displayed fields change.
    version = "campus-order-review-1"

    def __init__(self, store, customer, binding_key):
        self.store, self.customer, self._key = store, customer, binding_key

    @property
    def binding_key(self):
        return self._key

    def authorize(self, context, *, session_id, session_metadata, action):
        # The server authenticates the operator and supplies their tenant.
        return (
            bool(session_id)
            and context.purpose == REVIEW_PURPOSE
            and context.tenant == self.customer
            and action in {"inspect", "decide"}
        )

    def project(self, context, source):
        # Show only an exact declared question or the exact current proposal;
        # anything else stays redacted, which allows denial but not approval.
        if len(source.calls) != 1:
            return HumanReviewDisclosure(status="redacted")
        call = source.calls[0]
        args = source.arguments_by_call.get(call.tool_call_id)
        if source.kind == "user_input":
            if (
                call.tool_name != QUESTION_TOOL
                or not isinstance(args, dict)
                or set(args) != {"question"}
                or args["question"] not in QUESTIONS
            ):
                return HumanReviewDisclosure(status="redacted")
            fields = (HumanReviewField(label="Question", text=args["question"]),)
        else:
            proposal = self._current_proposal(call.tool_name, args)
            if proposal is None:
                return HumanReviewDisclosure(status="redacted")
            product, plan, assessment = (
                proposal["product"],
                proposal["plan"],
                proposal["assessment"],
            )
            delivery = (
                f"{product['delivery_minute'] // 60:02d}:{product['delivery_minute'] % 60:02d}"
            )
            fields = tuple(
                HumanReviewField(label=label, text=str(value))
                for label, value in (
                    ("Action", "Record one synthetic order after approval"),
                    ("SKU", proposal["sku"]),
                    ("Product", product["name"]),
                    ("Cases", proposal["cases"]),
                    ("Meal", plan["name"]),
                    ("Plan revision", plan["revision"]),
                    ("Portions", plan["portions"]),
                    ("Budget cents", plan["budget_cents"]),
                    ("Preparation minutes", assessment["prep_minutes"]),
                    ("Kitchen capacity minutes", plan["prep_minutes_available"]),
                    ("Usable cooked kilograms", assessment["usable_cooked_grams"] / 1000),
                    ("Delivery", f"{product['delivery_date']} {delivery}"),
                    ("Total cents", assessment["total_cents"]),
                    ("Proposal", proposal["proposal_id"]),
                    ("Fingerprint", proposal["digest"]),
                )
            )
        return HumanReviewDisclosure(
            status="permitted", sensitive_content="application_attested", fields=fields
        )

    def _current_proposal(self, tool_name, args):
        """The proposal these exact arguments name, if it is still current for its session.

        Submission separately rejects a proposal from another session.
        """

        if tool_name != "submit_proposal" or not isinstance(args, dict):
            return None
        if set(args) != {"proposal_id", "digest"}:
            return None
        try:
            proposal = self.store.proposal(args["proposal_id"], self.customer)
        except ValueError:
            return None
        current = self.store.current_proposal(self.customer, proposal["session_id"])
        if current is None or current["proposal_id"] != proposal["proposal_id"]:
            return None
        return proposal if proposal["digest"] == args["digest"] else None
