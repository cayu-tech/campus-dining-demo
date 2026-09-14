import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { fetchSessionTranscript } from "../../lib/api"
import { Button } from "../ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card"

/** The visible conversation refreshes independently of the collapsed history inspector. */
export function SessionConversation({
  sessionId,
  status,
  liveText,
}: {
  sessionId: string
  status: string
  liveText: string
}) {
  const viewport = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)
  const active = status === "running"
  const conversation = useQuery({
    queryKey: ["visible-session-conversation", sessionId],
    queryFn: async ({ signal }) => {
      const probe = await fetchSessionTranscript(sessionId, { offset: 0, limit: 1 }, signal)
      if (probe.total_messages <= 1) return probe
      return fetchSessionTranscript(
        sessionId,
        { offset: Math.max(0, probe.total_messages - 40), limit: 40 },
        signal,
      )
    },
    refetchInterval: active ? 2000 : false,
    gcTime: 0,
  })
  const previousStatus = useRef(status)
  const refreshConversation = conversation.refetch
  useEffect(() => {
    if (previousStatus.current !== status) {
      previousStatus.current = status
      void refreshConversation()
    }
  }, [status, refreshConversation])
  const messages = conversation.data?.messages ?? []
  useEffect(() => {
    // Depend on the received page and streaming text, without scrolling the page.
    if (conversation.data && (liveText || messages.length) && pinned.current && viewport.current) {
      viewport.current.scrollTop = viewport.current.scrollHeight
    }
  }, [conversation.data, liveText, messages.length])

  return (
    <Card className="min-h-0 flex-1 gap-0 overflow-hidden py-0">
      <CardHeader className="border-b border-border py-4">
        <CardTitle>Conversation</CardTitle>
      </CardHeader>
      <CardContent
        ref={viewport}
        aria-label="Conversation messages"
        className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain p-4"
        onScroll={(event) => {
          const target = event.currentTarget
          pinned.current = target.scrollHeight - target.scrollTop - target.clientHeight < 48
        }}
      >
        {conversation.isLoading && (
          <p className="text-sm text-muted-foreground">Loading conversation…</p>
        )}
        {messages
          .filter((message) => message.role === "user" || message.role === "assistant")
          .map((message) => {
            const text = message.content
              .filter((part) => part.type === "text" && typeof part.text === "string")
              .map((part) => part.text)
              .join("\n\n")
            if (!text) return null
            return (
              <div
                key={`${message.index}:${message.role}`}
                className={
                  message.role === "user"
                    ? "rounded-lg bg-muted/40 p-3"
                    : "rounded-lg border border-border p-3"
                }
              >
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {message.role === "user" ? "You" : "Agent"}
                </p>
                <p className="whitespace-pre-wrap break-words text-sm">{text}</p>
              </div>
            )
          })}
        {active && (
          <p role="status" className="whitespace-pre-wrap text-sm text-muted-foreground">
            {liveText || "The agent is working. Follow its browser alongside this conversation."}
          </p>
        )}
        {conversation.isError && (
          <div className="text-sm text-destructive">
            Conversation could not be refreshed.{" "}
            <Button variant="link" onClick={() => void conversation.refetch()}>
              Retry
            </Button>
          </div>
        )}
        {(conversation.data?.offset ?? 0) > 0 && (
          <p className="text-xs text-muted-foreground">
            Recent conversation shown. Earlier messages are available under Advanced.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
