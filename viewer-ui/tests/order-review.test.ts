import assert from "node:assert/strict"
import { test } from "node:test"
import { reviewedAnswer, reviewedApproval } from "../src/lib/order-review.ts"
import type { HumanReviewView } from "../src/lib/generated/server-api/types.gen.ts"

const view = { status: "permitted", session_id: "ui-test", kind: "user_input", interaction_id: "protected-input-uuid", reference: { content_tag: "displayed-review" } } as HumanReviewView

test("decision uses protected identities, not public pending-event display aliases", () => {
  const body = reviewedAnswer("ui-test", view, "Smaller packs")
  assert.equal(body.input_id, "protected-input-uuid")
  assert.notEqual(body.input_id, "cayu_event_34:input_id")
  assert.equal(body.review_reference, view.reference)
  const approval = reviewedApproval("ui-test", { ...view, kind: "tool_approval", interaction_id: "protected-approval-uuid", tool_round_id: "protected-round", tool_call_id: "protected-call" }, "approve", null)
  assert.equal(approval.approval_id, "protected-approval-uuid")
  assert.equal(approval.tool_round_id, "protected-round")
  assert.equal(approval.tool_call_id, "protected-call")
})

test("missing, wrong-session and wrong-kind reviews fail with a visible error", () => {
  assert.throws(() => reviewedAnswer("ui-test", undefined, "Small"), /Refresh review/)
  assert.throws(() => reviewedAnswer("another-session", view, "Small"), /Refresh review/)
  assert.throws(() => reviewedAnswer("ui-test", { ...view, status: "redacted" }, "Small"), /Refresh review/)
  assert.throws(() => reviewedApproval("ui-test", view, "approve", null), /Refresh review/)
})
