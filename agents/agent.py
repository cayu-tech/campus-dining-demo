"""Agent identity and settings; no application construction at import time."""

from cayu import AgentSpec

from prompts.agent import system_prompt

AGENT = AgentSpec(name="cayu-campus-dining-demo", model="gpt-5.6-sol")


def build_agent(settings, provider_name):
    return AGENT.model_copy(
        update={
            "model": settings.model,
            "provider_name": provider_name,
            "system_prompt": system_prompt(settings.customer, settings.browser),
        }
    )
