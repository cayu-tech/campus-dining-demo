# knowledge capability

1. **Behavior:** Reviewed durable knowledge, retrieval, curation, and maintenance.
2. **Use it when:** the application needs reviewed durable knowledge, retrieval, curation, and maintenance.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `knowledge/`, `configuration/storage.py`.
6. **Verify:**
   - `uv run --no-sync cayu check --json`
