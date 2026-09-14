import type { BrowserDescriptor, BrowserPage } from "./browser-control-client.ts"

/** Resolve the same selected browser/page from fresh, read-only observations. */
export async function freshBrowserViewSelection(
  owner: {
    discover(): Promise<BrowserDescriptor[]>
    pages(browser: BrowserDescriptor): Promise<{ pages: BrowserPage[] }>
  },
  selected: BrowserDescriptor,
  pageId: string,
) {
  const browsers = await owner.discover()
  const browser = browsers.find(
    (candidate) => JSON.stringify(candidate.identity) === JSON.stringify(selected.identity),
  )
  if (!browser) throw new Error("The selected browser is no longer available.")
  const result = await owner.pages(browser)
  const page = result.pages.find((candidate) => candidate.page_id === pageId)
  if (!page) throw new Error("The selected page is no longer available.")
  return { browser, page }
}
