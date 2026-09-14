"""Application-owned clarification questions with protected human input."""

from cayu import ExecutionProfileBehaviorIdentity, UserInputTool

PREFERENCE_TOOL = "ask_user"
QUESTIONS = (
    "Which meal should I help with: the potato dinner, rice lunch, or carrot side?",
    "What will you use this ingredient for, and are there any required product specifications?",
    "How many people are you serving?",
    "What is the maximum budget for this purchase?",
    "What is the latest time the kitchen can receive the delivery?",
    "Will the kitchen have the full team available, or be short-staffed?",
    "No option meets the current plan. Would you like to change the budget, receiving deadline, or staffing, or refer this to the dining manager?",
)
PREFERENCE_QUESTION = QUESTIONS[0]


class AskDiningQuestion(UserInputTool):
    @property
    def spec(self):
        return UserInputTool.spec.model_copy(
            update={
                "name": PREFERENCE_TOOL,
                "description": "Ask only a material question not answered by the user's message or dining records. Choose the applicable question exactly.",
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"question": {"type": "string", "enum": list(QUESTIONS)}},
                    "required": ["question"],
                },
                "execution_profile_identity": ExecutionProfileBehaviorIdentity(
                    name="campus-dining:clarification",
                    behavior_version="1",
                    implementation_version="2026-09-09.1",
                ),
            }
        )
