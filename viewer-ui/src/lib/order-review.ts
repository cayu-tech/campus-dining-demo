import type { HumanReviewView, UserInputResolveBody, ToolApprovalBody } from "./generated/server-api/types.gen"

function requireReview(sessionId: string, view: HumanReviewView | undefined, kind: "user_input" | "tool_approval") {
  if (!view || view.status !== "permitted" || view.session_id !== sessionId || view.kind !== kind || !view.reference || !view.interaction_id) {
    throw new Error("The protected review is unavailable or changed. Click Refresh review before deciding.")
  }
  return { view, reference: view.reference, interactionId: view.interaction_id }
}

export function reviewedAnswer(sessionId: string, view: HumanReviewView | undefined, answer: string): UserInputResolveBody {
  const review = requireReview(sessionId, view, "user_input")
  return { session_id: sessionId, input_id: review.interactionId, answer, review_reference: review.reference }
}

export function reviewedApproval(sessionId: string, view: HumanReviewView | undefined, decision: "approve" | "deny", reason: string | null): ToolApprovalBody {
  const review = requireReview(sessionId, view, "tool_approval")
  if (!review.view.tool_round_id || !review.view.tool_call_id) throw new Error("The reviewed proposal is incomplete. Click Refresh review.")
  return { session_id: sessionId, approval_id: review.interactionId, tool_round_id: review.view.tool_round_id, tool_call_id: review.view.tool_call_id, decision, reason, review_reference: review.reference }
}
