"""Provision explicit session capture grants before application construction."""

import json
import os
from uuid import uuid4

from cayu import BrowserRecordingPolicy

from configuration.recordings import recording_sessions, recording_store


async def prepare_recordings(settings):
    sessions = recording_sessions(settings)
    if not sessions:
        return
    store = recording_store(settings)
    path = settings.data_dir / "recording-grants.json"
    values = json.loads(path.read_text()) if path.exists() else {}
    for session_id in sessions:
        if session_id in values:
            continue
        config = await store.authorize_capture(
            session_id=session_id,
            policy=BrowserRecordingPolicy(
                scope="campus-" + uuid4().hex,
                allowed_origins=("https://supplier.campus-demo.test",),
                retention_seconds=7 * 24 * 3600,
                max_duration_seconds=900,
                max_bytes=64 * 1024 * 1024,
                frames_per_second=2,
            ),
            guest_endpoint="wss://cayu-control:8443/api/browser-recordings/guest",
        )
        values[session_id] = {
            **config.model_dump(mode="json"),
            "credential": config.credential.get_secret_value(),
        }
        temporary = path.with_name(".recording-grants-" + uuid4().hex)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(values, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)


async def delete_recordings_before_reset(settings):
    if not (settings.data_dir / "private-recordings.sqlite").is_file():
        return
    store = recording_store(settings)
    for session_id in recording_sessions(settings):
        for recording_id in await store.recordings_for_session(session_id):
            await store.delete(recording_id)
    await store.purge_expired()
