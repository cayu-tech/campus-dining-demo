"""Stateless scripted tool calls for contract coverage, never model-quality evidence."""

from cayu import ModelStreamEvent, ScriptedModelProvider

from tools.preference import QUESTIONS


def actions(case):
    steps = [("inspect_dining_plan", {"meal_id": case.meal})]
    if case.changes:
        steps.append(
            (
                "revise_dining_plan",
                {
                    "meal_id": case.meal,
                    "expected_revision": 1,
                    "changes": case.changes,
                },
            )
        )
    skus = (
        [case.sku or case.rejected_sku]
        if case.sku or case.rejected_sku
        else [
            "POT-PEELED-10KG",
            "POT-WHOLE-20KG",
            "POT-FROZEN-10KG",
            "POT-MASH-10KG",
        ]
    )
    steps += [("assess_product", {"meal_id": case.meal, "sku": sku}) for sku in skus]
    if case.sku:
        steps.append(
            (
                "prepare_proposal",
                {
                    "meal_id": case.meal,
                    "sku": case.sku,
                    "cases": case.cases,
                    "expected_plan_revision": 2 if case.changes else 1,
                },
            )
        )
    if case.approval:
        steps.append(("submit_proposal", None))
    return steps


class ContractProvider(ScriptedModelProvider):
    def __init__(self, case):
        super().__init__([], name=f"contract-{case.id}")
        self.case = case

    async def stream(self, request):
        results = [
            part
            for message in request.messages
            for part in message.content
            if part.type == "tool_result"
        ]
        script = actions(self.case)
        index = len(results)
        if index < len(script):
            name, arguments = script[index]
            if arguments is None:
                proposal = next(
                    part.structured
                    for part in reversed(results)
                    if part.tool_name == "prepare_proposal"
                )
                arguments = {key: proposal[key] for key in ("proposal_id", "digest")}
            yield ModelStreamEvent.tool_call(id=f"contract-{index}", name=name, arguments=arguments)
            yield ModelStreamEvent.completed({"finish_reason": "tool_calls"})
        elif self.case.clarification:
            yield ModelStreamEvent.tool_call(
                id="contract-clarification", name="ask_user", arguments={"question": QUESTIONS[-1]}
            )
            yield ModelStreamEvent.completed({"finish_reason": "tool_calls"})
        else:
            yield ModelStreamEvent.text_delta("Assessment finished. No order was placed.")
            yield ModelStreamEvent.completed({"finish_reason": "stop"})
