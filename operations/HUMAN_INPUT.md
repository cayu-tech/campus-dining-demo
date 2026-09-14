# human-input capability

1. **Behavior:** Durable pause and application-owned human input resolution.
2. **Use it when:** the application needs durable pause and application-owned human input resolution.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `operations/approvals.py`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
