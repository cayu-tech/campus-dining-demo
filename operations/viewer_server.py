"""Protected local application server; run inside its exact Docker host container."""

import asyncio
import json
import os
from pathlib import Path

import uvicorn
from cayu.server import (
    BasicAuth,
    BrowserControlServerConfig,
    DashboardConfig,
    ServerConfig,
    create_server,
)
from cayu.server.browser_recording import BrowserRecordingServer
from pydantic import SecretBytes

from app import build_app
from configuration.recordings import recording_sessions, recording_store
from configuration.settings import ROOT, settings_from_environment
from configuration.viewer import viewer_configuration
from operations.demo_dashboard import DemoDashboard
from operations.demo_reset import DemoReset
from operations.initialize import initialize
from operations.recordings import prepare_recordings
from policies.recordings import RecordingAccess


def build_server(settings, *, provider=None):
    config = viewer_configuration(settings)
    if config is None:
        raise ValueError("A private CAMPUS_VIEWER_STATE configuration is required")
    app = build_app(settings=settings, provider=provider)
    auth = BasicAuth(
        username="local-presenter", password=config["password"], tenant=settings.customer
    )
    sessions = recording_sessions(settings)
    recordings = (
        BrowserRecordingServer(
            store=recording_store(settings),
            authorize=RecordingAccess(settings.customer, sessions).authorize,
        )
        if sessions
        else None
    )
    server = create_server(
        app,
        browser_recordings=recordings,
        config=ServerConfig.protected(
            auth,
            dashboard=DashboardConfig(path="/operator", directory=ROOT / "viewer-ui/dist"),
            browser_control=BrowserControlServerConfig(
                operator_origin=config["origin"],
                signing_key=SecretBytes(bytes.fromhex(config["viewer_key"])),
            ),
        ),
    )

    DemoReset(settings.viewer_state, app, auth, config["origin"]).install(server)
    DemoDashboard(app, settings, auth, config["origin"]).install(server)
    return server


def main():
    settings = settings_from_environment()
    if settings.viewer_state is None:
        raise SystemExit("Use the local viewer launcher")
    asyncio.run(initialize(settings))
    asyncio.run(prepare_recordings(settings))
    worker = {
        "pid": os.getpid(),
        "start_time": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19],
    }
    (settings.viewer_state / "worker.json").write_text(json.dumps(worker))
    uvicorn.run(
        build_server(settings),
        host="0.0.0.0",
        port=8443,
        ssl_certfile=str(settings.viewer_state / "certificate.pem"),
        ssl_keyfile=str(settings.viewer_state / "key.pem"),
        ws="websockets-sansio",
        ws_per_message_deflate=False,
        ws_max_size=2 * 1024 * 1024 + 4096,
        access_log=False,
        log_level="error",
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
