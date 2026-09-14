import { Maximize2, Minimize2, Monitor, RefreshCw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { createBrowserControlClient } from "../../lib/browser-control-client"
import { type BrowserWatchState, startBrowserWatch } from "../../lib/browser-watch"
import { apiUrl } from "../../lib/config"
import { Button } from "../ui/button"
import { BrowserRecordings } from "./browser-recordings"

const phaseLabel = {
  waiting: "Starting browser",
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  unavailable: "View unavailable",
  stopped: "View closed",
}
const reasonLabel: Record<string, string> = {
  browser_starting: "The preview opens automatically when the agent starts browsing.",
  multiple_browsers:
    "More than one browser is available. A single browser is required for this demo preview.",
  capture_restricted: "The browser has temporarily restricted capture.",
  page_unavailable: "Waiting for the selected page to become available.",
  fresh_authorization: "Loading the current browser view…",
  receiving_frames: "Watching the agent’s browser. View only.",
  state_changed: "Updating the browser preview…",
  transport: "Connection interrupted. Reconnecting automatically…",
  timeout: "Waiting for the browser to respond. Reconnecting automatically…",
  protocol: "The frame stream stopped. Reconnecting automatically…",
  connection_unavailable: "Waiting for the browser connection. Retrying automatically…",
  authorization_required: "Browser access is unavailable. Retry after access has been restored.",
}

export function BrowserOperator({
  sessionId,
  sessionStatus,
}: {
  sessionId: string
  sessionStatus: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [watch, setWatch] = useState<BrowserWatchState | null>(null)
  const [enabled, setEnabled] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const active = sessionStatus === "running"
  const paused = sessionStatus === "interrupted"
  const ended = ["completed", "failed", "cancelled"].includes(sessionStatus)

  // biome-ignore lint/correctness/useExhaustiveDependencies: attempt deliberately restarts a stopped viewer after an explicit Retry.
  useEffect(() => {
    let current = true
    const clear = () => {
      if (current && canvas.current) {
        canvas.current.width = 0
        canvas.current.height = 0
      }
    }
    clear()
    if (!active || !enabled) {
      setWatch((previous) =>
        previous ? { ...previous, phase: "stopped", browser: null, location: null } : null,
      )
      return
    }
    setWatch(null)
    const connection = startBrowserWatch({
      client: createBrowserControlClient(
        new URL(apiUrl("browser-control"), window.location.href),
        sessionId,
      ),
      socket: (url) => new WebSocket(url, "cayu.browser-view.v1"),
      draw: (bitmap) => {
        if (!current) return
        const target = canvas.current
        if (!target) return
        target.width = bitmap.width
        target.height = bitmap.height
        target.getContext("2d")?.drawImage(bitmap, 0, 0)
      },
      clear,
      change: setWatch,
    })
    return () => {
      connection.stop()
      current = false
    }
  }, [sessionId, active, enabled, attempt])

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false)
    }
    window.addEventListener("keydown", handleEscape)
    return () => window.removeEventListener("keydown", handleEscape)
  }, [])

  const label = ended
    ? "Run finished"
    : paused
      ? "Agent paused"
      : !enabled
        ? "View closed"
        : watch?.reason === "state_changed" ||
            (watch?.reason === "fresh_authorization" && (watch?.frames ?? 0) > 0)
          ? "Updating view"
          : phaseLabel[watch?.phase ?? "waiting"]
  const live = active && enabled && watch?.phase === "live"
  const detail = ended
    ? "This run has ended. Its browser is no longer live."
    : paused
      ? "Answer the pending question or approval to continue. The preview reconnects when the agent resumes."
      : !enabled
        ? "Open the preview to watch this run."
        : (reasonLabel[watch?.reason ?? "browser_starting"] ?? "Reconnecting to the browser…")

  return (
    <div className="h-[38rem] min-h-0 min-w-0 lg:h-full">
      <section
        aria-label="Browser preview"
        className={
          expanded
            ? "fixed inset-4 z-50 flex flex-col rounded-xl border border-border bg-background shadow-2xl"
            : "flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-background"
        }
      >
        <div className="flex items-center justify-between gap-3 border-b border-border p-4">
          <div className="flex min-w-0 items-center gap-2">
            <Monitor className="size-4 shrink-0" />
            <h2 className="font-semibold">Browser</h2>
            <span
              role="status"
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${live ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"}`}
            >
              {label}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            aria-label={expanded ? "Minimize browser" : "Expand browser"}
          >
            {expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </Button>
        </div>
        <div
          hidden={ended}
          className="truncate border-b border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground"
        >
          {active && enabled && watch?.location ? watch.location : "Agent browser"} · View only
        </div>
        <div
          className={`relative min-h-0 flex-1 items-center justify-center bg-slate-100 ${ended ? "hidden" : "flex"}`}
        >
          <canvas
            ref={canvas}
            width={0}
            height={0}
            aria-label="Live browser frame"
            className="max-h-full max-w-full object-contain"
          />
          {!live && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center">
              <Monitor className="size-8 text-slate-400" />
              <p className="font-medium text-slate-700">{label}</p>
              <p className="max-w-sm text-sm text-slate-500">{detail}</p>
            </div>
          )}
        </div>
        <div
          className={
            ended
              ? "hidden"
              : "flex items-center justify-between gap-3 border-t border-border px-4 py-3"
          }
        >
          <p className="text-xs text-muted-foreground">
            {live ? "Watching the agent browse" : label}
          </p>
          {active && (
            <div className="flex gap-2">
              {enabled && watch?.phase === "unavailable" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setAttempt((value) => value + 1)}
                >
                  <RefreshCw className="mr-1 size-3" />
                  Retry
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setEnabled(!enabled)}>
                {enabled ? "Close preview" : "Open preview"}
              </Button>
            </div>
          )}
        </div>
        <div className={ended ? "min-h-0 flex-1 overflow-y-auto overscroll-contain" : "hidden"}>
          <BrowserRecordings key={sessionId} sessionId={sessionId} visible={ended} />
        </div>
        <details className="shrink-0 border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <summary className="cursor-pointer">Advanced</summary>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 break-all">
            <dt>Frames received</dt>
            <dd>{watch?.frames ?? 0}</dd>
            <dt>Reconnections</dt>
            <dd>{watch?.reconnects ?? 0}</dd>
            <dt>Connection</dt>
            <dd>{active ? (watch?.reason ?? "browser_starting") : sessionStatus}</dd>
            {active && watch?.browser && (
              <>
                <dt>Browser session</dt>
                <dd>{watch.browser.identity.browser_session_id}</dd>
                <dt>Environment</dt>
                <dd>{watch.browser.identity.environment_name}</dd>
              </>
            )}
          </dl>
          <p className="mt-3">
            Frames are transient. A Runtime purge clears old pixels before fresh viewing
            authorization is requested.
          </p>
        </details>
      </section>
    </div>
  )
}
