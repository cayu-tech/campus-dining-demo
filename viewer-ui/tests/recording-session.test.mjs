import assert from "node:assert/strict"
import test from "node:test"
import { prepareRecordingSession } from "../src/lib/recording-session.ts"

function status(session_id) {
  return Response.json({ enabled: true, ready: true, session_id })
}

test("same recording session does not request a worker transition", async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (_url, init) => {
    calls.push(init?.method ?? "GET")
    return status("first")
  }
  try {
    await prepareRecordingSession("first")
    assert.deepEqual(calls, ["GET"])
  } finally {
    globalThis.fetch = original
  }
})

test("switching recording sessions submits one idempotent preparation before readiness", async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "/demo/recording-session")
    calls.push(init?.method ?? "GET")
    if (init?.method === "POST") {
      const body = JSON.parse(init.body)
      assert.equal(body.session_id, "first")
      assert.match(body.request_id, /^[0-9a-f-]{36}$/)
      return Response.json({ ready: false }, { status: 202 })
    }
    return status(calls.length === 1 ? "recording-demo" : "first")
  }
  try {
    await prepareRecordingSession("first")
    assert.deepEqual(calls, ["GET", "POST", "GET"])
  } finally {
    globalThis.fetch = original
  }
})

test("unfinished-session refusal is surfaced without retrying the transition", async () => {
  const original = globalThis.fetch
  let posts = 0
  globalThis.fetch = async (_url, init) => {
    if (init?.method === "POST") {
      posts++
      return Response.json({}, { status: 409 })
    }
    return status("recording-demo")
  }
  try {
    await assert.rejects(prepareRecordingSession("first"), /Finish the current run/)
    assert.equal(posts, 1)
  } finally {
    globalThis.fetch = original
  }
})

test("a healthy worker arriving after 45 seconds does not trigger another preparation", async () => {
  const original = globalThis.fetch
  const originalNow = Date.now
  let now = 0
  let posts = 0
  Date.now = () => {
    const previous = now
    now = 60000
    return previous
  }
  globalThis.fetch = async (_url, init) => {
    if (init?.method === "POST") {
      posts++
      return Response.json({ ready: false }, { status: 202 })
    }
    return Response.json({
      enabled: true,
      ready: true,
      session_id: posts ? "first" : "other",
      transition_timeout_seconds: 180,
    })
  }
  try {
    await prepareRecordingSession("first")
    assert.equal(posts, 1)
  } finally {
    globalThis.fetch = original
    Date.now = originalNow
  }
})

test("failed worker startup stops preparation without submitting another transition", async () => {
  const original = globalThis.fetch
  let posts = 0
  globalThis.fetch = async (_url, init) => {
    if (init?.method === "POST") {
      posts++
      return Response.json({ ready: false }, { status: 202 })
    }
    return posts
      ? Response.json({ enabled: true, ready: false, status: "failed", session_id: "first" })
      : status("other")
  }
  try {
    await assert.rejects(prepareRecordingSession("first"), /Recording setup failed/)
    assert.equal(posts, 1)
  } finally {
    globalThis.fetch = original
  }
})

test("resuming the same session waits for cleanup without requesting a worker replacement", async () => {
  const original = globalThis.fetch
  let reads = 0
  globalThis.fetch = async (_url, init) => {
    assert.notEqual(init?.method, "POST")
    return Response.json({ enabled: true, ready: ++reads > 1, session_id: "first" })
  }
  try {
    await prepareRecordingSession("first")
    assert.equal(reads, 2)
  } finally {
    globalThis.fetch = original
  }
})
