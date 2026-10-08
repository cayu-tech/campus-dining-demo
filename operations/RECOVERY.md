# recovery capability

1. **Behavior:** Durable interruption inspection and explicit recovery entry points.
2. **Use it when:** the application needs durable interruption inspection and explicit recovery entry points.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `operations/recovery.py`, `operations/workers.py`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
