"""Check the eval harness itself, including known bad candidate decisions."""

import asyncio
from dataclasses import replace

from cayu import run_eval_plan

from evals.agent import build_plan
from evals.cases import all_cases, select_cases
from operations.lifecycle import close_app


def test_contract_suite_is_repeatable_and_isolated(tmp_path):
    async def run():
        plan = await build_plan(directory=tmp_path / "fixtures")
        try:
            result = await run_eval_plan(plan, max_concurrency=2)
            assert result.status.value == "passed", [(c.case_id, c.status) for c in result.cases]
            assert len(result.cases) == len(all_cases()) == 9
            # Providers derive the next scripted step from each fresh trial's history.
            again = await run_eval_plan(plan)
            assert again.status.value == "passed"
        finally:
            await close_app(plan.app)

    asyncio.run(run())


def test_grader_rejects_a_feasible_but_wrong_recommendation(tmp_path):
    async def run():
        plan = await build_plan(case_ids=["full-team"], directory=tmp_path / "fixtures")
        provider = plan.app.get_provider("contract-full-team")
        provider.case = replace(provider.case, sku="POT-PEELED-10KG", cases=7, cost=17500)
        try:
            result = await run_eval_plan(plan)
            assert result.status.value == "failed"
            outcome = next(a for a in result.cases[0].assertions if a.name == "DiningOutcome")
            assert outcome.outcome.value == "failed" and "Draft mismatch" in outcome.message
        finally:
            await close_app(plan.app)

    asyncio.run(run())


def test_grader_rejects_extra_unrequested_plan_changes(tmp_path):
    async def run():
        plan = await build_plan(case_ids=["full-team"], directory=tmp_path / "fixtures")
        provider = plan.app.get_provider("contract-full-team")
        provider.case = replace(provider.case, changes={"staffing": "full-team", "portions": 390})
        try:
            result = await run_eval_plan(plan)
            assert result.status.value == "failed"
            outcome = next(a for a in result.cases[0].assertions if a.name == "DiningOutcome")
            assert "portions" in outcome.message
        finally:
            await close_app(plan.app)

    asyncio.run(run())


def test_unknown_case_is_not_silently_dropped():
    import pytest

    with pytest.raises(ValueError, match="Unknown eval cases"):
        select_cases(["not-a-case"])
