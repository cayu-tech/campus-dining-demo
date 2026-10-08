"""Tool exposure and authorization policy for registered agents."""

from cayu import (
    DenyPatternRule,
    EveryCallRule,
    ExecutionProfileBehaviorIdentity,
    ParameterConstrainedToolPolicy,
    RequiredFieldRule,
    StaticToolExposurePolicy,
    StaticToolPolicy,
    ToolExposurePolicy,
    ToolPolicy,
    ToolPolicyDecision,
)

_TOOL_POLICY_IDENTITY = ExecutionProfileBehaviorIdentity(
    name="campus-dining-demo.standard.tool_policy",
    behavior_version="2",
    implementation_version="2",
)


def build_tool_policy(external_tool_names: tuple[str, ...]) -> ToolPolicy:
    """Authorize safe reads and pause before selected external effects."""

    rules = {}
    # Valid questions remain allowed so Cayu's durable user-input pause can
    # intercept them. Validity rules always deny malformed input, including
    # when the external-effect decision below requires approval.
    rules["ask_user"] = (RequiredFieldRule("question"),)
    if "remember_knowledge" in external_tool_names:
        # Every schema-valid knowledge proposal matches this rule and therefore
        # requires approval. The knowledge store still writes it as pending.
        rules["remember_knowledge"] = (DenyPatternRule("text", patterns=(r"(?s).*",)),)
    for name in external_tool_names:
        # Every other listed external tool pauses for approval on every call
        # (or is denied when the approvals capability is not selected).
        rules.setdefault(name, (EveryCallRule(),))
    if rules:
        return ParameterConstrainedToolPolicy(
            rules,
            decision=ToolPolicyDecision.REQUIRE_APPROVAL,
            execution_profile_identity=_TOOL_POLICY_IDENTITY,
        )
    return StaticToolPolicy(deny=external_tool_names)


def build_tool_exposure_policy(tools: tuple[str, ...]) -> ToolExposurePolicy:
    """Expose one explicit list; registration alone never grants model visibility."""

    return StaticToolExposurePolicy(profile_id="standard-local-v1", tools=tools)
