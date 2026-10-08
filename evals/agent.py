"""Nine purchasing evals on the real application with private fixture data.

The default plan uses a scripted provider: it checks tools, business outcomes and
the approval gate, not model understanding. `live=True` uses the configured model.
"""

import secrets
import tempfile
from pathlib import Path

from cayu import (
    EvalCase,
    EvalPlan,
    EvalSuite,
    InMemoryKnowledgeStore,
    InMemorySessionStore,
    InMemoryTaskStore,
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
from configuration.settings import CUSTOMER, configured_model
from domain.store import DiningStore
from evals.assertions import DiningOutcome
from evals.cases import select_cases
from evals.fixtures import ContractProvider
from knowledge.curation import publish_purchasing_policy

AGENT = "cayu-campus-dining-demo"


async def build_plan(*, live=False, case_ids=None, directory=None):
    cases = select_cases(case_ids)
    data_dir = Path(directory or tempfile.mkdtemp(prefix="campus-dining-evals-"))
    data_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    store = DiningStore(data_dir / "dining.db")
    knowledge = InMemoryKnowledgeStore()
    await publish_purchasing_policy(knowledge)
    model = configured_model() if live else "scripted-contract"
    provider = configured_provider() if live else ContractProvider(cases[0])
    if live:
        provider.preflight_model_target(model=model)
    app = build_app(
        provider=provider,
        session_store=InMemorySessionStore(),
        task_store=InMemoryTaskStore(),
        knowledge_store=knowledge,
        dining_store=store,
        human_review_key=secrets.token_bytes(32),
    )
    compiled = []
    for index, case in enumerate(cases):
        selected = provider
        if not live and index:
            selected = ContractProvider(case)
            app.register_provider(selected)
        assertions = [
            ToolCalled("inspect_dining_plan"),
            ToolCalled("assess_product"),
            DiningOutcome(store, CUSTOMER, case, app),
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
                    agent_name=AGENT,
                    messages=[Message.text("user", case.prompt)],
                    target=ModelTarget(provider_name=selected.name, model=model),
                    max_steps=20,
                    limits=RunLimits(
                        max_tool_calls=18, max_total_tokens=80000, max_elapsed_seconds=240
                    ),
                    retry_policy=RetryPolicy(max_attempts=1, max_unknown_attempts=1),
                ),
                assertions=assertions,
                metadata={"meal": case.meal, "lane": "live" if live else "scripted-contract"},
            )
        )
    return EvalPlan(
        app=app,
        suite=EvalSuite(
            id="dining-agent-live" if live else "dining-agent-contracts",
            cases=compiled,
            metadata={"model_quality_evidence": live, "fixture_directory": str(data_dir)},
        ),
    )


async def build_eval():
    return await build_plan()
