"""Explicit tools; no model-controlled tenant selection or network configuration."""

from cayu import (
    ListArtifactsTool,
    ListKnowledgeTool,
    ReadKnowledgeTool,
    RememberKnowledgeTool,
    SearchKnowledgeTool,
)

from tools.business import (
    AssessProduct,
    InspectDiningPlan,
    PrepareProposal,
    ReviseDiningPlan,
    SearchCatalog,
    SubmitProposal,
    VerifySubmission,
)
from tools.preference import AskDiningQuestion


def build_agent_tools(store, settings):
    tools = [
        ListKnowledgeTool(),
        RememberKnowledgeTool(),
        ListArtifactsTool(),
        SearchKnowledgeTool(),
        ReadKnowledgeTool(),
        AskDiningQuestion(),
        InspectDiningPlan(store, settings.customer),
        ReviseDiningPlan(store, settings.customer),
        AssessProduct(store, settings.customer),
        PrepareProposal(store, settings.customer),
        SubmitProposal(store, settings.customer),
        VerifySubmission(store, settings.customer),
    ]
    if not settings.browser:
        tools.insert(0, SearchCatalog(store, settings.customer))
    return tools
