"""Dining purchasing tools. Customer scope comes from configuration, never the model."""

import json

from cayu import (
    ExecutionProfileBehaviorIdentity,
    Tool,
    ToolContext,
    ToolEffect,
    ToolResult,
    ToolSpec,
)

from domain.catalog import POLICY, STAFFING

# Bump a tool's behavior_version whenever its behavior changes, so paused
# sessions never resume against different tool behavior.


class DiningTool(Tool):
    def __init__(self, store, customer):
        self.store, self.customer = store, customer

    async def run(self, ctx: ToolContext, args: dict) -> ToolResult:
        try:
            value = self.execute(ctx, args)
            return ToolResult(content=json.dumps(value, sort_keys=True), structured=value)
        except (ValueError, KeyError) as exc:
            return ToolResult(content=str(exc), structured={"accepted": False}, is_error=True)


class InspectDiningPlan(DiningTool):
    spec = ToolSpec(
        name="inspect_dining_plan",
        description=(
            "Read the meal recipe, existing inventory, budget, receiving deadline and staffing "
            "schedule for this session. Start here; missing details may already be in these records."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "meal_id": {"type": "string", "enum": ["dinner", "rice-lunch", "vegetable-side"]}
            },
            "required": ["meal_id"],
            "additionalProperties": False,
        },
        effect=ToolEffect.NONE,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.inspect_dining_plan",
            behavior_version="1",
            implementation_version="1",
        ),
    )

    def execute(self, ctx, args):
        return {
            "plan": self.store.plan(self.customer, ctx.session_id, args["meal_id"]),
            "staffing_schedules": STAFFING,
            "purchasing_policy": POLICY,
        }


class ReviseDiningPlan(DiningTool):
    spec = ToolSpec(
        name="revise_dining_plan",
        description=(
            "Record an explicit customer change to staffing, attendance, budget or receiving "
            "deadline. Never change constraints just to make an option pass. Invalidates the "
            "previous proposal. Use the inspected plan revision; full-team staffing provides 240 "
            "preparation minutes, short-staffed 45."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "meal_id": {"type": "string", "enum": ["dinner", "rice-lunch", "vegetable-side"]},
                "expected_revision": {"type": "integer", "minimum": 1},
                "changes": {
                    "type": "object",
                    "properties": {
                        "staffing": {"type": "string", "enum": ["short-staffed", "full-team"]},
                        "portions": {"type": "integer", "minimum": 1, "maximum": 5000},
                        "budget_cents": {"type": "integer", "minimum": 1, "maximum": 25000},
                        "delivery_deadline_minute": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1439,
                        },
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
            "required": ["meal_id", "expected_revision", "changes"],
            "additionalProperties": False,
        },
        effect=ToolEffect.IDEMPOTENT,
        parallel_safe=False,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.revise_dining_plan",
            behavior_version="1",
            implementation_version="1",
        ),
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


class SearchCatalog(DiningTool):
    spec = ToolSpec(
        name="search_catalog",
        description="Search current supplier products by SKU, name or category.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "maxLength": 100}},
            "required": ["query"],
            "additionalProperties": False,
        },
        effect=ToolEffect.NONE,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.search_catalog", behavior_version="1", implementation_version="1"
        ),
    )

    def execute(self, ctx, args):
        return {"products": self.store.products(args["query"])}


class AssessProduct(DiningTool):
    spec = ToolSpec(
        name="assess_product",
        description=(
            "Calculate the minimum whole cases needed after inventory and cooked yield, exact cost, "
            "preparation time and eligibility against the current meal plan and purchasing policy. "
            "Compare plausible options; this tool does not rank or choose for you."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "meal_id": {"type": "string", "enum": ["dinner", "rice-lunch", "vegetable-side"]},
                "sku": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "required": ["meal_id", "sku"],
            "additionalProperties": False,
        },
        effect=ToolEffect.NONE,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.assess_product", behavior_version="1", implementation_version="1"
        ),
    )

    def execute(self, ctx, args):
        return {
            "sku": args["sku"],
            **self.store.assess(self.customer, ctx.session_id, args["meal_id"], args["sku"]),
        }


class PrepareProposal(DiningTool):
    spec = ToolSpec(
        name="prepare_proposal",
        description=(
            "Store the exact feasible order for review, binding product facts and the meal plan "
            "and policy revisions. A draft does not purchase. Explain why this option fits best and "
            "the meaningful alternatives."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "meal_id": {"type": "string", "enum": ["dinner", "rice-lunch", "vegetable-side"]},
                "sku": {"type": "string", "minLength": 1, "maxLength": 64},
                "cases": {"type": "integer", "minimum": 1, "maximum": 100},
                "expected_plan_revision": {"type": "integer", "minimum": 1},
            },
            "required": ["meal_id", "sku", "cases", "expected_plan_revision"],
            "additionalProperties": False,
        },
        effect=ToolEffect.IDEMPOTENT,
        parallel_safe=False,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.prepare_proposal", behavior_version="1", implementation_version="1"
        ),
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


class SubmitProposal(DiningTool):
    spec = ToolSpec(
        name="submit_proposal",
        description=(
            "Request purchasing approval for the exact current proposal ID and digest. Cayu pauses "
            "for a person before any order is recorded. All facts are rechecked after approval."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "maxLength": 64},
                "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            },
            "required": ["proposal_id", "digest"],
            "additionalProperties": False,
        },
        effect=ToolEffect.IDEMPOTENT,
        parallel_safe=False,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.submit_proposal", behavior_version="1", implementation_version="1"
        ),
    )

    def execute(self, ctx, args):
        return self.store.submit(args["proposal_id"], args["digest"], self.customer, ctx.session_id)


class VerifySubmission(DiningTool):
    spec = ToolSpec(
        name="verify_submission",
        description=(
            "Read the purchase receipt for the exact proposal in this session. Only a matching "
            "recorded receipt proves the purchase."
        ),
        input_schema={
            "type": "object",
            "properties": {"proposal_id": {"type": "string", "maxLength": 64}},
            "required": ["proposal_id"],
            "additionalProperties": False,
        },
        effect=ToolEffect.NONE,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-dining.verify_submission", behavior_version="1", implementation_version="1"
        ),
    )

    def execute(self, ctx, args):
        self.store.proposal(args["proposal_id"], self.customer, ctx.session_id)
        return {
            "orders": [
                order
                for order in self.store.orders(self.customer)
                if order["proposal_id"] == args["proposal_id"]
            ]
        }


def build_dining_tools(store, customer):
    return [
        cls(store, customer)
        for cls in (
            SearchCatalog,
            InspectDiningPlan,
            ReviseDiningPlan,
            AssessProduct,
            PrepareProposal,
            SubmitProposal,
            VerifySubmission,
        )
    ]
