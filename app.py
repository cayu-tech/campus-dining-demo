"""Composition only. No service startup, model calls, or seeding at import."""

from cayu import CayuApp, EnvironmentSpec, LocalArtifactStore

from agents.registration import register_agents
from configuration.providers import configured_provider
from configuration.providers import (
    validate_run_configuration as validate_run_configuration,  # noqa: PLC0414
)
from configuration.runtime import build_runtime_options
from configuration.settings import settings_from_environment
from configuration.storage import build_stores
from configuration.viewer import browser_control_options
from domain.store import PortalStore
from environments.browser import build_browser
from environments.local import build_local_environment
from knowledge.retrieval import build_knowledge_scope
from memory.context import build_context_policy
from policies.human_review import OrderReview


def build_app(
    *,
    settings=None,
    provider=None,
    session_store=None,
    task_store=None,
    knowledge_store=None,
    artifact_store=None,
    browser_events=None,
):
    settings = settings or settings_from_environment()
    scope = build_knowledge_scope(settings)
    stores = build_stores(
        settings,
        scope,
        session_store=session_store,
        task_store=task_store,
        knowledge_store=knowledge_store,
    )
    runtime = build_runtime_options(settings)
    app = CayuApp(
        human_review_policy=OrderReview(settings),
        browser_control=browser_control_options(settings),
        session_store=stores.session_store,
        task_store=stores.task_store,
        knowledge_store=stores.knowledge_store,
        knowledge_access_scope=scope,
        config=runtime.config,
        enable_logging=runtime.enable_logging,
        request_footprint=runtime.request_footprint,
        knowledge_review_namespace=runtime.knowledge_review_namespace,
    )
    selected = provider if provider is not None else configured_provider()
    app.register_provider(selected, default=True)
    artifacts = (
        artifact_store
        if artifact_store is not None
        else LocalArtifactStore(settings.data_dir / "artifacts", store_id="campus-demo-artifacts")
    )
    bridge = None
    recorded_tools = []
    if settings.browser:
        factory, bridge, recorded_tools = build_browser(
            settings, artifacts, stores.knowledge_store, scope, browser_events
        )
        app.register_environment_factory(
            EnvironmentSpec(
                name="demo-browser", execution_profile_identity=factory.execution_profile_identity
            ),
            factory,
            default=True,
        )
    else:
        app.register_environment(
            build_local_environment(artifacts, stores.knowledge_store, scope), default=True
        )
    register_agents(
        app,
        settings,
        selected.name,
        PortalStore(settings.portal_database),
        build_context_policy(settings),
        bridge,
        recorded_tools,
    )
    return app
