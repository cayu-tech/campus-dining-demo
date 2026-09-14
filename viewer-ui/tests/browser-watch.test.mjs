import assert from "node:assert/strict"
import test from "node:test"
import { BrowserControlHttpError } from "../src/lib/browser-control-client.ts"
import { startBrowserWatch } from "../src/lib/browser-watch.ts"

const flush = () => new Promise((resolve) => setImmediate(resolve))
function frame() {
  const bytes = new ArrayBuffer(24)
  new Uint8Array(bytes).set([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82])
  new DataView(bytes).setUint32(16, 16)
  new DataView(bytes).setUint32(20, 16)
  return bytes
}
function harness(overrides = {}, decodeOverride) {
  const states = [],
    sockets = [],
    tickets = []
  let revision = 1,
    draws = 0,
    clears = 0,
    disposed = 0
  const identity = { browser_session_id: "one", run_epoch: 1 }
  const client = {
    async discover() {
      return [{ identity, revision, sensitive_entry: false, sensitive_entry_pending: false }]
    },
    async pages(browser) {
      return {
        active_page_id: "p1",
        pages: [{ page_id: "p1", revision: String(browser.revision) }],
        locations: [],
      }
    },
    async viewerTicket(browser, page) {
      tickets.push({ revision: browser.revision, pageRevision: page.revision })
      return `ticket-${tickets.length}`
    },
    viewerUrl() {
      return "wss://example.test/viewer"
    },
    dispose() {
      disposed++
    },
    ...overrides,
  }
  const watch = startBrowserWatch({
    client,
    socket() {
      const sent = []
      const socket = { sent, send: (message) => sent.push(message), close() {} }
      sockets.push(socket)
      return socket
    },
    draw() {
      draws++
    },
    clear() {
      clears++
    },
    change(state) {
      states.push(state)
    },
    decode: decodeOverride ?? (async () => ({ width: 16, height: 16, close() {} })),
  })
  return {
    watch,
    states,
    sockets,
    tickets,
    get draws() {
      return draws
    },
    get clears() {
      return clears
    },
    get disposed() {
      return disposed
    },
    revise() {
      revision++
    },
  }
}

test("navigation purge settles and reconnects using freshly observed browser and page revisions", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  const h = harness()
  await flush()
  const first = h.sockets[0]
  first.onopen()
  first.onmessage({ data: "ready" })
  first.onmessage({ data: frame() })
  await flush()
  assert.equal(h.draws, 1)
  h.revise()
  first.onmessage({ data: `purge:${"a".repeat(32)}` })
  await flush()
  assert.equal(first.sent.at(-1), `purged:${"a".repeat(32)}`)
  assert.equal(h.sockets.length, 1)
  first.onmessage({ data: "retired" })
  assert.equal(h.states.at(-1).phase, "reconnecting")
  assert.equal(h.states.at(-1).reason, "state_changed")
  t.mock.timers.tick(750)
  await flush()
  assert.deepEqual(h.tickets, [
    { revision: 1, pageRevision: "1" },
    { revision: 2, pageRevision: "2" },
  ])
  const second = h.sockets[1]
  second.onopen()
  second.onmessage({ data: "ready" })
  second.onmessage({ data: frame() })
  await flush()
  assert.equal(h.draws, 2)
  assert.equal(h.states.at(-1).phase, "live")
  assert.equal(h.states.at(-1).reconnects, 1)
  h.watch.stop()
})

test("ticket conflicts retry discovery, never replay the stale view intent", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  let reads = 0,
    requests = []
  const h = harness({
    async discover() {
      return [{ identity: { browser_session_id: "one" }, revision: ++reads }]
    },
    async viewerTicket(browser) {
      requests.push(browser.revision)
      if (reads === 1) throw new BrowserControlHttpError(409)
      return "fresh"
    },
  })
  await flush()
  assert.equal(h.sockets.length, 0)
  t.mock.timers.tick(750)
  await flush()
  assert.deepEqual(requests, [1, 2])
  assert.equal(h.sockets.length, 1)
  h.watch.stop()
})

test("missing browser waits automatically; authentication failure stops retries", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  let reads = 0
  const h = harness({
    async discover() {
      if (++reads === 1) return []
      throw new BrowserControlHttpError(401)
    },
  })
  await flush()
  assert.equal(h.states.at(-1).phase, "waiting")
  t.mock.timers.tick(750)
  await flush()
  assert.equal(h.states.at(-1).phase, "unavailable")
  t.mock.timers.tick(60000)
  await flush()
  assert.equal(reads, 2)
  h.watch.stop()
})

test("reconnect cannot silently switch to a replacement browser", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  let reads = 0
  const h = harness({
    async discover() {
      return [
        { identity: { browser_session_id: ++reads === 1 ? "one" : "replacement" }, revision: 1 },
      ]
    },
  })
  await flush()
  h.sockets[0].onclose()
  t.mock.timers.tick(750)
  await flush()
  assert.equal(h.tickets.length, 1)
  assert.equal(h.states.at(-1).browser, null)
  h.watch.stop()
})

test("stopping during discovery disposes the client and cannot open a late socket", async () => {
  let release
  const h = harness({
    discover() {
      return new Promise((resolve) => (release = resolve))
    },
  })
  h.watch.stop()
  release([{ identity: { browser_session_id: "one" }, revision: 1 }])
  await flush()
  assert.equal(h.disposed, 1)
  assert.equal(h.sockets.length, 0)
  assert.equal(h.states.length, 1)
})

test("stopping a live watcher cancels recovery and late frame publication", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  const h = harness()
  await flush()
  const socket = h.sockets[0]
  socket.onopen()
  socket.onmessage({ data: "ready" })
  h.watch.stop()
  socket.onmessage({ data: frame() })
  socket.onclose()
  t.mock.timers.tick(60000)
  await flush()
  assert.equal(h.draws, 0)
  assert.equal(h.sockets.length, 1)
  assert.equal(h.disposed, 1)
})

test("startup and page-discovery 403 conflicts retry fresh reads without admitting denied frames", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  let reads = 0,
    pageReads = 0
  const h = harness({
    async discover() {
      if (++reads === 1) throw new BrowserControlHttpError(403)
      return [{ identity: { browser_session_id: "one" }, revision: reads }]
    },
    async pages(browser) {
      if (++pageReads === 1) throw new BrowserControlHttpError(403)
      return {
        active_page_id: "p1",
        pages: [{ page_id: "p1", revision: String(browser.revision) }],
        locations: [],
      }
    },
  })
  await flush()
  assert.equal(h.tickets.length, 0)
  t.mock.timers.tick(750)
  await flush()
  assert.equal(h.tickets.length, 0)
  t.mock.timers.tick(1500)
  await flush()
  assert.equal(reads, 3)
  assert.equal(pageReads, 2)
  assert.deepEqual(h.tickets, [{ revision: 3, pageRevision: "3" }])
  h.watch.stop()
})

test("an old purge finishing after timeout cannot clear its replacement viewer", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] })
  let release,
    decodes = 0
  const h = harness({}, () =>
    ++decodes === 1
      ? new Promise((resolve) => (release = resolve))
      : Promise.resolve({ width: 16, height: 16, close() {} }),
  )
  await flush()
  const first = h.sockets[0]
  first.onopen()
  first.onmessage({ data: "ready" })
  first.onmessage({ data: frame() })
  await flush()
  first.onmessage({ data: `purge:${"a".repeat(32)}` })
  t.mock.timers.tick(5000)
  t.mock.timers.tick(750)
  await flush()
  const next = h.sockets[1]
  next.onopen()
  next.onmessage({ data: "ready" })
  next.onmessage({ data: frame() })
  await flush()
  assert.equal(h.draws, 1)
  const clears = h.clears
  release({ width: 16, height: 16, close() {} })
  await flush()
  assert.equal(h.clears, clears)
  assert.equal(h.draws, 1)
  assert.equal(h.states.at(-1).phase, "live")
  h.watch.stop()
})
