# approvals capability

1. **Behavior:** Explicit approval policy and settlement boundaries.
2. **Use it when:** the application needs explicit approval policy and settlement boundaries.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `operations/approvals.py`, `policies/tools.py`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
