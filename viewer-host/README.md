# Protected local presenter

The trusted application container hosts the installed Cayu Runtime and a separately built dashboard. The agent browser runs in its own Docker allocation. Runtime is pinned to public commit `c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b`. The [browser worker](../browser-worker/README.md) uses unmodified inputs from the same commit.

## Build and launch

Build the installed Runtime wheel from a disposable checkout; the wheel is intentionally excluded from Git:

```sh
runtime_build_dir="$(mktemp -d)/runtime"
git clone https://github.com/cayu-dev/cayu.git "$runtime_build_dir"
git -C "$runtime_build_dir" checkout --detach c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b
npm ci --prefix "$runtime_build_dir/dashboard"
npm run build:package --prefix "$runtime_build_dir/dashboard"
uv build --wheel --out-dir viewer-host "$runtime_build_dir"
docker build -t cayu-browser-fetch:13-playwright-1.62.0 browser-worker
docker build -f viewer-host/Dockerfile -t cayu-campus-viewer:c5816d0 .
```

The browser image tag is shared by the local Runtime adapter. Do not rebuild it while another evaluation uses it. The trusted application host alone mounts Docker management access. No service port is published beyond loopback.

The presenter base image is pinned by digest. Its Python dependency versions and
hashes are exported from the root `uv.lock` into `requirements.lock`; package
installation checks hashes and `pip check` validates the resulting environment.
When changing the root lock, regenerate this file from the demo root:

```sh
uv export --frozen --extra viewer --no-dev --no-emit-project --no-emit-package cayu --no-emit-package campus-catalog-fixture --format requirements-txt --output-file viewer-host/requirements.lock
```

Each new presenter uses username `local-presenter` and a randomly generated
password stored in its private configuration. The `open` command reads that
password automatically.

Set `OPENAI_API_KEY` in your shell; the app uses OpenAI directly at
`https://api.openai.com/v1`. The launcher forwards the environment variable to the
trusted presenter container, never to the browser worker or dashboard. It does
not write the key into the source or presenter configuration files. You can set
`CAYU_MODEL` to override the default `gpt-5.6-sol`. Cayu uses its native
non-streaming Responses mode: the browser preview remains live, and the final
answer appears together when the model finishes.

On macOS, with your API key copied to the clipboard:

```sh
export OPENAI_API_KEY="$(pbpaste)"
```

This follows [OpenAI's environment-variable setup](https://developers.openai.com/api/docs/quickstart).
Choose a fresh private state directory:

```sh
uv run --no-sync python viewer.py start --state-dir /tmp/campus-presenter
uv run --no-sync python viewer.py open --state-dir /tmp/campus-presenter
```

`open` launches Chromium with the generated certificate's public-key pin and presenter login. It does not change system trust. The state directory contains credentials, signing keys, databases, and recordings; never commit or distribute it. Keep the source and state paths stable while sessions are paused because Docker bind mounts use those paths.

To use your regular Chrome browser, start the host as above, then read its URL and login and open Chrome explicitly:

```sh
uv run --no-sync python - /tmp/campus-presenter <<'PYTHON'
import json, pathlib, subprocess, sys
config = json.loads((pathlib.Path(sys.argv[1]) / "configuration.json").read_text())
print("Username: local-presenter")
print("Password:", config["password"])
subprocess.run(["open", "-a", "Google Chrome", config["origin"] + "/operator/run"], check=True)
PYTHON
```

Regular Chrome may show a certificate warning for this local self-signed HTTPS endpoint. The `viewer.py open` helper is for the separate automated Chromium profile; use the command above for your own browser.

Initial startup allows up to 120 seconds. Recording-session preparation allows
up to 180 seconds for shutdown and startup; failed preparation prevents dispatch.
Build the dashboard before starting a rehearsal, and keep its assets unchanged
while a browser tab is running the demo.

Default allowed sessions are `dinner`, `comparison`, `rice-lunch`, and `vegetable-side`. New Run prepares capture for the selected session before dispatch. Continue an existing session through its Resume input. Questions and approvals appear in that session's protected review card. Do not operate the presenter's database with a separate host-side application process.

After a Runtime upgrade, finish or resolve old sessions using their original installation, then start a fresh state directory. Existing sessions are not automatically migrated.

## Saved browser videos

The session page shows the live browser while running and saved videos after completion. Playback and download require the presenter identity and customer scope. Videos are silent sampled viewports at two frames per second, bounded to 1280×720, 64 MiB, and 15 minutes each. Navigation can introduce marked capture gaps. The private store is bounded at 512 MiB; capture grants expire after seven days. Each video's displayed expiry is authoritative. Sensitive and unsupported contexts are excluded by Runtime.

## Lifecycle

Reset demo is an authenticated administrative action that requires confirmation and refuses unfinished work. Settled interrupted sessions can also be abandoned by reset. Pending questions, approvals, recovery issues, active provider work, and unfinished interruption or browser cleanup still block it. It removes recorded media, privately archives the remaining old data, resets the fixture, and restarts the worker at the same URL. It is not an agent tool.

At a durable pause, `viewer.py restart-worker --state-dir /tmp/campus-presenter` replaces the worker within the same application container. This demo inherits retained-browser reconnect support; the campus-specific validation does not claim a new restart qualification. Manual browser takeover is disabled.

Finish or resolve sessions before `viewer.py stop --state-dir /tmp/campus-presenter`. Shutdown refuses to orphan retained browser allocations. Never use global Docker prune to clean up this demo.
