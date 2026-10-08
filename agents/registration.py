"""Explicit agent, tool, policy, and runtime registration seam."""

from cayu import AgentSpec, CayuApp, ModelProvider
from cayu import ContextPolicy

from agents.agent import AGENT
from configuration import resolve_configured_agent
from domain.store import DiningStore
from policies.tools import build_tool_exposure_policy, build_tool_policy
from tools.registration import build_agent_tools, external_effect_tool_names

# Generated tool-backed slices add imports only inside this owned region.
# <cayu:generated-imports>
# </cayu:generated-imports>


def _agent_for_provider_override(
    agent: AgentSpec, provider: ModelProvider | None
) -> AgentSpec:
    agent = resolve_configured_agent(agent)
    if provider is None:
        return agent
    return agent.model_copy(update={"provider_name": provider.name})


def register_agents(
    app: CayuApp,
    *,
    dining_store: DiningStore,
    customer: str,
    provider_override: ModelProvider | None = None,
    context_policy: ContextPolicy | None = None,
) -> None:
    """Register every agent and its explicitly constructed capabilities."""

    starter_tools = list(build_agent_tools(dining_store, customer))
    # Every tool named here pauses for human approval before each call, or is
    # denied without the approvals capability (see policies/tools.py). Resolve
    # pauses on the control plane's Pending page.
    starter_external_tool_names = list(external_effect_tool_names())
    # <cayu:generated-starter-tools>
    # </cayu:generated-starter-tools>
    app.register_agent(
        _agent_for_provider_override(AGENT, provider_override),
        tools=starter_tools,
        context_policy=context_policy,
        tool_exposure_policy=build_tool_exposure_policy(
            tuple(tool.spec.name for tool in starter_tools)
        ),
        tool_policy=build_tool_policy(tuple(starter_external_tool_names)),
    )
    # <cayu:generated-registrations>
    # </cayu:generated-registrations>
