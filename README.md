# Campus dining purchasing demo

A fictional university dining demo built on Cayu. The agent keeps a planned meal feasible by comparing supplier products against cooked yield, kitchen inventory, preparation capacity, delivery, dietary requirements, stock, and budget. It browses a local supplier portal, explains its choice, prepares an immutable proposal, and requires human approval before recording an order.

## Try the scenario

Open **New Run**, choose **Dinner shortage**, and run the default request: dinner for 400 students tomorrow, usual potatoes unavailable, short-staffed, draft only. Open the session to see the live browser beside the conversation. After completion, the same panel plays saved browser videos.

The fixture requires 80 kg cooked potatoes, with 20 kg already in the kitchen. With 45 minutes of preparation available, seven cases of peeled potatoes provide 66.5 kg for $175. Whole potatoes cost $96 for four cases but need 180 minutes of preparation. Tell the agent that the full kitchen team is now available and ask it to reconsider: 240 minutes are available, so the cheaper whole potatoes become feasible. The prompt does not prescribe a SKU; deterministic tools calculate eligibility and the model chooses and explains the draft.

Other options expose meaningful constraints: late frozen delivery, unverified dairy in prepared mash, and unavailable baby potatoes. Rice lunch and a carrot side have their own meal records. Requests outside those records need clarification; this is a bounded fixture, not a general purchasing integration. All suppliers, prices, yields, dietary attestations, and delivery promises are synthetic.

Ask to submit only when ready. Review the exact product, cases, cost, meal revision, preparation, yield, and delivery, then approve or deny. Changing a plan invalidates its prior proposal. Submission rechecks current policy, plan and product facts, and stock; an idempotent receipt records one stock decrement. There is no browser checkout endpoint.

## Setup

Requires Python 3.11+, uv, Node 22.18+ (validated with 24.13.1), npm, Docker, and an OpenAI API key. Cayu is pinned to public commit `c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b`.

```sh
uv sync --extra dev --extra viewer --frozen
uv run --no-sync python -m playwright install chromium
npm ci --prefix viewer-ui
npm run build --prefix viewer-ui
```

Follow [viewer setup](viewer-host/README.md) to build the images and start the protected local presenter. Provider access must be provisioned separately; no credentials or presenter state are included.

## Verify

After setup, run the same credential-free checks used by CI:

```sh
python3 scripts/verify.py
```

This runs the lock check, initialization, Cayu inspection/check, Ruff, Python tests,
scripted evals, API compatibility, dashboard tests, and production build in sequence.
A fresh source copy, application state, and eval reports use a disposable directory; presenter sessions
are untouched. For persistent local CLI use, initialize once with
`uv run --no-sync python demo.py init` before `run.py` or Cayu inspection commands.

For an additional credential-free Chromium check after installing Playwright, run
`uv run --no-sync python -m evals.ui_smoke`. It opens the protected presenter,
checks the knowledge page, runs all nine checks from the Evals page, and checks
mobile overflow and browser errors. Screenshots stay under ignored
`validation/private/ui-smoke/`. This does not run a live model.

Unit and scripted-provider tests cover business arithmetic, infeasible choices, plan revisions, stale proposals, exact approval/denial, idempotency, scope, and the read-only portal. The [nine-case eval suite](evals/README.md) checks exact purchasing outcomes and the approval gate in isolated state. Run `uv run --no-sync python -m evals.run` for contract checks, or `uv run --no-sync python -m evals.run --live --all` for an explicit live-model evaluation. Scripted evals prove tool behavior, not model understanding. See [validation](VALIDATION.md) for current evidence and live browser limitations.

The **Evals** page lists all nine contract scenarios, their expected purchasing outcomes, and the latest dashboard run, with a **Run all 9 checks** button and full report. **Knowledge** displays the active purchasing policy and source; the pending review queue remains below it.

## Structure and boundaries

`domain/` owns plans, assessments, proposals, receipts, and SQLite transactions. `tools/` exposes explicit business operations. `policies/` owns exposure, approval, budget and browser egress. `knowledge/` seeds reviewed purchasing policy. `catalog-app/` serves only read-only product and meal information. `operations/` owns the protected presenter, capture grants, and reset lifecycle. `viewer-ui/` is a pinned, locally customized operator dashboard.

The presenter is a single-customer local demo with authenticated loopback TLS, not a hosted multi-user service. Browser access is restricted to the fixture supplier origin. Only declared dining questions and application-owned proposal fields can reach the protected review controls. Model prose is not approval authority. Keep private state directories and generated recordings out of Git.

For an opt-in live rehearsal against a fresh presenter, run `uv run --no-sync python -m evals.browser_rehearsal --state-dir /absolute/private/presenter-state`. It uses the live provider, drives the UI, checks the changed draft, and plays its recording. Existing comparison sessions are refused to avoid duplicate work.

## Customer handoff

Share a fresh clone or a source archive of the reviewed commit, not this working
directory. Generated state, credentials, recordings, environments, caches, and
wheels are excluded from Git. Preserve the worker and dashboard license notices.
Start the presenter with a fresh private state directory and the separately
provisioned model credential. Each presenter generates a unique password for the `local-presenter` login.
Use `viewer.py open` to sign in to this loopback-only demonstration. Public hosting is a separate service project.

The CI workflow runs the same verification command on Python 3.12, then installs
Chromium and runs the credential-free UI smoke test. Review
[VALIDATION.md](VALIDATION.md) for what was exercised on the current Runtime pin
and the remaining live rehearsal limits before presenting.
