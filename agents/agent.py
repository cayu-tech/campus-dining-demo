"""Narrow AgentSpec declaration for the starter agent."""

from cayu import AgentSpec

from configuration import configured_model, configured_provider_name
from prompts.agent import SYSTEM_PROMPT_PARTS

# Generated first-tool imports and agent contract additions live in these regions.
# <cayu:generated-agent-imports>
# </cayu:generated-agent-imports>

_SYSTEM_PROMPT_PARTS: list[str] = list(SYSTEM_PROMPT_PARTS)
_WORKFLOW_TOOL_NAMES: list[str] = []
_AUTHORING_STATE: str | None = None

# <cayu:generated-agent-config>
# </cayu:generated-agent-config>

AGENT = AgentSpec(
    name="cayu-campus-dining-demo",
    model=configured_model(),
    provider_name=configured_provider_name(),
    system_prompt="\n".join(_SYSTEM_PROMPT_PARTS) or None,
    workflow_tool_names=tuple(_WORKFLOW_TOOL_NAMES),
    authoring_state=_AUTHORING_STATE,
)
