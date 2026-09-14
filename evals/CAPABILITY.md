# evals capability

1. **Behavior:** Credential-free behavioral acceptance and durable eval evidence.
2. **Use it when:** the application needs credential-free behavioral acceptance and durable eval evidence.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `evals/`.
6. **Verify:**
   - `uv run --no-sync cayu eval run`
