"""Exercise protected demo views against actual knowledge and native eval execution."""

import asyncio

import httpx
from cayu import ScriptedModelProvider, SessionQuery
from cayu.server import BasicAuth
from fastapi import FastAPI

from app import build_app
from operations.demo_dashboard import DemoDashboard
from operations.lifecycle import close_app


def test_demo_views_auth_scope_execution_and_saved_results(settings):
    async def run():
        app = build_app(settings=settings, provider=ScriptedModelProvider([]))
        server = FastAPI()
        dashboard = DemoDashboard(
            app, settings, BasicAuth(username="local-presenter", password="demo"), "http://demo"
        )
        dashboard.install(server)
        transport = httpx.ASGITransport(app=server)
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://demo") as client:
                assert (await client.get("/api/demo/knowledge")).status_code == 401
                assert (await client.post("/api/demo/evals/run")).status_code == 401
                client.auth = ("local-presenter", "demo")
                knowledge = (await client.get("/api/demo/knowledge")).json()
                assert len(knowledge["entries"]) == 1
                entry = knowledge["entries"][0]
                assert entry["id"] == "purchasing-policy" and entry["status"] == "active"
                assert entry["namespace"] == settings.namespace
                assert entry["text"]
                initial = (await client.get("/api/demo/evals")).json()
                assert len(initial["cases"]) == 9 and initial["latest"] is None
                assert (await client.get("/api/demo/evals/report")).status_code == 404
                assert (await client.post("/api/demo/evals/run")).status_code == 403
                first = asyncio.create_task(
                    client.post("/api/demo/evals/run", headers={"Origin": "http://demo"})
                )
                try:
                    for _ in range(100):
                        if dashboard.lock.locked():
                            break
                        await asyncio.sleep(0.01)
                    assert dashboard.lock.locked()
                    duplicate = await client.post(
                        "/api/demo/evals/run", headers={"Origin": "http://demo"}
                    )
                    assert duplicate.status_code == 409
                    result = await first
                finally:
                    if not first.done():
                        first.cancel()
                        await asyncio.gather(first, return_exceptions=True)
                assert result.status_code == 200, result.text
                assert result.json()["status"] == "passed"
                assert len(result.json()["cases"]) == 9
                assert all(case["status"] == "passed" for case in result.json()["cases"])
                assert (await client.get("/api/demo/evals")).json()["latest"] == result.json()
                assert (await client.get("/api/demo/evals/report")).status_code == 200
                # A new controller can read the persisted report; fixture sessions stay isolated.
                replacement = DemoDashboard(app, settings, None, "http://demo")
                assert replacement.latest() == result.json()
                assert not (await app.session_store.list_sessions(SessionQuery())).sessions
        finally:
            await close_app(app)

    asyncio.run(run())
