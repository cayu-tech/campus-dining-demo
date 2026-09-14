# tasks capability

1. **Behavior:** Durable tasks and application-owned operation lifecycle wiring.
2. **Use it when:** the application needs durable tasks and application-owned operation lifecycle wiring.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `operations/tasks.py`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
