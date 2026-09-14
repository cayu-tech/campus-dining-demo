# observability capability

1. **Behavior:** Event sinks, logging, tracing, and metrics adapters.
2. **Use it when:** the application needs event sinks, logging, tracing, and metrics adapters.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `configuration/runtime.py`, `observability/`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
   - `uv run --no-sync pytest`
