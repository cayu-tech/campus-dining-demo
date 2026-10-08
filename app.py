"""Composition root for campus-dining-demo.

This module constructs and wires the application. Implement prompts, tools,
policies, environments, workflows, operations, domain rules, and integrations
in their owning packages, then connect them through the explicit registration
seams imported here.
"""

from cayu import (
    ArtifactStore,
    CayuApp,
    KnowledgeStore,
    ModelProvider,
    SessionStore,
    TaskStore,
)
from cayu.model_policy import configured_model_policy

from agents.registration import register_agents
from configuration.providers import (
    configured_provider,
    validate_run_configuration as validate_run_configuration,
)
from configuration.runtime import build_runtime_options
from configuration.settings import CUSTOMER, configured_dining_database, configured_human_review_key
from configuration.storage import build_stores
from domain.store import DiningStore
from environments.local import build_local_environment
from knowledge.retrieval import build_knowledge_scope
from memory.context import build_context_policy
from policies.human_review import OrderReview


def build_app(
    *,
    provider: ModelProvider | None = None,
    session_store: SessionStore | None = None,
    task_store: TaskStore | None = None,
    knowledge_store: KnowledgeStore | None = None,
    artifact_store: ArtifactStore | None = None,
    dining_store: DiningStore | None = None,
    human_review_key: bytes | None = None,
) -> CayuApp:
    """Construct a fresh process-scoped application graph.

    Injected stores and providers are public hermetic-test seams. Importing this
    module never constructs the application or connects to an external service.
    """

    knowledge_scope = build_knowledge_scope()
    stores = build_stores(
        session_store=session_store,
        task_store=task_store,
        knowledge_store=knowledge_store,
        knowledge_scope=knowledge_scope,
    )
    runtime = build_runtime_options()
    dining = dining_store if dining_store is not None else DiningStore(configured_dining_database())
    review_key = human_review_key if human_review_key is not None else configured_human_review_key()
    app = CayuApp(
        human_review_policy=OrderReview(dining, CUSTOMER, review_key),
        config=runtime.config,
        session_store=stores.session_store,
        task_store=stores.task_store,
        knowledge_store=stores.knowledge_store,
        knowledge_access_scope=knowledge_scope,
        knowledge_review_namespace=runtime.knowledge_review_namespace,
        request_footprint=runtime.request_footprint,
        enable_logging=runtime.enable_logging,
        model_policy=configured_model_policy(
            None if stores.configured is None else stores.configured.model_policy_store
        ),
    )
    selected_provider = provider if provider is not None else configured_provider()
    app.register_provider(selected_provider, default=True)
    environment = build_local_environment(
        artifact_store=artifact_store,
        knowledge_store=stores.knowledge_store,
        knowledge_scope=knowledge_scope,
    )
    if environment is not None:
        app.register_environment(environment, default=True)
    register_agents(
        app,
        dining_store=dining,
        customer=CUSTOMER,
        provider_override=provider,
        context_policy=build_context_policy(),
    )
    return app
