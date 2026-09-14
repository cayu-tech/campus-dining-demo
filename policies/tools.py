"""Inspectable Runtime approval rules; business tools validate exact scope and digest."""

from cayu import (
    DenyPatternRule,
    ExecutionProfileBehaviorIdentity,
    ParameterConstrainedToolPolicy,
    RequiredFieldRule,
    StaticToolExposurePolicy,
    ToolPolicyDecision,
)


def build_tool_policy(names):
    rules = {
        "ask_user": (RequiredFieldRule("question"),),
        "remember_knowledge": (DenyPatternRule("text", patterns=(r"(?s).*",)),),
        "submit_proposal": (DenyPatternRule("proposal_id", patterns=(r"(?s).*",)),),
    }
    if "browser_session" in names:
        rules["browser_session"] = (RequiredFieldRule("operation"),)
    return ParameterConstrainedToolPolicy(
        rules,
        decision=ToolPolicyDecision.REQUIRE_APPROVAL,
        execution_profile_identity=ExecutionProfileBehaviorIdentity(
            name="campus-demo:approval-policy",
            behavior_version="1",
            implementation_version="2026-09-09.1",
        ),
    )


def build_tool_exposure_policy(names):
    return StaticToolExposurePolicy(profile_id="campus-demo-v1", tools=tuple(name for name in names if name not in {"remember_knowledge", "list_artifacts"}))
