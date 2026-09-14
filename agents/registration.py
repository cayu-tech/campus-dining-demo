"""Register exactly one agent and the explicit policy/tool set."""

from agents.agent import build_agent
from policies.tools import build_tool_exposure_policy, build_tool_policy
from tools.registration import build_agent_tools


def register_agents(
    app, settings, provider_name, store, context_policy, bridge=None, recorded_tools=()
):
    tools = build_agent_tools(store, settings)
    if bridge is not None:
        tools.extend(recorded_tools or bridge.tools)
    names = [t.spec.name for t in tools]
    app.register_agent(
        build_agent(settings, provider_name),
        tools=tools,
        execution_requirements=bridge.execution_requirements if bridge else None,
        context_policy=context_policy,
        tool_policy=build_tool_policy(names),
        tool_exposure_policy=build_tool_exposure_policy(names),
    )
