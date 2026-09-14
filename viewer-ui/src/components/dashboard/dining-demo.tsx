import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BookOpen, CheckCircle2, FlaskConical, LoaderCircle, Play } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { apiUrl } from "@/lib/config"
import { DataCard, Page, PageHeader, StateMessage } from "./layout"

async function readDemo<T>(path: string, method = "GET"): Promise<T> {
  const response = await fetch(apiUrl(`/demo/${path}`), { method, credentials: "same-origin" })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

type DiningCase = {
  id: string
  prompt: string
  sku: string | null
  cases: number | null
  cost: number | null
  approval: boolean
}
type EvalSummary = { id: string; status: string; cases: { case_id: string; status: string }[] }
type EvalCatalog = { cases: DiningCase[]; running: boolean; latest: EvalSummary | null }
type KnowledgeLibrary = {
  entries: {
    id: string
    title: string
    text: string
    revision: number
    status: string
    source_uri: string
  }[]
  recall: string
}

const CASE_NAMES: Record<string, string> = {
  "short-staffed": "Short-staffed kitchen",
  "full-team": "Full kitchen team",
  "budget-infeasible": "No option within budget",
  "rice-lunch": "Rice lunch",
  "vegetable-side": "Carrot side dish",
  "later-receiving": "Later receiving deadline",
  "fewer-diners": "Fewer diners",
  "dietary-boundary": "Dairy-free requirement",
  "approval-gate": "Human approval before ordering",
}

export function DiningEvalsPage() {
  const client = useQueryClient()
  const catalog = useQuery({
    queryKey: ["dining-evals"],
    queryFn: () => readDemo<EvalCatalog>("evals"),
    refetchInterval: 3000,
  })
  const run = useMutation({
    mutationFn: () => readDemo<EvalSummary>("evals/run", "POST"),
    onSettled: () => client.invalidateQueries({ queryKey: ["dining-evals"] }),
  })
  const busy = run.isPending || catalog.data?.running
  const latest = catalog.data?.latest
  const passed = latest?.cases.filter((item) => item.status === "passed").length ?? 0
  return (
    <Page>
      <PageHeader
        title="Dining agent evaluations"
        description="Nine purchasing scenarios check the agent’s tools, business rules, and approval boundary."
        actions={
          <Button disabled={busy || !catalog.data} onClick={() => run.mutate()}>
            {busy ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" />
            ) : (
              <Play className="mr-2 size-4" />
            )}
            {busy ? "Running evaluations…" : "Run all 9 checks"}
          </Button>
        }
      />
      <DataCard>
        <div className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-3">
            <FlaskConical className="size-6 text-primary" />
            <div>
              <h2 className="font-semibold">Dining purchasing acceptance suite</h2>
              <p className="text-sm text-muted-foreground">
                Scripted provider · isolated meal records · no orders placed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline">
              {latest ? `${passed} / ${latest.cases.length} passed` : "Ready to run"}
            </Badge>
            {latest && (
              <a
                className="text-sm font-medium text-primary underline"
                href={apiUrl("/demo/evals/report")}
                target="_blank"
                rel="noreferrer"
              >
                Open full report
              </a>
            )}
          </div>
        </div>
        <p className="border-t px-5 py-3 text-sm text-muted-foreground">
          These checks execute real application tools with predetermined model calls. They verify
          purchasing outcomes, not live-model understanding. The live-model suite is available from
          the command line.
        </p>
      </DataCard>
      {(catalog.error || run.error) && (
        <StateMessage>{(catalog.error ?? run.error)?.message}</StateMessage>
      )}
      {catalog.isPending && <StateMessage>Loading dining scenarios…</StateMessage>}
      <div className="grid gap-4 lg:grid-cols-2">
        {catalog.data?.cases.map((item) => {
          const status = latest?.cases.find((result) => result.case_id === item.id)?.status
          return (
            <DataCard key={item.id}>
              <div className="space-y-3 p-5">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold">{CASE_NAMES[item.id] ?? item.id}</h2>
                  <Badge variant={status === "passed" ? "secondary" : "outline"}>
                    {status === "passed" && <CheckCircle2 className="mr-1 size-3" />}
                    {busy ? "Running" : (status ?? "Not run")}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{item.prompt}</p>
                <div className="rounded-md bg-muted/50 p-3 text-sm">
                  <span className="font-medium">Expected outcome: </span>
                  {item.sku
                    ? `${item.cases} cases of ${item.sku}, $${((item.cost ?? 0) / 100).toFixed(2)}${item.approval ? "; pause for human approval" : "; draft only"}.`
                    : "No proposal or order when the requirements cannot be met."}
                </div>
              </div>
            </DataCard>
          )
        })}
      </div>
    </Page>
  )
}

export function DiningKnowledge() {
  const library = useQuery({
    queryKey: ["dining-knowledge"],
    queryFn: () => readDemo<KnowledgeLibrary>("knowledge"),
  })
  return (
    <section className="space-y-4">
      <PageHeader
        title="Dining knowledge"
        description="Published purchasing guidance available to the agent during a run."
      />
      {library.isPending && <StateMessage>Loading purchasing knowledge…</StateMessage>}
      {library.error && <StateMessage>{library.error.message}</StateMessage>}
      {library.data?.entries.length === 0 && (
        <StateMessage>No published purchasing policy was found.</StateMessage>
      )}
      {library.data?.entries.map((entry) => (
        <DataCard key={entry.id}>
          <div className="space-y-4 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 font-semibold">
                <BookOpen className="size-5 text-primary" />
                {entry.title}
              </h2>
              <div className="flex gap-2">
                <Badge>{entry.status}</Badge>
                <Badge variant="outline">Revision {entry.revision}</Badge>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">{library.data?.recall}</p>
            <PolicyText text={entry.text} />
            <p className="break-all text-xs text-muted-foreground">Source: {entry.source_uri}</p>
          </div>
        </DataCard>
      ))}
    </section>
  )
}

function PolicyText({ text }: { text: string }) {
  let content: unknown
  try {
    content = JSON.parse(text)
  } catch {
    return <p className="whitespace-pre-wrap text-sm">{text}</p>
  }
  if (!content || typeof content !== "object" || Array.isArray(content))
    return <p className="whitespace-pre-wrap text-sm">{text}</p>
  return (
    <dl className="divide-y rounded-md border px-4">
      {Object.entries(content).map(([key, value]) => (
        <div className="space-y-1 py-3" key={key}>
          <dt className="text-sm font-medium capitalize">{key.replaceAll("_", " ")}</dt>
          <dd className="whitespace-pre-wrap text-sm text-muted-foreground">
            {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
          </dd>
        </div>
      ))}
    </dl>
  )
}
