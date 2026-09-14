"""Planning and approval-protected purchasing tools; never infer customer scope."""

import json

from cayu import ExecutionProfileBehaviorIdentity, Tool, ToolEffect, ToolResult, ToolSpec

from domain.catalog import MEALS, POLICY, STAFFING

MEAL = {"type": "string", "enum": list(MEALS)}
SKU = {"type": "string", "minLength": 1, "maxLength": 64}
REVISION = {"type": "integer", "minimum": 1}


def schema(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


class BusinessTool(Tool):
    def __init__(self, store, customer):
        self.store, self.customer = store, customer

    @property
    def execution_profile_identity(self):
        return ExecutionProfileBehaviorIdentity(
            name=f"campus-dining:{self.customer}:{self.spec.name}",
            behavior_version="1",
            implementation_version="2026-09-09.1",
        )

    async def run(self, ctx, args):
        try:
            value = self.execute(ctx, args)
            return ToolResult(content=json.dumps(value, sort_keys=True), structured=value)
        except (ValueError, KeyError) as exc:
            return ToolResult(content=str(exc), structured={"accepted": False}, is_error=True)


class InspectDiningPlan(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="inspect_dining_plan",
            description="Read the meal recipe, existing inventory, budget, receiving deadline and staffing schedule for this customer's session. Start here; missing user details may already be in these records.",
            input_schema=schema({"meal_id": MEAL}),
            effect=ToolEffect.NONE,
        )

    def execute(self, ctx, args):
        return {
            "plan": self.store.plan(self.customer, ctx.session_id, args["meal_id"]),
            "staffing_schedules": STAFFING,
            "purchasing_policy": POLICY,
        }


class ReviseDiningPlan(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="revise_dining_plan",
            description="Record an explicit customer change to staffing, attendance, spending budget or receiving deadline. Never change constraints simply to make an option pass. Invalidates the previous proposal. Use the inspected plan revision; staffing full-team provides 240 preparation minutes, short-staffed 45.",
            input_schema=schema(
                {
                    "meal_id": MEAL,
                    "expected_revision": REVISION,
                    "changes": schema(
                        {
                            "staffing": {"type": "string", "enum": list(STAFFING)},
                            "portions": {"type": "integer", "minimum": 1, "maximum": 5000},
                            "budget_cents": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": POLICY["maximum_order_cents"],
                            },
                            "delivery_deadline_minute": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1439,
                            },
                        },
                        required=[],
                    ),
                }
            ),
            effect=ToolEffect.IDEMPOTENT,
            parallel_safe=False,
        )

    def execute(self, ctx, args):
        return self.store.revise_plan(
            self.customer,
            ctx.session_id,
            args["meal_id"],
            args["expected_revision"],
            args["changes"],
            ctx.idempotency_key,
        )


class SearchCatalog(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="search_catalog",
            description="Search current supplier facts. Available only in native development mode; the browser demo uses the supplier portal.",
            input_schema=schema({"query": {"type": "string", "maxLength": 100}}),
            effect=ToolEffect.NONE,
        )

    def execute(self, ctx, args):
        return {"products": self.store.products(args["query"])}


class AssessProduct(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="assess_product",
            description="Calculate the minimum whole cases required after inventory and cooked yield, exact cost, prep time and eligibility against the current meal plan and purchasing policy. Compare plausible options; this tool does not rank or choose for you.",
            input_schema=schema({"meal_id": MEAL, "sku": SKU}),
            effect=ToolEffect.NONE,
        )

    def execute(self, ctx, args):
        return {
            "sku": args["sku"],
            **self.store.assess(self.customer, ctx.session_id, args["meal_id"], args["sku"]),
        }


class PrepareProposal(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="prepare_proposal",
            description="Store the exact feasible order for review, binding product facts, meal plan and policy revisions. A draft does not purchase. Explain why this option is the best fit and meaningful alternatives to the customer.",
            input_schema=schema(
                {
                    "meal_id": MEAL,
                    "sku": SKU,
                    "cases": {"type": "integer", "minimum": 1, "maximum": 100},
                    "expected_plan_revision": REVISION,
                }
            ),
            effect=ToolEffect.IDEMPOTENT,
            parallel_safe=False,
        )

    def execute(self, ctx, args):
        return self.store.prepare(
            self.customer,
            ctx.session_id,
            args["meal_id"],
            args["sku"],
            args["cases"],
            args["expected_plan_revision"],
        )


class SubmitProposal(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="submit_proposal",
            description="Request purchasing approval for the exact current proposal ID and digest. Runtime pauses before any order is submitted. All facts and constraints are rechecked atomically after approval.",
            input_schema=schema(
                {
                    "proposal_id": {"type": "string", "maxLength": 64},
                    "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                }
            ),
            effect=ToolEffect.IDEMPOTENT,
            parallel_safe=False,
        )

    def execute(self, ctx, args):
        return self.store.submit(args["proposal_id"], args["digest"], self.customer, ctx.session_id)


class VerifySubmission(BusinessTool):
    @property
    def spec(self):
        return ToolSpec(
            name="verify_submission",
            description="Independently read the purchase receipt for the exact proposal and current customer/session. Only a matching recorded receipt proves purchase.",
            input_schema=schema({"proposal_id": {"type": "string", "maxLength": 64}}),
            effect=ToolEffect.NONE,
        )

    def execute(self, ctx, args):
        self.store.proposal(args["proposal_id"], self.customer, ctx.session_id)
        return {
            "orders": [
                o
                for o in self.store.orders(self.customer)
                if o["proposal_id"] == args["proposal_id"]
            ]
        }
