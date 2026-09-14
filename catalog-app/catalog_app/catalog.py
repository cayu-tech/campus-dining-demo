"""Fictional supplier facts and meal plans, separate from purchasing policy."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

POLICY = {
    "id": "campus-purchasing",
    "revision": 1,
    "approved_suppliers": ["Campus Fresh", "Pantry Partners"],
    "maximum_order_cents": 25000,
    "requires_exact_order_approval": True,
    "rules": [
        "Respect the customer's meal quantity, budget, delivery deadline, and kitchen capacity.",
        "Use verified supplier specifications for recipe and dietary compatibility; unknown is not compliant.",
        "Compare total cost and usable cooked quantity, not the cheapest case price.",
        "Do not change the menu, dietary requirements, or supplier policy to make an option pass.",
        "Explain infeasibility and request a decision when no available option meets the plan.",
        "Only submit a reviewed exact proposal; recheck facts, stock, and plan revision before purchase.",
    ],
}


def product(sku, name, category, form, grams, price, stock, yield_bps, prep, delivery, dietary):
    return {
        "sku": sku,
        "name": name,
        "category": category,
        "form": form,
        "pack_count": 1,
        "grams_each": grams,
        "case_price_cents": price,
        "stock": stock,
        "cooked_yield_bps": yield_bps,
        "prep_minutes_per_case": prep,
        "delivery_day_offset": 1,
        "delivery_minute": delivery,
        "supplier": "Campus Fresh" if category == "potatoes" else "Pantry Partners",
        "verified_dietary": dietary,
        "revision": 1,
        "specification_source": f"supplier-spec:{sku}:r1",
    }


PRODUCTS = (
    product(
        "POT-WHOLE-20KG",
        "Russet potatoes · whole",
        "potatoes",
        "whole",
        20000,
        2400,
        12,
        8000,
        45,
        480,
        ["dairy-free", "vegan"],
    ),
    product(
        "POT-PEELED-10KG",
        "Peeled diced potatoes",
        "potatoes",
        "peeled diced",
        10000,
        2500,
        15,
        9500,
        5,
        540,
        ["dairy-free", "vegan"],
    ),
    product(
        "POT-FROZEN-10KG",
        "Frozen diced potatoes",
        "potatoes",
        "frozen diced",
        10000,
        1800,
        20,
        10000,
        3,
        1080,
        ["dairy-free", "vegan"],
    ),
    product(
        "POT-MASH-10KG",
        "Prepared butter mashed potatoes",
        "potatoes",
        "prepared mash",
        10000,
        1700,
        20,
        10000,
        2,
        540,
        [],
    ),
    product(
        "POT-BABY-10KG",
        "Baby roasting potatoes",
        "potatoes",
        "whole",
        10000,
        2900,
        0,
        9000,
        30,
        480,
        ["dairy-free", "vegan"],
    ),
    product(
        "RICE-WHITE-20KG",
        "Long-grain white rice",
        "rice",
        "dry",
        20000,
        3600,
        10,
        30000,
        30,
        480,
        ["dairy-free", "vegan"],
    ),
    product(
        "RICE-READY-12KG",
        "Cooked long-grain rice",
        "rice",
        "ready cooked",
        12000,
        5500,
        10,
        10000,
        2,
        540,
        ["dairy-free", "vegan"],
    ),
    product(
        "VEG-CARROT-10KG",
        "Whole carrots",
        "carrots",
        "whole",
        10000,
        1400,
        20,
        8000,
        40,
        480,
        ["dairy-free", "vegan"],
    ),
    product(
        "VEG-CARROT-DICED-10KG",
        "Peeled diced carrots",
        "carrots",
        "peeled diced",
        10000,
        2100,
        20,
        9500,
        5,
        540,
        ["dairy-free", "vegan"],
    ),
)

MEALS = {
    "dinner": {
        "name": "Tomorrow's dinner · potato side",
        "category": "potatoes",
        "portions": 400,
        "cooked_grams_per_portion": 200,
        "available_cooked_grams": 20000,
        "allowed_forms": ["whole", "peeled diced", "frozen diced"],
        "budget_cents": 18000,
    },
    "rice-lunch": {
        "name": "Tomorrow's lunch · rice side",
        "category": "rice",
        "portions": 300,
        "cooked_grams_per_portion": 150,
        "available_cooked_grams": 10000,
        "allowed_forms": ["dry", "ready cooked"],
        "budget_cents": 18000,
    },
    "vegetable-side": {
        "name": "Tomorrow's dinner · carrot side",
        "category": "carrots",
        "portions": 300,
        "cooked_grams_per_portion": 100,
        "available_cooked_grams": 5000,
        "allowed_forms": ["whole", "peeled diced"],
        "budget_cents": 12000,
    },
}
STAFFING = {"short-staffed": 45, "full-team": 240}


def default_plan(meal_id, service_date):
    if meal_id not in MEALS:
        raise ValueError("Unknown meal; choose dinner, rice-lunch, or vegetable-side")
    return {
        "meal_id": meal_id,
        "revision": 1,
        **MEALS[meal_id],
        "service_date": service_date,
        "delivery_deadline_minute": 900,
        "staffing": "short-staffed",
        "prep_minutes_available": STAFFING["short-staffed"],
        "required_dietary": ["dairy-free"],
        "source": f"dining-plan:{meal_id}:r1",
    }


def tomorrow():
    return (datetime.now(ZoneInfo("America/Los_Angeles")).date() + timedelta(days=1)).isoformat()
