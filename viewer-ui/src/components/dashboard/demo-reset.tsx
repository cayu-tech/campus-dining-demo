import { useState } from "react"
import { RotateCcw } from "lucide-react"
import { Button } from "../ui/button"

export function DemoResetButton({ collapsed = false }: { collapsed?: boolean }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")

  async function reset() {
    if (
      busy ||
      !window.confirm(
        "Reset demo? This clears sessions, draft orders, submitted demo orders, and saved preferences, and restores the sample catalog. Your login stays the same.",
      )
    )
      return
    setBusy(true)
    setMessage("Resetting demo…")
    const requestId = crypto.randomUUID()
    try {
      let accepted = false
      try {
        const response = await fetch("/demo/reset", {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: requestId, confirm: true }),
          signal: AbortSignal.timeout(15000),
        })
        if (!response.ok) {
          const body = await response.json()
          setMessage(body.detail ?? "Reset was not accepted.")
          return
        }
        accepted = true
      } catch {
        // Check the original request's durable status; never repeat the reset POST.
      }
      const until = Date.now() + 75000
      while (Date.now() < until) {
        await new Promise((resolve) => setTimeout(resolve, 1000))
        let job: { request_id?: string; status?: string; message?: string }
        try {
          const response = await fetch("/demo/reset", {
            credentials: "same-origin",
            cache: "no-store",
            signal: AbortSignal.timeout(3000),
          })
          if (!response.ok) continue
          job = await response.json()
        } catch {
          continue
        }
        if (job.request_id !== requestId) {
          if (!accepted)
            throw new Error(
              "Reset was not confirmed. Reload and check the demo before trying again.",
            )
          continue
        }
        if (job.status === "failed") throw new Error(job.message ?? "Reset failed.")
        if (job.status === "complete") {
          window.location.assign("/operator/run")
          return
        }
      }
      throw new Error(
        "Reset is taking longer than expected. Reload to check its outcome before trying again.",
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Reset could not be confirmed.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 space-y-2">
      <Button
        variant="outline"
        className="w-full justify-start"
        aria-label={busy ? "Resetting demo" : "Reset demo"}
        title={collapsed ? "Reset demo" : undefined}
        disabled={busy}
        onClick={() => void reset()}
      >
        <RotateCcw size={16} className={collapsed ? "shrink-0" : "mr-2 shrink-0"} />
        <span className={collapsed ? "sr-only" : undefined}>
          {busy ? "Resetting…" : "Reset demo"}
        </span>
      </Button>
      {message && (
        <p role="status" className="text-xs text-muted-foreground">
          {message}
        </p>
      )}
    </div>
  )
}
