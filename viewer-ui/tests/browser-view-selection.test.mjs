import assert from "node:assert/strict"
import test from "node:test"
import { freshBrowserViewSelection } from "../src/lib/browser-view-selection.ts"

const old = { identity: { browser_session_id: "selected", run_epoch: 1 }, revision: 1 }

test("view selection observes fresh browser and page revisions", async () => {
  const current = { ...old, revision: 4 }
  const page = { page_id: "p1", revision: "new-navigation", control_epoch: 2 }
  const result = await freshBrowserViewSelection({
    async discover() { return [current] },
    async pages(browser) { assert.equal(browser, current); return { pages: [page] } },
  }, old, "p1")
  assert.deepEqual(result, { browser: current, page })
})

test("view selection refuses replacement browsers and missing pages", async () => {
  let reads = 0
  await assert.rejects(freshBrowserViewSelection({
    async discover() { return [{ ...old, identity: { ...old.identity, run_epoch: 2 } }] },
    async pages() { reads++; return { pages: [] } },
  }, old, "p1"), /browser is no longer available/)
  assert.equal(reads, 0)
  await assert.rejects(freshBrowserViewSelection({
    async discover() { return [old] },
    async pages() { return { pages: [{ page_id: "other" }] } },
  }, old, "p1"), /page is no longer available/)
})

test("failed observation is not automatically replayed", async () => {
  let calls = 0
  await assert.rejects(freshBrowserViewSelection({
    async discover() { calls++; throw new Error("unavailable") },
    async pages() { throw new Error("must not read") },
  }, old, "p1"), /unavailable/)
  assert.equal(calls, 1)
})
