"""Independent purchasing arithmetic and mutation boundary regressions."""

import json

import pytest
from catalog_app.catalog import POLICY
from catalog_app.planning import assess

from domain.store import PortalStore

CUSTOMER = "north-campus"


def test_short_staffed_meal_requires_prepared_option(settings):
    store = PortalStore(settings.portal_database)
    options = {
        p["sku"]: store.assess(CUSTOMER, "s1", "dinner", p["sku"])
        for p in store.products("potatoes")
    }
    assert [sku for sku, r in options.items() if r["eligible"]] == ["POT-PEELED-10KG"]
    result = options["POT-PEELED-10KG"]
    assert (
        result["shortfall_cooked_grams"],
        result["cases"],
        result["usable_cooked_grams"],
        result["total_cents"],
        result["prep_minutes"],
    ) == (60000, 7, 66500, 17500, 35)
    assert any("preparation" in r for r in options["POT-WHOLE-20KG"]["reasons"])
    assert any("deadline" in r for r in options["POT-FROZEN-10KG"]["reasons"])
    assert any("dietary" in r for r in options["POT-MASH-10KG"]["reasons"])


def test_staffing_change_creates_a_cheaper_feasible_choice(settings):
    store = PortalStore(settings.portal_database)
    store.revise_plan(CUSTOMER, "s1", "dinner", 1, {"staffing": "full-team"}, "change-1")
    result = store.assess(CUSTOMER, "s1", "dinner", "POT-WHOLE-20KG")
    assert result["eligible"]
    assert (
        result["cases"],
        result["total_cents"],
        result["prep_minutes"],
        result["usable_cooked_grams"],
    ) == (4, 9600, 180, 64000)
    assert store.plan(CUSTOMER, "s2")["revision"] == 1
    assert store.plan("south-campus", "s1")["revision"] == 1


def test_budget_infeasibility_does_not_relax_requirements(settings):
    store = PortalStore(settings.portal_database)
    store.revise_plan(CUSTOMER, "s1", "dinner", 1, {"budget_cents": 8000}, "budget")
    assert not any(
        store.assess(CUSTOMER, "s1", "dinner", p["sku"])["eligible"] for p in store.products()
    )
    assert store.orders(CUSTOMER) == []


def test_other_meal_uses_its_own_recipe_and_inventory(settings):
    result = PortalStore(settings.portal_database).assess(
        CUSTOMER, "rice", "rice-lunch", "RICE-WHITE-20KG"
    )
    assert result["eligible"]
    assert (result["shortfall_cooked_grams"], result["cases"], result["total_cents"]) == (
        35000,
        1,
        3600,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_cents": 25001},
        {"staffing": "infinite"},
        {"portions": True},
        {"required_dietary": []},
        {"category": "rice"},
        {},
    ],
)
def test_request_changes_cannot_change_policy(settings, changes):
    store = PortalStore(settings.portal_database)
    with pytest.raises(ValueError):
        store.revise_plan(CUSTOMER, "s", "dinner", 1, changes, "bad")
    assert store.plan(CUSTOMER, "s")["revision"] == 1


def test_plan_change_is_idempotent_but_conflicting_replay_is_rejected(settings):
    store = PortalStore(settings.portal_database)
    args = (CUSTOMER, "s", "dinner", 1, {"staffing": "full-team"}, "stable-key")
    assert store.revise_plan(*args) == store.revise_plan(*args)
    with pytest.raises(ValueError, match="identity"):
        store.revise_plan(CUSTOMER, "s", "dinner", 1, {"budget_cents": 20000}, "stable-key")
    with pytest.raises(ValueError, match="changed"):
        store.revise_plan(CUSTOMER, "s", "dinner", 1, {"budget_cents": 20000}, "different-key")


def test_plan_revision_invalidates_old_draft(settings):
    store = PortalStore(settings.portal_database)
    p = store.prepare(CUSTOMER, "s", "dinner", "POT-PEELED-10KG", 7, 1)
    store.revise_plan(CUSTOMER, "s", "dinner", 1, {"staffing": "full-team"}, "change")
    with pytest.raises(ValueError, match="superseded"):
        store.submit(p["proposal_id"], p["digest"], CUSTOMER, "s")
    with pytest.raises(ValueError, match="changed"):
        store.prepare(CUSTOMER, "s", "dinner", "POT-WHOLE-20KG", 4, 1)
    q = store.prepare(CUSTOMER, "s", "dinner", "POT-WHOLE-20KG", 4, 2)
    assert q["digest"] != p["digest"]


def test_scope_receipt_replay_and_stock_drift(settings):
    store = PortalStore(settings.portal_database)
    p = store.prepare(CUSTOMER, "s1", "dinner", "POT-PEELED-10KG", 7, 1)
    q = store.prepare(CUSTOMER, "s2", "dinner", "POT-PEELED-10KG", 7, 1)
    for customer, sid, digest in [
        ("south-campus", "s1", p["digest"]),
        (CUSTOMER, "s2", p["digest"]),
        (CUSTOMER, "s1", "0" * 64),
    ]:
        with pytest.raises(ValueError):
            store.submit(p["proposal_id"], digest, customer, sid)
    receipt = store.submit(p["proposal_id"], p["digest"], CUSTOMER, "s1")
    assert store.submit(p["proposal_id"], p["digest"], CUSTOMER, "s1") == receipt
    assert store.product("POT-PEELED-10KG")["stock"] == 8
    assert len(store.orders(CUSTOMER)) == 1
    with pytest.raises(ValueError, match="changed"):
        store.submit(q["proposal_id"], q["digest"], CUSTOMER, "s2")


def test_exact_product_facts_rechecked_after_proposal(settings):
    store = PortalStore(settings.portal_database)
    p = store.prepare(CUSTOMER, "s", "dinner", "POT-PEELED-10KG", 7, 1)
    product = store.product(p["sku"])
    product["delivery_minute"] = 1100
    with store.connect() as db:
        db.execute("UPDATE products SET payload=? WHERE sku=?", (json.dumps(product), p["sku"]))
    with pytest.raises(ValueError, match="changed"):
        store.submit(p["proposal_id"], p["digest"], CUSTOMER, "s")


def test_surplus_and_unknown_dietary_evidence_are_not_admitted(settings):
    store = PortalStore(settings.portal_database)
    plan = store.plan(CUSTOMER, "s")
    p = store.product("POT-PEELED-10KG")
    assert not assess(p, plan, 6)["eligible"]
    assert not assess(p, plan, 8)["eligible"]
    p["verified_dietary"] = []
    assert not assess(p, plan)["eligible"]
    p["supplier"] = "Unapproved supplier"
    assert not assess(p, plan)["eligible"]
    assert POLICY["requires_exact_order_approval"]
