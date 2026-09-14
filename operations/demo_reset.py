"""Authenticated local-demo reset; never exposed as an agent capability."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool
from starlette.responses import JSONResponse

from configuration.settings import PRESENTER_STARTUP_SECONDS, PRESENTER_TRANSITION_SECONDS


class RecordingSessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    session_id: str


class ResetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    confirm: StrictBool


def request_identity(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "request_id must be a UUID") from exc


def read_job(root):
    path = root / "reset-job.json"
    return json.loads(path.read_text()) if path.exists() else {"status": "idle"}


def write_job(root, job):
    path = root / "reset-job.tmp"
    path.write_text(json.dumps(job))
    path.chmod(0o600)
    path.replace(root / "reset-job.json")


class ResetGate:
    def __init__(self, app, control):
        self.app = app
        self.control = control

    async def __call__(self, scope, receive, send):
        tracked = scope["type"] == "http" and scope["path"].startswith("/api/")
        if tracked and scope["path"] != "/api/health":
            if self.control.resetting or read_job(self.control.root)["status"] == "resetting":
                await JSONResponse({"detail": "Demo reset in progress."}, status_code=503)(
                    scope, receive, send
                )
                return
            mutating = scope["method"] == "POST"
            self.control.active_requests += 1
            if mutating:
                self.control.active_mutations += 1
            try:
                await self.app(scope, receive, send)
            finally:
                self.control.active_requests -= 1
                if mutating:
                    self.control.active_mutations -= 1
        else:
            await self.app(scope, receive, send)


class DemoReset:
    def __init__(self, root, app, auth, origin, launcher=None):
        self.root, self.app, self.auth, self.origin = root, app, auth, origin
        self.active_requests = 0
        self.active_mutations = 0
        self.resetting = False
        self.launcher = launcher or self.launch

    def launch(self, job):
        with (self.root / "reset-worker.log").open("ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "operations.demo_reset", str(self.root), job["request_id"]],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
            )

    def install(self, server):
        server.add_middleware(ResetGate, control=self)

        @server.get("/demo/reset")
        async def status(request: Request):
            await self.auth(request)
            job = read_job(self.root)
            return {k: v for k, v in job.items() if k in {"status", "request_id", "message"}}

        @server.get("/demo/recording-session")
        async def recording_status(request: Request):
            await self.auth(request)
            config = json.loads((self.root / "configuration.json").read_text())
            job = read_job(self.root)
            return {"session_id": config.get("recording_session"),
                    "enabled": bool(config.get("recording_sessions")),
                    "ready": job["status"] in {"idle", "complete"} and not self.active_mutations,
                    "status": job["status"],
                    "transition_timeout_seconds": PRESENTER_TRANSITION_SECONDS}

        @server.post("/demo/recording-session", status_code=202)
        async def select_recording_session(request: Request, body: RecordingSessionBody):
            from cayu import SessionQuery

            await self.auth(request)
            if request.headers.get("origin") != self.origin:
                raise HTTPException(403, "Select the session from this demo dashboard.")
            config = json.loads((self.root / "configuration.json").read_text())
            if body.session_id not in config.get("recording_sessions", ()):
                raise HTTPException(403, "This session is not authorized for recording.")
            job = read_job(self.root)
            if job["status"] == "resetting" or self.resetting:
                if job.get("request_id") == request_identity(body.request_id) and job.get("session_id") == body.session_id:
                    return {"ready": False, "session_id": body.session_id}
                raise HTTPException(409, "Another presenter transition is in progress.")
            if job["status"] == "failed":
                raise HTTPException(409, "Presenter startup failed. Inspect the worker logs.")
            if config.get("recording_session") == body.session_id:
                return {"ready": True, "session_id": body.session_id}
            self.resetting = True
            try:
                if self.active_requests:
                    raise HTTPException(409, "Wait for the current request to finish.")
                page = await self.app.session_store.list_sessions(SessionQuery(limit=1000))
                if page.next_cursor or any(s.status != "completed" for s in page.sessions):
                    raise HTTPException(409, "Complete the current run before switching recording sessions.")
                for session in page.sessions:
                    if not await self.app.discard_parked_egress_allocations(session.id):
                        raise HTTPException(409, "Browser cleanup is still in progress.")
                job = {"request_id": request_identity(body.request_id), "status": "resetting",
                       "kind": "recording_session", "session_id": body.session_id,
                       "worker": json.loads((self.root / "worker.json").read_text())}
                write_job(self.root, job)
                try:
                    self.launcher(job)
                except Exception:
                    write_job(self.root, {**job, "status": "failed", "message": "Could not prepare recording."})
                    raise
                return {"ready": False, "session_id": body.session_id}
            finally:
                self.resetting = False

        @server.post("/demo/reset", status_code=202)
        async def reset(request: Request, body: ResetBody):
            await self.auth(request)
            if request.headers.get("origin") != self.origin or not body.confirm:
                raise HTTPException(403, "Confirm reset from this demo dashboard.")
            request_id = request_identity(body.request_id)
            previous = read_job(self.root)
            if previous.get("request_id") == request_id:
                return {k: v for k, v in previous.items() if k in {"status", "request_id"}}
            if self.resetting or previous["status"] == "resetting":
                raise HTTPException(409, "A demo reset is already in progress.")
            self.resetting = True
            try:
                if self.active_requests:
                    raise HTTPException(409, "Wait for the current run to finish, then reset.")
                sessions = await resettable_sessions(self.app)
                # Public Runtime cleanup boundary; never inspect or edit private ownership journals.
                for session in sessions:
                    if not await self.app.discard_parked_egress_allocations(session.id):
                        raise HTTPException(409, "Browser cleanup is still in progress. Try again shortly.")
                worker = json.loads((self.root / "worker.json").read_text())
                job = {"request_id": request_id, "status": "resetting", "worker": worker}
                write_job(self.root, job)
                try:
                    self.launcher(job)
                except Exception:
                    write_job(self.root, {**job, "status": "failed", "message": "Could not start reset."})
                    raise
                return {"request_id": request_id, "status": "resetting"}
            finally:
                self.resetting = False



async def resettable_sessions(app):
    """Permit abandoned, settled interruptions without erasing unresolved work."""
    from cayu import PendingActionQuery, SessionQuery

    page = await app.session_store.list_sessions(SessionQuery(limit=1000))
    if page.next_cursor or any(s.status not in {"completed", "interrupted"} for s in page.sessions):
        raise HTTPException(409, "Stop the current run before resetting. Failed runs need inspection.")
    for session in page.sessions:
        pending = await app.session_store.query_pending_actions(
            PendingActionQuery(session_id=session.id, limit=1)
        )
        if pending.actions or pending.issues or pending.has_more or pending.next_cursor:
            raise HTTPException(
                409, "Resolve pending questions, approvals, or recovery actions before resetting."
            )
        if await app.interruption_cascade_status(session.id) != "none":
            raise HTTPException(409, "Wait for session interruption to settle before resetting.")
        if await app.session_store.load_active_model_completion_stage(session.id) is not None:
            raise HTTPException(409, "Provider work is still unsettled. Inspect the session before resetting.")
    return page.sessions


def same_process(worker):
    try:
        stat = Path(f"/proc/{worker['pid']}/stat").read_text()
        return stat.rsplit(")", 1)[1].split()[19] == worker["start_time"]
    except FileNotFoundError:
        return False


def reset_worker(root, request_id):
    import fcntl

    with (root / "reset.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        job = read_job(root)
        if job.get("request_id") != request_id or job["status"] != "resetting":
            return
        try:
            time.sleep(1)  # Allow the accepted HTTP response to leave the old worker.
            worker = job["worker"]
            if same_process(worker):
                os.kill(worker["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 30
            while same_process(worker):
                if time.monotonic() > deadline:
                    raise RuntimeError("The old worker did not stop; data was not reset.")
                time.sleep(0.1)
            config_path = root / "configuration.json"
            config = json.loads(config_path.read_text())
            if job.get("kind") == "recording_session":
                if job["session_id"] not in config.get("recording_sessions", ()):
                    raise RuntimeError("Recording session is no longer authorized.")
                config["recording_session"] = job["session_id"]
            else:
                import asyncio

                from configuration.settings import settings_from_environment
                from operations.recordings import delete_recordings_before_reset

                asyncio.run(delete_recordings_before_reset(settings_from_environment()))
                archive = root / f"data-before-reset-{request_id}"
                (root / "data").rename(archive)
            config_path.write_text(json.dumps(config))
            with (root / "worker.log").open("wb") as log:
                subprocess.Popen(
                    [sys.executable, "-m", "operations.viewer_server"],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                )
            import ssl

            import httpx

            tls = ssl.create_default_context(cafile=str(root / "certificate.pem"))
            with httpx.Client(base_url="https://127.0.0.1:8443", verify=tls, trust_env=False,
                              auth=("local-presenter", config["password"]), timeout=2) as client:
                deadline = time.monotonic() + PRESENTER_STARTUP_SECONDS
                while time.monotonic() < deadline:
                    try:
                        if client.get("/api/health").status_code == 200:
                            write_job(root, {"request_id": request_id, "status": "complete"})
                            return
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)
            raise RuntimeError("Reset worker did not become healthy. Saved data is preserved.")
        except Exception as exc:
            write_job(root, {"request_id": request_id, "status": "failed", "message": str(exc)})
            raise


if __name__ == "__main__":
    reset_worker(Path(sys.argv[1]), str(UUID(sys.argv[2])))
