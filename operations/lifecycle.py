"""Explicit close of process-owned resources; Cayu remains execution owner."""

import inspect


async def close_app(app):
    seen = set()
    for obj in (
        app.session_store,
        app.task_store,
        app.knowledge_store,
        *[app.get_provider(p.name) for p in app.describe().providers],
    ):
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        method = getattr(obj, "aclose", None) or getattr(obj, "close", None)
        if method:
            result = method()
            if inspect.isawaitable(result):
                await result
