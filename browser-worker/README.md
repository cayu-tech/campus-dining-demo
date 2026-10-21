# Pinned browser worker

Dockerfile, seccomp profile, and all five worker Python files are unmodified build
inputs from public Cayu commit `8355cca9f8783adae5ebd2bf42643827ccd24eec`.
The native form-control recording fix is included upstream. There are no local
worker patches. The application imports the installed Cayu package; these files
execute only inside the browser image. Upstream LICENSE and NOTICE are retained.

Build from the demo root on a machine without active Cayu browser allocations:

```sh
docker build -t cayu-browser-fetch:13-playwright-1.62.0 browser-worker
```

The Runtime adapter validates this workload tag and its protocol labels. Do not
replace the shared tag during another evaluation. For build-only verification,
use a separate tag such as `cayu-campus-browser:8355cca`.

Update these inputs and the Runtime lock together. Start with fresh presenter
state after an upgrade; there is no demo-specific session migration exception.
