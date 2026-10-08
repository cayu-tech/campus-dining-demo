# mcp capability

1. **Behavior:** External MCP clients, protocols, and hosted-tool adapters.
2. **Use it when:** the application needs external MCP clients, protocols, and hosted-tool adapters.
3. **Project state:** available but not configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `integrations/mcp.py`.
6. **Verify:**
   - `uv run --no-sync cayu inspect --json`
