# Coding-agent instructions

## This demo

A fictional campus dining purchasing agent; see README.md for the scenario.

- Business records and exact arithmetic live in `domain/`; tools in `tools/dining.py`
  call them with the customer from configuration, never from model arguments.
- `submit_proposal` pauses for approval (`tools/registration.py`,
  `policies/tools.py`). `policies/human_review.py` decides what a reviewer sees;
  bump its `version` when that changes.
- Keep module-level code declarative (literal data and `ToolSpec(...)`):
  `cayu check` refuses imports it can't prove side-effect free.
- Run `python demo.py setup` once, then the proof commands below. The nine
  purchasing evals are `python -m evals.run`.

The registered agent identity is `cayu-campus-dining-demo`.

Edit the existing agent, test, and eval to implement the user's first requested
job. Do not retain the starter and add a second agent. Tools are registered in
`agents/registration.py`; change their policies deliberately. Do not create echo,
pass-through, or placeholder tools.

## When the user asks for...

Users describe product behavior, not Cayu concepts. Before building one of these
yourself, use the Cayu feature that already does it:

| The user asks for | Use | Read |
| --- | --- | --- |
| A chat, follow-up questions, "remember what I said" | Keep `outcome.session_id`, then `run_to_completion(app, ResumeRequest(session_id=..., messages=[...]))`. A new `RunRequest` always starts an empty conversation. | `cayu guide references#sessions` |
| Approval before the agent acts, "let me confirm first" | A tool generated with `cayu generate tool NAME --agent cayu-campus-dining-demo --effect external`. Listed external tools pause for approval under `policies/tools.py`; resolve pauses on the control plane's Pending page. Do not build a separate approve button or approval table. | `cayu guide durable-operations` |
| The agent asking the user a question mid-task | The `ask_user` tool, a durable user-input pause | `cayu guide references#approvals` |
| Structured data back (JSON, fields, a list) | `RunRequest(structured_output=StructuredOutputSpec(...))`, then `outcome.structured_output.output`. Do not parse JSON out of `final_text`. | `cayu guide structured-output` |
| A new capability: call an API, read data, compute | A typed tool with a declared `ToolEffect` | `cayu guide references#domain-tool` |
| A web UI that shows progress or live results | `mount_cayu(...)` and `connect()` from the served `client.js`. Do not poll on a fixed timer. | `cayu guide app-ui` |
| Work that runs in the background or later | `TaskStore`, dispatcher and worker | `cayu guide references#background-work` |
| Remembering facts across conversations | The knowledge tools (remember, search) | `cayu guide references#knowledge` |
| Running a fixed command or parsing files in isolation | `cayu new NAME --execution docker` on the agent preset: a hardened per-session sandbox your tools reach with `require_sandbox_runner(ctx)`. Don't switch to the coding preset for this. | `cayu guide references#environments` |
| Another agent for a sub-task | Subagent tools | `cayu guide references#subagents` |
| Spending or usage limits | Budgets and run limits | `cayu guide references#cost-control` |
| A public or multi-user product | `cayu new NAME --preset service` | `cayu guide references#server` |

Run every `cayu guide` command as `uv run --no-sync cayu guide ...`.

Use the Cayu Map to choose only the concepts the job needs:
`uv run --no-sync cayu guide authoring#cayu-map`. If the job observes, proposes, authorizes,
executes, verifies, or recovers an operational change, read the runnable paved
path first: `uv run --no-sync cayu guide durable-operations`.

If another capability is required, use the smallest package-shipped reference
from `uv run --no-sync cayu guide references`.

OpenRouter is a first-class scaffold choice. Fireworks, Baseten, OpenCode Go,
and other compatible endpoints work through Cayu's generic adapter. Run
`uv run --no-sync cayu guide providers#compatible-chat-completions` for exact setup.

This scaffold is for local development. Deployment is a separate task.
If the requested application is public or multi-user, regenerate with
`cayu new NAME --preset service` or adopt Cayu's maintained service contract;
do not improvise product authorization around raw Cayu routes.

## Project commands

- Setup: `uv sync --extra dev`.
- Run setup and proof commands sequentially. Do not parallelize application-
  constructing commands against the same database.
- Application contract: `uv run --no-sync cayu guide anatomy`.
- Authoring details: `uv run --no-sync cayu guide authoring`.
- Inspect/check: `uv run --no-sync cayu inspect --json` and
  `uv run --no-sync cayu check --fail-on warning --json`.
- Hermetic proof: `uv run --no-sync pytest` and `uv run --no-sync cayu eval run`.
- Local developer/operator control plane: run `uv run --no-sync cayu serve --dev` in a separate
  terminal and open `http://127.0.0.1:8000/cayu/`. This is not the application's
  end-user UI or a production server configuration.
- Deployed control plane: `cayu serve` without `--dev` authenticates operators with
  `CAYU_OPERATOR_USERNAME` and `CAYU_OPERATOR_PASSWORD` through
  `[tool.cayu.serve].auth` and refuses to start without them. Keep that setting
  unless you replace it with another authentication dependency; never remove it.
- First Control Plane evaluation: `uv run --no-sync cayu guide evals-first`.
- Never mount it with `OpenAccess()` on a public listener.
- Client-IP and forwarded-header checks are not authentication. Use
  `AuthenticatedAccess(...)` for any public or deployed control-plane surface.
- Live execution: `uv run --no-sync python run.py --message "USER REQUEST"` after configuring a
  provider in `app.configured_provider()`.

Use public `cayu` imports and public CLI JSON only. Do not depend on Cayu source,
private symbols, or import-time application construction.

If the job truly needs a tool, read `cayu guide tool-effects`; every tool must
declare `ToolEffect`, and effect metadata does not authorize execution. Every
custom tool, including read-only ones, also needs
`execution_profile_identity=ExecutionProfileBehaviorIdentity(name=..., behavior_version="1", implementation_version="1")`
in its class-level `ToolSpec`: without it, paused or resumed sessions fail with
`ExecutionProfileMismatchError ... tool_implementations` as soon as the tool set
changes. Bump `behavior_version` when a tool's behavior changes. A
`ScriptedModelProvider` proves handling of predetermined calls, not prompt
comprehension or live model behavior. A custom tool's result reaches the model
only through its `content`, never its `structured` data: assert on
`model_facing_text(provider.requests[i])` to check what the real model would read.

For the starter's first real tool, run
`uv run --no-sync cayu generate tool TOOL_NAME --agent cayu-campus-dining-demo --effect EFFECT`.
Then replace the generated sample schema, implementation, test, and eval with
domain behavior; `cayu check` keeps the tracer-bullet warning active until the
explicit authoring marker is removed.

## Capability profile

The scaffold contract, explicit registration, capability cards, and commands below describe the same normalized profile. Inclusion alone grants no model exposure or execution authority. `cayu new` also creates ignored private `data/memory-evidence.key` material for durable recall evidence; set `CAYU_MEMORY_EVIDENCE_KEY` to rotate or provision it outside local development.

| Capability | State | Contract |
| --- | --- | --- |
| `knowledge` | configured | Reviewed durable knowledge, retrieval, curation, and maintenance. |
| `memory` | configured | Context selection, recall, compaction, and memory attribution. |
| `mcp` | available, not configured | External MCP clients, protocols, and hosted-tool adapters. |
| `tasks` | configured | Durable tasks and application-owned operation lifecycle wiring. |
| `human-input` | configured | Durable pause and application-owned human input resolution. |
| `approvals` | configured | Explicit approval policy and settlement boundaries. |
| `artifacts` | configured | Durable local artifacts with bounded model-facing discovery. |
| `recovery` | configured | Durable interruption inspection and explicit recovery entry points. |
| `evals` | configured | Credential-free behavioral acceptance and durable eval evidence. |
| `observability` | configured | Event sinks, logging, tracing, and metrics adapters. |


## Cayu application convention

`[tool.cayu.scaffold]` records the exact generated plan. It is a source
generation and checking contract, not runtime authority. Implement a concern
in its owning package first, then wire it through `agents/registration.py` or
the explicit application composition seam. Keep `app.py` composition-only.

Service-owned artifact, knowledge, and delegation extensions are declared in
`[tool.cayu.scaffold].extensions`, sorted and unique, after explicit wiring.
Keep generated `capabilities` unchanged. See
`cayu guide applications#explicit-service-extensions` for migration and scope
requirements; declarations grant no authority and do not change authentication.

| Requested concern | Canonical home |
| --- | --- |
| Agent identity, model defaults, thinking, and metadata | `agents/` |
| System/developer prompt material | `prompts/` |
| Native model-callable capability and `ToolEffect` | `tools/` |
| Exposure, grants, authorization, approval, context, execution, egress, budgets, retries | `policies/` |
| Workspace, runner, artifacts, vaults, MCP servers, knowledge bindings, lifecycle | `environments/` |
| Deterministic multi-step orchestration | `workflows/` |
| Tasks, workers, watchers, interruptions, completion, and recovery | `operations/` |
| Reviewed knowledge, retrieval, curation, embeddings, and maintenance | `knowledge/` |
| Model-facing context, recall, compaction, and memory attribution | `memory/` |
| Business rules and data transformations | `domain/` |
| External clients, protocols, and MCP adapters | `integrations/` |
| Behavioral acceptance evidence | `evals/` |
| Runtime correctness and architectural contracts | `tests/` |
| Event sinks, logging, tracing, and metrics adapters | `observability/` |
| Final explicit construction and registration only | `app.py` |

Runtime sessions, transcripts, events, checkpoints, tasks, leases, approvals,
receipts, knowledge entries, indexes, usage, artifacts, eval results, and
snapshots belong in configured stores, never in source packages.

Use `understand -> inspect -> plan -> change -> test -> eval -> exercise ->
report evidence`. Reproduce this exact selected architecture safely in a
disposable reference, reviewing the write-free preview before applying it:

```bash
reference_parent="$(mktemp -d)"
uv run --no-sync cayu new campus-dining-demo_reference --preset agent --provider openai --execution none --json --agent-name "cayu-campus-dining-demo" --dir "$reference_parent" --dry-run
uv run --no-sync cayu new campus-dining-demo_reference --preset agent --provider openai --execution none --json --agent-name "cayu-campus-dining-demo" --dir "$reference_parent"
```

Run the command through `uv --no-sync` so the disposable reference uses this
project's installed, exactly pinned Cayu version even though its target directory
is elsewhere. The project-local uv cache under ignored `.cayu/` keeps these
commands usable in workspace-restricted coding-agent sandboxes. `cayu new`
creates projects; it does not migrate an existing repository. For a reviewed
plan change, adjust the reference flags, compare only the owning files, then
update this project and `[tool.cayu.scaffold]` explicitly.

Do not grant authority through prompts, add filesystem auto-discovery, rewrite
arbitrary Python, start lifecycle work during import, or delete the scaffold
contract to silence diagnostics. A custom layout is an explicit migration.


## Durable data

Cayu's session, task, and knowledge stores live in the configured database.
`configuration/storage.py` opens them with `open_application_stores`:
`CAYU_DATABASE_URL` selects PostgreSQL, and without it they use local SQLite at
`data/cayu.db`. Cayu CLI commands resolve `CAYU_DATABASE_URL` before
`[tool.cayu.session_store]`, so they read the same database as the app.

- Keep application-owned durable records, such as orders, cases, ledgers, and
  sync cursors, in that configured database. Application tables may share it
  with their own table prefix; Cayu reserves the `cayu_` prefix for its tables.
- `data/` locally and `/data` in a deployment hold files: artifacts, uploads,
  and fixtures. Do not open SQLite files there for durable application state; a
  deployment's `/data` may be a network filesystem.
- Deployments set `CAYU_DATABASE_URL` to a migrated PostgreSQL database
  (`cayu storage migrate` is a deploy step; running apps only validate the
  schema) and set `CAYU_REQUIRE_POSTGRES=1`, which makes every Cayu SQLite store
  refuse to open instead of silently writing local files.
- `CAYU_DATABASE_POOL_MAX` (default 5) bounds the shared connection pool. Behind
  a transaction-pooling proxy such as PgBouncer, set `CAYU_DATABASE_DIRECT_URL`
  to a direct server address for the task-admission `LISTEN` connection.
- Deployments must set `CAYU_MEMORY_EVIDENCE_KEY`. The local
  `data/memory-evidence.key` is git-ignored and never reaches a deployment.
