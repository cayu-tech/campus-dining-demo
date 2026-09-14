"""Exact arithmetic and enforceable purchasing constraints; no model decisions."""

from decimal import ROUND_HALF_UP, Decimal

from catalog_app.catalog import POLICY, STAFFING


def assess(product, plan, cases=None):
    needed = max(
        0, plan["portions"] * plan["cooked_grams_per_portion"] - plan["available_cooked_grams"]
    )
    usable_per_case = (
        product["pack_count"] * product["grams_each"] * product["cooked_yield_bps"] // 10000
    )
    minimum_cases = (needed + usable_per_case - 1) // usable_per_case
    cases = minimum_cases if cases is None else cases
    if type(cases) is not int or not 0 <= cases <= 100:
        raise ValueError("Cases must be an integer from 0 to 100")
    total = cases * product["case_price_cents"]
    usable = cases * usable_per_case
    prep = cases * product["prep_minutes_per_case"]
    reasons = []
    if needed == 0:
        reasons.append("Existing kitchen inventory covers the meal; no purchase needed")
    if product["category"] != plan["category"]:
        reasons.append("Does not match the meal's requested ingredient")
    if product["form"] not in plan["allowed_forms"]:
        reasons.append("Product form is not approved for this recipe")
    if product["supplier"] not in POLICY["approved_suppliers"]:
        reasons.append("Supplier is not approved")
    if any(d not in product["verified_dietary"] for d in plan["required_dietary"]):
        reasons.append("Required dietary specification is not verified")
    if cases > product["stock"]:
        reasons.append("Insufficient supplier stock")
    if usable < needed:
        reasons.append("Not enough usable cooked quantity")
    if cases > minimum_cases:
        reasons.append(
            "Exceeds the minimum whole cases needed; revise the meal plan before adding surplus"
        )
    if total > min(plan["budget_cents"], POLICY["maximum_order_cents"]):
        reasons.append("Exceeds the meal budget or purchasing authority")
    if prep > plan["prep_minutes_available"]:
        reasons.append("Requires more preparation time than the kitchen has available")
    if (product["delivery_date"], product["delivery_minute"]) > (
        plan["service_date"],
        plan["delivery_deadline_minute"],
    ):
        reasons.append("Delivery arrives after the kitchen's receiving deadline")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "cases": cases,
        "required_cooked_grams": plan["portions"] * plan["cooked_grams_per_portion"],
        "shortfall_cooked_grams": needed,
        "usable_grams_per_case": usable_per_case,
        "total_grams": cases * product["pack_count"] * product["grams_each"],
        "usable_cooked_grams": usable,
        "surplus_cooked_grams": max(0, usable - needed),
        "total_cents": total,
        "prep_minutes": prep,
        "cost_per_usable_kg": str(
            (Decimal(product["case_price_cents"]) * 10 / usable_per_case).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
        ),
        "product_revision": product["revision"],
        "plan_revision": plan["revision"],
        "policy_revision": POLICY["revision"],
    }


def revise(plan, changes):
    if not changes or set(changes) - {
        "staffing",
        "portions",
        "budget_cents",
        "delivery_deadline_minute",
    }:
        raise ValueError(
            "Change only staffing, portions, budget_cents, or delivery_deadline_minute"
        )
    value = dict(plan)
    for key, data in changes.items():
        if key == "staffing":
            if data not in STAFFING:
                raise ValueError("Unknown kitchen staffing schedule")
            value["prep_minutes_available"] = STAFFING[data]
        else:
            maximum = {
                "portions": 5000,
                "budget_cents": POLICY["maximum_order_cents"],
                "delivery_deadline_minute": 1439,
            }[key]
            if type(data) is not int or not 1 <= data <= maximum:
                raise ValueError(f"{key} must be an integer from 1 to {maximum}")
        value[key] = data
    value["revision"] += 1
    value["source"] = f"dining-plan:{plan['meal_id']}:r{value['revision']}"
    return value
