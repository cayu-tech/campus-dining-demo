import {
  BrowserControlHttpError,
  type BrowserDescriptor,
  type BrowserPageLocation,
  type createBrowserControlClient,
} from "./browser-control-client.ts"
import { startPrivateBrowserViewer, type ViewerEndReason } from "./browser-private-viewer.ts"

export type BrowserWatchState = {
  phase: "waiting" | "connecting" | "live" | "reconnecting" | "unavailable" | "stopped"
  frames: number
  reconnects: number
  reason: string
  browser: BrowserDescriptor | null
  location: string | null
}

type Client = ReturnType<typeof createBrowserControlClient>

/** Read-only viewing. Every reconnect rediscovers authority and uses a new ticket.
 * No tool execution, takeover, input, or replay of session mutations belongs here.
 */
export function startBrowserWatch(options: {
  client: Client
  socket: (url: string) => WebSocket
  draw: (bitmap: ImageBitmap) => void
  clear: () => void
  change: (state: BrowserWatchState) => void
  decode?: (blob: Blob) => Promise<ImageBitmap>
}) {
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let viewer: ReturnType<typeof startPrivateBrowserViewer> | null = null
  let viewerGeneration = 0
  let pinnedIdentity: string | null = null
  let pinnedPage: string | null = null
  let failures = 0
  let state: BrowserWatchState = {
    phase: "waiting",
    frames: 0,
    reconnects: 0,
    reason: "browser_starting",
    browser: null,
    location: null,
  }

  function update(change: Partial<BrowserWatchState>) {
    if (stopped) return
    state = { ...state, ...change }
    options.change(state)
  }

  function schedule(reason: string) {
    if (stopped) return
    clearTimeout(timer)
    update({ phase: state.frames ? "reconnecting" : "waiting", reason })
    timer = setTimeout(() => void connect(), Math.min(750 * 2 ** Math.min(failures++, 3), 6000))
  }

  async function connect() {
    if (stopped) return
    try {
      const browsers = await options.client.discover()
      if (stopped) return
      const browser = pinnedIdentity
        ? browsers.find((candidate) => JSON.stringify(candidate.identity) === pinnedIdentity)
        : browsers.length === 1
          ? browsers[0]
          : undefined
      if (!browser) {
        options.clear()
        update({ browser: null, location: null })
        schedule(browsers.length > 1 && !pinnedIdentity ? "multiple_browsers" : "browser_starting")
        return
      }
      if (browser.sensitive_entry || browser.sensitive_entry_pending) {
        options.clear()
        update({ browser, location: null })
        schedule("capture_restricted")
        return
      }
      const observed = await options.client.pages(browser)
      if (stopped) return
      const pageId = pinnedPage ?? observed.active_page_id ?? observed.pages[0]?.page_id
      const page = observed.pages.find((candidate) => candidate.page_id === pageId)
      if (!page) {
        options.clear()
        schedule("page_unavailable")
        return
      }
      // Never silently switch to a replacement browser or a different page.
      pinnedIdentity = JSON.stringify(browser.identity)
      pinnedPage = page.page_id
      const location =
        observed.locations.find((item: BrowserPageLocation) => item.page.page_id === page.page_id)
          ?.origin ?? null
      update({
        browser,
        location,
        phase: state.frames ? "reconnecting" : "connecting",
        reason: "fresh_authorization",
      })
      let ticket = await options.client.viewerTicket(browser, page)
      if (stopped) {
        ticket = ""
        return
      }
      const socket = options.socket(options.client.viewerUrl())
      const epoch = ++viewerGeneration
      const current = () => !stopped && epoch === viewerGeneration
      viewer = startPrivateBrowserViewer(
        socket,
        ticket,
        (bitmap) => {
          if (current()) options.draw(bitmap)
        },
        () => {
          if (current()) options.clear()
        },
        options.decode ?? createImageBitmap,
        (phase, reason?: ViewerEndReason) => {
          if (!current()) return
          if (phase === "live") {
            failures = 0
            update({ phase: "live", frames: state.frames + 1, reason: "receiving_frames" })
          } else {
            viewer = null
            update({ reconnects: state.reconnects + 1 })
            // This callback follows disposal/purge acknowledgement. An old
            // socket or decoding bitmap can never publish into its successor.
            schedule(reason ?? "transport")
          }
        },
      )
      ticket = ""
    } catch (error) {
      if (stopped) return
      options.clear()
      if (error instanceof BrowserControlHttpError && error.status === 401) {
        update({
          phase: "unavailable",
          reason: "authorization_required",
          browser: null,
          location: null,
        })
        return
      }
      // Runtime deliberately uses 403 for both denied access and transient
      // discovery/revision conflicts. Retry fresh *read-only* discovery while
      // running; no pixels or authority survive the failed request.
      schedule(
        error instanceof BrowserControlHttpError && [403, 409].includes(error.status)
          ? "state_changed"
          : "connection_unavailable",
      )
    }
  }

  options.change(state)
  void connect()
  return {
    stop() {
      if (stopped) return
      stopped = true
      viewerGeneration++
      clearTimeout(timer)
      viewer?.stop()
      viewer = null
      options.client.dispose()
      options.clear()
    },
  }
}
