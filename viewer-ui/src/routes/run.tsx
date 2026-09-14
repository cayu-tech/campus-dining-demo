import { useQuery } from "@tanstack/react-query"
import { Link, useNavigate } from "@tanstack/react-router"
import {
  AlertCircle,
  Bot,
  Check,
  CheckCircle,
  Copy,
  Play,
  ShieldCheck,
  UserRound,
  Wrench,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { DataCard, Page, PageHeader, StateMessage } from "../components/dashboard/layout"
import { MutationTransportStatus } from "../components/dashboard/mutation-transport-status"
import { Button } from "../components/ui/button"
import { Textarea } from "../components/ui/textarea"
import { fetchAgents, fetchSessionState, type SSEEvent } from "../lib/api"
import { formatCount, modelUsagePayload, numericValue } from "../lib/format"
import type { MutationTransportSnapshot } from "../lib/mutation-transport.ts"
import { prepareRecordingSession } from "../lib/recording-session"
import { reconcileRunAgentSelection } from "../lib/run-agent-selection.ts"

const selectClassName =
  "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"

function LiveEvent({ event }: { event: SSEEvent }) {
  const icons: Record<string, React.ReactNode> = {
    "tool.call.started": <Wrench className="h-3.5 w-3.5 text-primary" />,
    "tool.call.completed": <CheckCircle className="h-3.5 w-3.5 text-chart-2" />,
    "tool.call.failed": <AlertCircle className="h-3.5 w-3.5 text-destructive" />,
    "tool.call.approval_requested": <ShieldCheck className="h-3.5 w-3.5 text-chart-1" />,
    "session.awaiting_user_input": <UserRound className="h-3.5 w-3.5 text-chart-3" />,
    "model.started": <Bot className="h-3.5 w-3.5 text-chart-1" />,
    "model.completed": <Bot className="h-3.5 w-3.5 text-chart-1" />,
  }

  let text = event.type
  if (event.tool_name) text += ` — ${event.tool_name}`
  if (event.type === "model.completed") {
    const usage = modelUsagePayload(event.payload)
    const inputTokens = numericValue(usage.input_tokens)
    const outputTokens = numericValue(usage.output_tokens)
    if (inputTokens > 0 || outputTokens > 0) {
      text = `model.completed (${formatCount(inputTokens)} in / ${formatCount(outputTokens)} out)`
    }
  }
  if (event.type === "session.completed") text = "Session completed"
  if (event.type === "session.failed") text = `Session failed: ${event.payload.error || "unknown"}`
  if (event.type === "tool.call.approval_requested") {
    const approval = event.payload.approval
    const payloadToolName =
      approval && typeof approval === "object" && "tool_name" in approval
        ? String((approval as { tool_name?: unknown }).tool_name || "")
        : ""
    const toolName = payloadToolName || event.tool_name || "tool"
    text = `Approval requested: ${toolName}`
  }
  if (event.type === "session.awaiting_user_input") {
    const question =
      typeof event.payload.question === "string" ? event.payload.question : "Input required"
    text = `Awaiting user input: ${question}`
  }
  if (event.type === "session.interrupted") {
    const interruptionType =
      typeof event.payload.interruption_type === "string" ? event.payload.interruption_type : null
    if (interruptionType === "tool_approval_required") text = "Session paused for approval"
    else if (interruptionType === "user_input_required") text = "Session paused for user input"
    else text = "Session interrupted"
  }
  if (event.type === "task.started") text = "Task started"
  if (event.type === "task.completed") text = "Task completed"

  return (
    <div className="flex items-center gap-2 py-1.5">
      {icons[event.type] || <span className="w-3.5" />}
      <span className="text-sm text-muted-foreground">{text}</span>
    </div>
  )
}

function runAttention(events: SSEEvent[]) {
  for (const event of [...events].reverse()) {
    if (
      event.type === "session.resumed" ||
      event.type === "session.completed" ||
      event.type === "session.failed"
    ) {
      return null
    }
    if (event.type === "session.interrupted") {
      if (event.payload.interruption_type === "tool_approval_required") {
        return "This run is paused for tool approval. Open the session to approve or deny it."
      }
      if (event.payload.interruption_type === "user_input_required") {
        return "This run is paused for user input. Open the session to answer the question."
      }
    }
  }
  return null
}

export function RunPage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState("We are serving dinner to 400 students tomorrow. Our usual potatoes are unavailable. Find a workable replacement within our remaining budget. We are short-staffed, so avoid extra preparation. Prepare a draft; do not order yet.")
  const [demoSession, setDemoSession] = useState("dinner")
  const [selectedAgentName, setSelectedAgentName] = useState("")
  const [running, setRunning] = useState(false)
  const [transport, setTransport] = useState<MutationTransportSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copiedSessionReference, setCopiedSessionReference] = useState<string | null>(null)
  const [sessionReferenceError, setSessionReferenceError] = useState<string | null>(null)
  const runAbortRef = useRef<AbortController | null>(null)
  const eventsEndRef = useRef<HTMLDivElement>(null)
  const outputEndRef = useRef<HTMLDivElement>(null)
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: ({ signal }) => fetchAgents(signal),
    staleTime: 15_000,
  })
  const registeredAgents = agents.data?.agents ?? []
  const resolvedAgentName = reconcileRunAgentSelection(selectedAgentName, registeredAgents)
  const selectedAgent = registeredAgents.find((agent) => agent.name === resolvedAgentName) ?? null
  const agentInventoryError = agents.error instanceof Error ? agents.error.message : null
  const events = transport?.events ?? []
  const textOutput = transport?.liveText ?? ""
  const activeSessionId =
    transport?.sessionId ?? events.find((event) => event.session_id)?.session_id ?? null
  const liveState = useQuery({
    queryKey: ["run-state", activeSessionId],
    queryFn: ({ signal }) => fetchSessionState(activeSessionId!, signal),
    enabled: activeSessionId !== null,
    refetchInterval: (query) =>
      ["completed", "failed", "interrupted"].includes(query.state.data?.status ?? "")
        ? false
        : 2000,
  })
  const lifecycleEvent = [...events]
    .reverse()
    .find((event) =>
      [
        "session.completed",
        "session.failed",
        "session.interrupted",
        "session.started",
        "session.resumed",
      ].includes(event.type),
    )
  const eventStatus = lifecycleEvent?.type.replace("session.", "")
  const runStatus = ["completed", "failed", "interrupted"].includes(eventStatus ?? "")
    ? eventStatus!
    : (liveState.data?.status ?? (running ? "running" : "unknown"))
  const activity = [...events]
    .reverse()
    .find((event) =>
      ["tool.call.started", "tool.call.completed", "model.started"].includes(event.type),
    )
  const activityText =
    activity?.tool_name === "browser_session"
      ? "Browsing the supplier catalog…"
      : activity?.type === "model.started"
        ? "Considering the next step…"
        : activity?.tool_name === "read_knowledge" || activity?.tool_name === "search_knowledge"
          ? "Checking product and substitution guidance…"
          : "Working on your request…"

  useEffect(
    () => () => {
      runAbortRef.current?.abort()
      runAbortRef.current = null
    },
    [],
  )

  const handleRun = async () => {
    if (!prompt.trim() || selectedAgent === null) return
    runAbortRef.current?.abort()
    const controller = new AbortController()
    runAbortRef.current = controller
    setRunning(true)
    setTransport(null)
    setError(null)
    setCopiedSessionReference(null)
    setSessionReferenceError(null)

    try {
      await prepareRecordingSession(demoSession, controller.signal)
      const { executeRunMutation } = await import("../lib/mutation-browser")
      if (controller.signal.aborted || runAbortRef.current !== controller) return
      const snapshot = await executeRunMutation(
        { agent: selectedAgent.name, prompt: prompt.trim(), session_id: demoSession },
        {
          signal: controller.signal,
          onChange: (next) => {
            if (!controller.signal.aborted && runAbortRef.current === controller) {
              setTransport(next)
            }
          },
        },
      )
      if (!controller.signal.aborted && runAbortRef.current === controller) {
        setTransport(snapshot)
      }
    } catch (runError) {
      if (!controller.signal.aborted && runAbortRef.current === controller) {
        setError(runError instanceof Error ? runError.message : "Failed to start the run.")
      }
    } finally {
      if (runAbortRef.current === controller) {
        runAbortRef.current = null
        if (!controller.signal.aborted) setRunning(false)
      }
    }
  }

  const lastSessionId =
    !running && transport?.phase !== "request_failed"
      ? (transport?.sessionId ?? events.at(-1)?.session_id ?? null)
      : null
  const attentionMessage = runAttention(events)
  const sessionReferenceCopied = lastSessionId !== null && copiedSessionReference === lastSessionId

  const handleCopySessionReference = async () => {
    if (lastSessionId === null) return
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard access is unavailable in this browser context.")
      }
      await navigator.clipboard.writeText(lastSessionId)
      setCopiedSessionReference(lastSessionId)
      setSessionReferenceError(null)
    } catch (copyError) {
      setCopiedSessionReference(null)
      setSessionReferenceError(
        copyError instanceof Error ? copyError.message : "Failed to copy the session reference.",
      )
    }
  }

  return (
    <Page>
      <PageHeader
        title="New Run"
        description="Start a request here. Open its session to follow the conversation and browser."
      />

      <details open={!activeSessionId} className="rounded-xl border border-border p-4">
        <summary className="cursor-pointer text-sm font-medium">
          {activeSessionId ? "Run settings" : "Set up your run"}
        </summary>
        <DataCard title="Run configuration" headerClassName="pb-3" contentClassName="space-y-4 p-4">
          <div className="space-y-1.5">
            <label htmlFor="run-agent" className="text-sm font-medium">
              Agent
            </label>
            <select
              id="run-agent"
              className={selectClassName}
              value={resolvedAgentName}
              onChange={(event) => {
                setSelectedAgentName(event.target.value)
                setError(null)
              }}
              disabled={running || (agents.isLoading && agents.data === undefined)}
              aria-describedby="run-agent-help"
            >
              <option value="">
                {agents.isLoading && agents.data === undefined
                  ? "Loading registered agents..."
                  : "Select an agent"}
              </option>
              {registeredAgents.map((agent) => (
                <option key={agent.name} value={agent.name}>
                  {agent.name}
                </option>
              ))}
            </select>
            <p id="run-agent-help" className="text-xs text-muted-foreground">
              {selectedAgent
                ? `${selectedAgent.provider_name ?? "default provider"} · ${selectedAgent.model} · ${formatCount(selectedAgent.tool_count)} ${selectedAgent.tool_count === 1 ? "tool" : "tools"}`
                : registeredAgents.length > 1
                  ? "Choose which registered agent receives this prompt."
                  : "The selected agent identity is sent explicitly with the run request."}
            </p>
          </div>

          {agents.isError && agents.data === undefined && (
            <StateMessage tone="danger" className="rounded-md border border-destructive/30 py-4">
              <div role="alert">Registered agents could not be loaded: {agentInventoryError}</div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                disabled={agents.isFetching}
                onClick={() => void agents.refetch()}
              >
                {agents.isFetching ? "Retrying..." : "Retry"}
              </Button>
            </StateMessage>
          )}
          {!agents.isLoading && !agents.isError && registeredAgents.length === 0 && (
            <StateMessage className="rounded-md border border-border py-4">
              No agents are registered. Register an agent in the Cayu application before starting a
              control-plane run.
            </StateMessage>
          )}
          {agents.isError && agents.data !== undefined && (
            <p className="text-sm text-destructive" role="alert">
              The agent inventory could not be refreshed. The last confirmed selection remains
              available.
            </p>
          )}

          <div className="space-y-1.5">
            <label htmlFor="demo-session" className="text-sm font-medium">
              Demo session
            </label>
            <select
              id="demo-session"
              value={demoSession}
              onChange={(event) => setDemoSession(event.target.value)}
              disabled={running}
              className="block rounded-md border p-2"
            >
              <option value="dinner">Dinner shortage</option>
              <option value="comparison">Another comparison</option>
              <option value="rice-lunch">Rice lunch</option>
              <option value="vegetable-side">Vegetable side</option>
            </select>
            <p className="text-sm text-muted-foreground">
              Use an unused session here. To continue an existing session, open it from Sessions.
            </p>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="run-prompt" className="text-sm font-medium">
              Prompt
            </label>
            <Textarea
              id="run-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Review alternatives for the missing crushed tomatoes. I prefer smaller packs. Show me your recommendation before placing an order."
              disabled={running}
              rows={4}
              className="resize-none"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <MutationTransportStatus snapshot={transport} />
          {lastSessionId && (
            <div className="flex flex-col gap-3 rounded-md border border-border bg-muted/20 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Session reference
                </div>
                <code
                  className="block truncate text-sm"
                  data-testid="run-session-reference"
                  title={lastSessionId}
                >
                  {lastSessionId}
                </code>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCopySessionReference}>
                  {sessionReferenceCopied ? (
                    <Check className="mr-1.5 h-3.5 w-3.5" />
                  ) : (
                    <Copy className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  {sessionReferenceCopied ? "Copied" : "Copy"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    navigate({ to: "/sessions/$sessionId", params: { sessionId: lastSessionId } })
                  }
                >
                  View Session →
                </Button>
              </div>
            </div>
          )}
          {sessionReferenceError && (
            <p className="text-sm text-destructive" role="alert">
              {sessionReferenceError}
            </p>
          )}
          <div className="flex items-center justify-end">
            <Button
              onClick={handleRun}
              disabled={running || !prompt.trim() || selectedAgent === null}
            >
              <Play className="h-4 w-4 mr-2" />
              {running ? "Running..." : "Run"}
            </Button>
          </div>
        </DataCard>
      </details>
      {activeSessionId && (
        <div className="space-y-4">
          <DataCard title="Conversation" contentClassName="space-y-4 p-4">
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="mb-1 text-xs font-medium text-muted-foreground">You</p>
              <p className="whitespace-pre-wrap text-sm">{prompt}</p>
            </div>
            <div className="min-h-28 rounded-lg border border-border p-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">Agent</p>
              <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words font-sans text-sm">
                {textOutput ||
                  (runStatus === "running"
                    ? activityText
                    : attentionMessage ||
                      "The run has ended. Open the session for its saved conversation.")}
              </pre>
              {textOutput && runStatus === "running" && (
                <p className="mt-3 text-xs text-muted-foreground">{activityText}</p>
              )}
              <div ref={outputEndRef} />
            </div>
            {attentionMessage && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <p>{attentionMessage}</p>
                {lastSessionId && (
                  <Button
                    variant="link"
                    className="mt-2 h-auto p-0"
                    onClick={() =>
                      navigate({ to: "/sessions/$sessionId", params: { sessionId: lastSessionId } })
                    }
                  >
                    Answer or review →
                  </Button>
                )}
              </div>
            )}
            <MutationTransportStatus snapshot={transport} />
            <Link
              to="/sessions/$sessionId"
              params={{ sessionId: activeSessionId }}
              target={running ? "_blank" : undefined}
              rel={running ? "noopener noreferrer" : undefined}
              className="inline-flex items-center rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-accent"
            >
              Open session and browser{running ? " in a new tab" : ""} →
            </Link>
            <details className="border-t border-border pt-3">
              <summary className="cursor-pointer text-xs text-muted-foreground">
                Advanced · Run events
              </summary>
              <div className="mt-2 max-h-64 overflow-auto">
                {events
                  .filter((event) => event.type !== "model.text.delta")
                  .map((event) => (
                    <LiveEvent key={event.id} event={event} />
                  ))}
                <div ref={eventsEndRef} />
              </div>
            </details>
          </DataCard>
        </div>
      )}
    </Page>
  )
}
