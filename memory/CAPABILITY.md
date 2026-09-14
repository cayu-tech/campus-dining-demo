# memory capability

1. **Behavior:** Context selection, recall, compaction, and memory attribution.
2. **Use it when:** the application needs context selection, recall, compaction, and memory attribution.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `memory/`, `policies/context.py`.
6. **Verify:**
   - `uv run --no-sync pytest -q tests/test_agent.py`
