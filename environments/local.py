"""No runner or network access in native-tool development mode."""

from cayu import Environment, EnvironmentSpec, ExecutionProfileBehaviorIdentity


def build_local_environment(artifacts, knowledge, scope):
    return Environment(
        EnvironmentSpec(
            name="demo-local",
            execution_profile_identity=ExecutionProfileBehaviorIdentity(
                name="campus-demo:local", behavior_version="1", implementation_version="2026-09-07.2"
            ),
        ),
        artifact_store=artifacts,
        knowledge_store=knowledge,
        knowledge_access_scope=scope,
    )
