# Validation — 2026-09-14

Runtime: public Cayu `0.5.2`, commit
`c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b`. The Python dependency,
presenter wheel, and unmodified browser-worker inputs use this same commit.
Provider: OpenAI Responses at `https://api.openai.com/v1`, configured through
`OPENAI_API_KEY`; model defaults to `gpt-5.6-sol` and supports `CAYU_MODEL`.

## Reproducible checks

Run setup from README, then `python3 scripts/verify.py`. The script checks a
fresh source snapshot with disposable application and CLI eval databases. It
also verifies the presenter's exported Python lock and the dashboard API
baseline against the installed Runtime. It never uses a provider credential.

The clean-source run passed Cayu inspection/check (zero diagnostics), Ruff,
55 Python tests, including missing-key startup and an exact outgoing Responses
URL regression check, the native nine-case eval suite, and the separate
nine-case JSON/HTML report runner.
Two upstream FastAPI/Starlette deprecation warnings remain on Python 3.14.
Dashboard verification is included in the same command and was also rerun after
the responsive navigation fix.

GitHub recognizes the verification workflow, but organization policy disables
Actions for this repository. Enabling it at repository scope returned HTTP 409.
No hosted CI run is claimed; an organization owner must allow Actions before
the committed workflow can run. Organization policy was not changed.

## Build evidence

Both Docker images built successfully on macOS Apple Silicon:

- Browser worker: `cayu-campus-browser:c5816d0` (separate build-only tag).
- Presenter: `cayu-campus-viewer:c5816d0`, built from the public Runtime wheel,
  digest-pinned Python 3.12 base, and hash-checked Python dependencies.
- Presenter `pip check`: passed.
- Network-disabled presenter smoke: authentication, health, API contract 44,
  knowledge, nine eval definitions, and the dashboard shell passed against the
  installed image with disposable state and a read-only source mount.
- Dashboard: 314 tests passed; TypeScript/Vite production build, license checks,
  and generated API compatibility passed with Node 24.13.1.

The browser Dockerfile, seccomp profile, and all five worker modules were
compared byte-for-byte with the public commit. No local Runtime or worker patch
remains. Existing browser allocations and shared image tags were preserved.

The Docker base and Python dependencies are pinned. OS package repositories
and the fixture's wheel build tooling are not frozen snapshots; byte-identical
container rebuilds are not claimed.

## Browser rehearsal

Credential-free Chromium exercised New Run, published purchasing knowledge,
and the actual **Run all 9 checks** action: 9/9 passed with no page JavaScript
errors. Screenshot review caught a cramped mobile sidebar; navigation now uses
its compact icon rail below 768 px. The smoke test checks the main content width
as well as horizontal overflow. Final responsive screenshot verification passed at 390 px; the content area
remains at least 300 px wide with no horizontal overflow.

Reproduce with `uv run --no-sync python -m evals.ui_smoke`. This uses a disposable
protected loopback presenter and real browser; model calls are scripted.

Live OpenAI execution now verifies both purchasing decisions: seven cases of
peeled potatoes for $175 under the short-staffed plan, then four cases of whole
potatoes for $96 after the full-team revision. The real supplier preview and
saved-video playback were observed, and independent business-store inspection
confirmed zero orders. The final unmodified rehearsal ran both turns from a
fresh presenter without retries or diagnostic reattachment in 338 seconds,
including startup and recording-session preparation. It reported no uncaught
browser JavaScript errors. Recordings are sampled and can include declared capture
gaps; this is playback evidence, not a claim of gap-free screen recording.

The regression fixes are application-owned:

- Worker replacement no longer imports Cayu through configuration re-exports
  before doing any lifecycle work. Startup and transition waits cover both
  worker shutdown and startup, and failed startup is not reported as ready.
- The original mutation stream stays connected across tab changes and drains
  through EOF after a terminal event. Same-session preparation waits for that
  request to finish before dispatching a follow-up. Cleanup timeouts remain
  uncertain and do not replay model work.
- The recording panel fetches when it becomes visible, so a lookup made before
  capture starts cannot permanently hide the finished recording.
- OpenAI uses its native non-streaming Responses mode. The browser remains live;
  final text arrives together, reducing tiny persisted text events. The agent
  assesses catalog candidates before visiting detail pages and keeps its final
  recommendation brief and in plain text for the presenter.
- The browser test uses bounded session-state polling, tolerates transient
  read-only transport failures, and surfaces composer errors immediately.

The earlier provider URL regression is also covered: Cayu appends `/v1` itself,
so the application uses the native adapter default. A request-level test
requires exactly `https://api.openai.com/v1/responses` and non-streaming mode.
The key is forwarded through `OPENAI_API_KEY`, never stored in source or
presenter configuration files.

The opt-in command is:

```sh
uv run --no-sync python -m evals.browser_rehearsal --state-dir /absolute/private/presenter-state
```

It launches Chromium, submits the dinner request through New Run, requires an
actual live supplier preview, checks the seven-case peeled-potato draft,
continues with full kitchen staffing, checks the four-case whole-potato draft,
plays a saved recording, and independently verifies zero recorded orders.
Screenshots, videos, and detailed results belong in ignored private storage.

The scripted checks establish tool handling and business outcomes. The live
rehearsal adds evidence for this two-turn fixture on the current Runtime and
provider; it does not qualify every possible meal request or provider model.

## Public-source checks

The published source and its single-commit history passed a redacted Gitleaks
scan. Provider and startup regression tests passed (7 tests). Chromium repeated
navigation, knowledge, all nine UI evals, and mobile checks with a generated
presenter password and no JavaScript errors. New presenters generate their own
password; the provider credential remains environment-only. Required upstream
license attributions are preserved. Distribute a fresh clone or source archive,
never local state or recordings.

## State and scope

Start the upgraded presenter with fresh private state. Existing local CLI
storage was at schema revision 82 and requires migrations 83–85. It was left
unchanged; the application-specific session upgrade exception was removed.
For existing installations, inspect through `cayu storage status` and resolve
old sessions using the original installation before planning a migration.

This is an authenticated, loopback-only synthetic demo with a generated presenter password.
Multi-user hosting and deployment are separate work. Retained-browser restart
recovery and real supplier purchasing are not qualified by these checks.
