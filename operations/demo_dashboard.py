"""Authenticated demo knowledge library and isolated dining eval reports."""

import asyncio
import json
from dataclasses import asdict
from uuid import uuid4

from cayu import eval_run_to_json, render_html_report, run_eval_plan
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from evals.agent import build_plan
from evals.cases import all_cases
from knowledge.retrieval import build_knowledge_scope
from operations.lifecycle import close_app


class DemoDashboard:
    def __init__(self, app, settings, auth, origin):
        self.app, self.settings, self.auth, self.origin = app, settings, auth, origin
        self.lock = asyncio.Lock()
        self.directory = settings.data_dir / "dining-evals"

    def latest(self):
        pointer = self.directory / "latest.json"
        return json.loads(pointer.read_text()) if pointer.exists() else None

    def install(self, server):
        @server.get("/api/demo/knowledge")
        async def knowledge(request: Request):
            await self.auth(request)
            entry = await self.app.knowledge_store.get_entry(
                "purchasing-policy", access_scope=build_knowledge_scope(self.settings)
            )
            fields = ("id", "title", "text", "status", "revision", "namespace", "source_uri")
            return {
                "entries": []
                if entry is None
                else [{key: entry.model_dump(mode="json")[key] for key in fields}],
                "recall": "Automatic recall uses active purchasing knowledge. Past-session transcript recall is disabled.",
            }

        @server.get("/api/demo/evals")
        async def evals(request: Request):
            await self.auth(request)
            return {
                "cases": [asdict(case) for case in all_cases()],
                "running": self.lock.locked(),
                "latest": self.latest(),
            }

        @server.get("/api/demo/evals/report", response_class=HTMLResponse)
        async def report(request: Request):
            await self.auth(request)
            latest = self.latest()
            if latest is None:
                raise HTTPException(404, "Run the dining eval suite first.")
            return HTMLResponse((self.directory / latest["id"] / "report.html").read_text())

        @server.post("/api/demo/evals/run")
        async def run(request: Request):
            await self.auth(request)
            if request.headers.get("origin") != self.origin:
                raise HTTPException(403, "Run evals from the demo dashboard.")
            if self.lock.locked():
                raise HTTPException(409, "The dining eval suite is already running.")
            async with self.lock:
                run_id = uuid4().hex
                directory = self.directory / run_id
                directory.mkdir(mode=0o700, parents=True)
                plan = await build_plan(directory=directory / "fixtures")
                try:
                    result = await run_eval_plan(plan, case_timeout_seconds=300, max_concurrency=1)
                    data = json.loads(eval_run_to_json(result))
                    (directory / "result.json").write_text(json.dumps(data))
                    (directory / "report.html").write_text(render_html_report(result))
                    summary = {
                        "id": run_id,
                        "status": data["status"],
                        "cases": [
                            {"case_id": case["case_id"], "status": case["status"]}
                            for case in data["cases"]
                        ],
                    }
                    temporary = self.directory / "latest.tmp"
                    temporary.write_text(json.dumps(summary))
                    temporary.replace(self.directory / "latest.json")
                    return summary
                finally:
                    await close_app(plan.app)
