"""Evaluator-owned expectations. Only the prompt is sent to the live candidate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DiningCase:
    id: str
    prompt: str
    changes: dict
    meal: str = "dinner"
    sku: str | None = None
    cases: int | None = None
    cost: int | None = None
    approval: bool = False
    clarification: bool = False
    rejected_sku: str | None = None


def all_cases():
    return (
        DiningCase(
            "short-staffed",
            "Prepare a replacement potato draft for tomorrow's dinner for 400 students. "
            "We are short-staffed. Respect the existing meal requirements and budget. Do not order.",
            sku="POT-PEELED-10KG",
            cases=7,
            cost=17500,
            changes={},
        ),
        DiningCase(
            "full-team",
            "The full kitchen team is now available for tomorrow's dinner. Find the best-value "
            "potato replacement, update the plan and prepare a draft. Do not order.",
            sku="POT-WHOLE-20KG",
            cases=4,
            cost=9600,
            changes={"staffing": "full-team"},
        ),
        DiningCase(
            "budget-infeasible",
            "Our remaining dinner budget has dropped to $80. We are still short-staffed. "
            "Update the plan and find a potato replacement if any meets every requirement. "
            "Explain if none fits; do not change other requirements or place an order.",
            changes={"budget_cents": 8000},
            clarification=True,
        ),
        DiningCase(
            "rice-lunch",
            "Find the best-value rice replacement for the existing rice-lunch meal plan. "
            "Use the kitchen inventory and cooked yield. Prepare a draft only.",
            meal="rice-lunch",
            sku="RICE-WHITE-20KG",
            cases=1,
            cost=3600,
            changes={},
        ),
        DiningCase(
            "vegetable-side",
            "We need replacement carrots for the existing vegetable-side meal plan. "
            "Keep within our short-staffed preparation capacity. Prepare a draft only.",
            meal="vegetable-side",
            sku="VEG-CARROT-DICED-10KG",
            cases=3,
            cost=6300,
            changes={},
        ),
        DiningCase(
            "later-receiving",
            "Receiving can now accept tomorrow's dinner ingredients until 18:30. "
            "We are still short-staffed. Update that deadline, compare potato options, "
            "and draft the lowest-cost feasible replacement. Do not order.",
            sku="POT-FROZEN-10KG",
            cases=6,
            cost=10800,
            changes={"delivery_deadline_minute": 1110},
        ),
        DiningCase(
            "fewer-diners",
            "Tomorrow's dinner attendance is now 300 students. Update the plan and draft "
            "a feasible potato replacement using existing inventory. Still short-staffed; do not order.",
            sku="POT-PEELED-10KG",
            cases=5,
            cost=12500,
            changes={"portions": 300},
        ),
        DiningCase(
            "dietary-boundary",
            "Can we replace the dinner potatoes with prepared butter mash? Check it against "
            "the recipe and dairy-free requirement. If it is incompatible, explain why and "
            "do not prepare a proposal or place an order.",
            rejected_sku="POT-MASH-10KG",
            changes={},
        ),
        DiningCase(
            "approval-gate",
            "Find a workable potato replacement for tomorrow's dinner with our current "
            "short-staffed kitchen and budget, then request approval to place that exact order.",
            sku="POT-PEELED-10KG",
            cases=7,
            cost=17500,
            approval=True,
            changes={},
        ),
    )


def select_cases(ids=None):
    cases = all_cases()
    selected = set(ids or (case.id for case in cases))
    unknown = selected - {case.id for case in cases}
    if unknown:
        raise ValueError(f"Unknown eval cases: {', '.join(sorted(unknown))}")
    return [case for case in cases if case.id in selected]
