"""Worker replacement can start without importing the agent Runtime first."""

import asyncio
import json
import subprocess
import sys

import httpx
from fastapi import FastAPI

from operations.demo_reset import DemoReset


def test_transition_entrypoint_does_not_load_cayu():
    subprocess.run(
        [sys.executable, "-c", ("import sys; import operations.demo_reset; "
          "assert 'cayu' not in sys.modules")], check=True, timeout=30,
    )


def test_failed_startup_is_not_reported_as_ready(tmp_path):
    (tmp_path / "configuration.json").write_text(json.dumps({
        "recording_session": "comparison", "recording_sessions": ["comparison"],
    }))
    (tmp_path / "reset-job.json").write_text(json.dumps({"status": "failed"}))

    async def run():
        async def auth(request):
            pass

        server = FastAPI()
        DemoReset(tmp_path, None, auth, "http://demo").install(server)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server), base_url="http://demo"
        ) as client:
            response = await client.get("/demo/recording-session")
        assert response.status_code == 200
        assert response.json()["ready"] is False
        assert response.json()["status"] == "failed"

    asyncio.run(run())


def test_recording_readiness_waits_for_mutation_stream_cleanup(tmp_path):
    from starlette.responses import StreamingResponse

    (tmp_path / "configuration.json").write_text(json.dumps({
        "recording_session": "comparison", "recording_sessions": ["comparison"],
    }))

    async def run():
        async def auth(request):
            pass

        terminal_emitted = asyncio.Event()
        cleanup_finished = asyncio.Event()
        server = FastAPI()
        DemoReset(tmp_path, None, auth, "http://demo").install(server)

        @server.post("/api/run")
        async def start():
            async def events():
                yield b"data: session.completed\n\n"
                terminal_emitted.set()
                await cleanup_finished.wait()
            return StreamingResponse(events(), media_type="text/event-stream")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server), base_url="http://demo"
        ) as client:
            running = asyncio.create_task(client.post("/api/run"))
            try:
                await asyncio.wait_for(terminal_emitted.wait(), 5)
                waiting = await client.get("/demo/recording-session")
                assert waiting.json()["ready"] is False
            finally:
                cleanup_finished.set()
                await running
            ready = await client.get("/demo/recording-session")
            assert ready.json()["ready"] is True

    asyncio.run(run())
