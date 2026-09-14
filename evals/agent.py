"""Native Cayu evaluation plans with private, isolated fixture data."""

from pathlib import Path
from uuid import uuid4

from cayu import (
    EvalCase,
    EvalPlan,
    EvalSuite,
    Message,
    ModelTarget,
    RetryPolicy,
    RunLimits,
    RunRequest,
    ToolCalled,
    ToolNotCalled,
)

from app import build_app
from configuration.providers import configured_provider
from configuration.settings import ROOT, Settings, configured_model
from domain.store import PortalStore
from evals.assertions import DiningOutcome
from evals.cases import select_cases
from evals.fixtures import ContractProvider
from operations.initialize import initialize


async def build_plan(*, live=False, case_ids=None, directory=None):
    cases = select_cases(case_ids)
    data_dir = Path(directory) if directory else ROOT / ".cayu/eval-fixtures" / uuid4().hex
    data_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    settings = Settings(
        data_dir=data_dir, browser=False, model=configured_model() if live else "scripted-contract"
    )
    await initialize(settings)
    provider = configured_provider() if live else ContractProvider(cases[0])
    if live:
        provider.preflight_model_target(model=settings.model)
    app = build_app(settings=settings, provider=provider)
    store = PortalStore(settings.portal_database)
    compiled = []
    for index, case in enumerate(cases):
        selected = provider
        if not live and index:
            selected = ContractProvider(case)
            app.register_provider(selected)
        assertions = [
            ToolCalled("inspect_dining_plan"),
            ToolCalled("assess_product"),
            DiningOutcome(store, settings.customer, case, app, settings),
        ]
        if not case.approval:
            assertions.append(ToolNotCalled("submit_proposal"))
        if case.sku:
            assertions.append(ToolCalled("prepare_proposal", max_count=1))
        else:
            assertions.append(ToolNotCalled("prepare_proposal"))
        compiled.append(
            EvalCase(
                id=case.id,
                request=RunRequest(
                    agent_name="cayu-campus-dining-demo",
                    messages=[Message.text("user", case.prompt)],
                    target=ModelTarget(provider_name=selected.name, model=settings.model),
                    max_steps=20,
                    limits=RunLimits(
                        max_tool_calls=18, max_total_tokens=80000, max_elapsed_seconds=240
                    ),
                    retry_policy=RetryPolicy(max_attempts=1, max_unknown_attempts=1),
                ),
                assertions=assertions,
                metadata={
                    "meal": case.meal,
                    "lane": "live-native" if live else "scripted-contract",
                },
            )
        )
    return EvalPlan(
        app=app,
        suite=EvalSuite(
            id="dining-agent-live" if live else "dining-agent-contracts",
            cases=compiled,
            metadata={
                "fixture_version": "2026-09-10.1",
                "browser": False,
                "model_quality_evidence": live,
                "fixture_directory": str(data_dir),
            },
        ),
    )


async def build_eval():
    return await build_plan()


async def build_live_eval():
    return await build_plan(live=True)
