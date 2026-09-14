"""Admitted browser uses public Cayu WebBridge, never host Playwright fallback."""

from cayu import (
    ApprovedEgressDestination,
    BrowserEgressPolicy,
    BrowserSessionTool,
    BrowserVisualPolicy,
    ExecutionProfileBehaviorIdentity,
    VirtualEgressEnvironmentFactory,
    WebBridge,
)
from cayu.egress.docker_adapter import DockerEgressAdapter
from cayu.runners import PINNED_BROWSER_SESSION_WORKLOAD

from configuration.recordings import active_recording_config
from configuration.viewer import viewer_configuration, viewer_setup
from integrations.fixture_upstream import FixturePortalUpstream

HOST = "supplier.campus-demo.test"


def build_browser(settings, artifacts, knowledge, scope, event_emitter=None):
    viewer = viewer_configuration(settings)
    factory = VirtualEgressEnvironmentFactory(
        event_emitter=event_emitter,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name=f"campus-demo:{settings.customer}:browser",
            behavior_version="4",
            implementation_version="2026-09-09.1",
        ),
        policies={
            "supplier": BrowserEgressPolicy(
                name="supplier", allowed_hosts=(HOST,), allowed_path_prefixes=("/",)
            )
        },
        approved_destinations=(
            ApprovedEgressDestination(destination=HOST, policy_name="supplier"),
        ),
        adapter=DockerEgressAdapter(
            seccomp_profile=str(settings.seccomp_path.resolve()),
            reconnect_state_dir=str(settings.data_dir / "docker-ownership"),
            control_server_container_id=viewer["control_server_container_id"] if viewer else None,
        ),
        upstream=FixturePortalUpstream(settings, HOST),
        setup_commands=viewer_setup(settings),
        image=PINNED_BROWSER_SESSION_WORKLOAD.image,
        artifact_store=artifacts,
        knowledge_store=knowledge,
        knowledge_access_scope_factory=lambda request: scope,
    )
    interactive_options = {
        "max_sessions": 1,
        "max_operations": 40,
        "idle_timeout_seconds": 180,
        "visual_policy": BrowserVisualPolicy(
            artifact_store_id=artifacts.id,
            allowed_origins=(f"https://{HOST}",),
            retention="application_managed",
            publish_to_model=False,
            allow_coordinate_fallback=False,
            max_captures=12,
        ),
    }

    bridge = WebBridge.sandboxed_browser(
        environment=factory,
        browser_image=PINNED_BROWSER_SESSION_WORKLOAD.image,
        interactive=True,
        interactive_options=interactive_options,
    )
    original = bridge.tools[0]
    recording = active_recording_config(settings)
    recorded_tools = []
    if recording is not None:
        recorded_tools.append(
            BrowserSessionTool(
                expected_runner_candidate=original.expected_runner_candidate,
                expected_environment_authority=original.expected_environment_authority,
                expected_workload_authority=original.expected_workload_authority,
                expected_artifact_store_id=original.expected_artifact_store_id,
                recording=recording,
                **interactive_options,
            )
        )
    return factory, bridge, recorded_tools
