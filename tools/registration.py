"""Native model-callable tools selected for the starter agent."""

from cayu import (
    ExecutionProfileBehaviorIdentity,
    ListArtifactsTool,
    ListKnowledgeTool,
    ReadKnowledgeTool,
    RememberKnowledgePolicy,
    RememberKnowledgeTool,
    SearchKnowledgeTool,
    Tool,
)

from domain.store import DiningStore
from knowledge.retrieval import KNOWLEDGE_NAMESPACE
from tools.dining import build_dining_tools
from tools.questions import AskDiningQuestion

_REMEMBER_KNOWLEDGE_IDENTITY = ExecutionProfileBehaviorIdentity(
    name="campus-dining-demo.standard.remember_knowledge",
    behavior_version="1",
    implementation_version="1",
)


def build_agent_tools(store: DiningStore, customer: str) -> tuple[Tool, ...]:
    """Construct the dining tools and the safe local tools selected by the scaffold plan."""

    tools: list[Tool] = list(build_dining_tools(store, customer))
    tools.append(ListArtifactsTool())
    tools.extend(
        (
            ListKnowledgeTool(),
            SearchKnowledgeTool(default_namespace=KNOWLEDGE_NAMESPACE),
            ReadKnowledgeTool(),
            RememberKnowledgeTool(
                spec=RememberKnowledgeTool.spec.model_copy(
                    update={
                        "execution_profile_identity": _REMEMBER_KNOWLEDGE_IDENTITY,
                    },
                    deep=True,
                ),
                policy=RememberKnowledgePolicy(
                    default_namespace=KNOWLEDGE_NAMESPACE,
                ),
            ),
        )
    )
    tools.append(AskDiningQuestion())
    return tuple(tools)


def external_effect_tool_names() -> tuple[str, ...]:
    """Return tools whose calls pause for approval under policies/tools.py.

    To make a tool ask a person before it acts, add its name here (or generate it
    with ``cayu generate tool NAME --effect external``, which does this for you).
    """

    return ("remember_knowledge", "submit_proposal")
