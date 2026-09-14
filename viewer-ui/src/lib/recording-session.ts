/** Prepare capture and wait for the prior request to drain; never retry model work. */
export async function prepareRecordingSession(sessionId: string, signal?: AbortSignal) {
  const read = async () => {
    const response = await fetch("/demo/recording-session", {
      credentials: "same-origin",
      cache: "no-store",
      signal,
    })
    if (!response.ok) throw new Error("Could not inspect the recording session.")
    return response.json() as Promise<{
      enabled: boolean
      ready: boolean
      session_id: string | null
      status?: "idle" | "resetting" | "complete" | "failed"
      transition_timeout_seconds?: number
    }>
  }
  const failed = () =>
    new Error("Recording setup failed. Inspect the presenter logs before starting a run.")
  const current = await read()
  if (current.status === "failed") throw failed()
  if (!current.enabled || (current.ready && current.session_id === sessionId)) return
  if (current.session_id !== sessionId) {
    const response = await fetch("/demo/recording-session", {
      method: "POST",
      credentials: "same-origin",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, request_id: crypto.randomUUID() }),
    })
    if (!response.ok) {
      throw new Error("Finish the current run before switching recording sessions, then try again.")
    }
  }
  const seconds = current.transition_timeout_seconds ?? 180
  const deadline = Date.now() + Math.max(1, Math.min(seconds, 180)) * 1000
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError")
    let status: Awaited<ReturnType<typeof read>> | undefined
    try {
      status = await read()
    } catch (error) {
      if (signal?.aborted) throw error
      // The application worker is being replaced; no run has been submitted.
    }
    if (status?.status === "failed") throw failed()
    if (status?.ready && status.session_id === sessionId) return
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(
    "The previous turn or recording setup is still finishing. Refresh before starting a run.",
  )
}
