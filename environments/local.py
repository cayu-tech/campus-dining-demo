"""Safe local artifacts and knowledge environment."""

from pathlib import Path

from cayu import (
    ArtifactStore,
    Environment,
    EnvironmentSpec,
    ExecutionProfileBehaviorIdentity,
    KnowledgeAccessScope,
    KnowledgeStore,
    LocalArtifactStore,
)

_PROJECT_ROOT = Path(__file__).parents[1]
_LOCAL_ENVIRONMENT_IDENTITY = ExecutionProfileBehaviorIdentity(
    name="campus-dining-demo.standard.local_environment",
    behavior_version="1",
    implementation_version="1",
)


def build_local_environment(
    *,
    artifact_store: ArtifactStore | None,
    knowledge_store: KnowledgeStore | None,
    knowledge_scope: KnowledgeAccessScope | None,
) -> Environment | None:
    """Construct local collaborators without granting runner, network, or vault authority."""

    selected_artifacts = artifact_store
    if selected_artifacts is None:
        selected_artifacts = LocalArtifactStore(
            _PROJECT_ROOT / "data" / "artifacts",
            store_id="standard-local-artifacts",
        )
    if selected_artifacts is None and knowledge_store is None:
        return None
    return Environment(
        EnvironmentSpec(
            name="local",
            execution_profile_identity=_LOCAL_ENVIRONMENT_IDENTITY,
            metadata={
                "profile": "standard-local-v1",
                "runner": "unavailable",
                "network": "unavailable",
            },
        ),
        artifact_store=selected_artifacts,
        knowledge_store=knowledge_store,
        knowledge_access_scope=knowledge_scope,
    )
