# artifacts capability

1. **Behavior:** Durable local artifacts with bounded model-facing discovery.
2. **Use it when:** the application needs durable local artifacts with bounded model-facing discovery.
3. **Project state:** configured by `[tool.cayu.scaffold]`.
4. **Restricted/unavailable:** selection grants no implicit model exposure, effect authority, credentials, network, runner, or lifecycle startup.
5. **Explicit seam:** `environments/local.py`, `data/artifacts/`.
6. **Verify:**
   - `uv run --no-sync pytest -q tests/test_application.py`
