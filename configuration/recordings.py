"""Explicit capture scopes and private application-owned recording storage."""

import json

from cayu import BrowserRecordingConfig, BrowserRecordingStore

from configuration.viewer import viewer_configuration


def recording_sessions(settings):
    config = viewer_configuration(settings)
    return tuple(config.get("recording_sessions", ())) if config else ()


def recording_store(settings):
    return BrowserRecordingStore(
        settings.data_dir / "private-recordings.sqlite",
        max_storage_bytes=512 * 1024 * 1024,
        max_recordings=128,
    )


def recording_configs(settings):
    sessions = recording_sessions(settings)
    if not sessions:
        return {}
    path = settings.data_dir / "recording-grants.json"
    if not path.is_file():
        raise RuntimeError("Prepare the recording grants before starting the viewer.")
    values = json.loads(path.read_text())
    result = {}
    for session_id in sessions:
        config = BrowserRecordingConfig.model_validate(values[session_id])
        if config.session_id != session_id:
            raise ValueError("Recording grant belongs to a different session.")
        result[session_id] = config
    return result


def active_recording_config(settings):
    config = viewer_configuration(settings)
    sessions = recording_sessions(settings)
    if not sessions:
        return None
    selected = config.get("recording_session", sessions[0])
    if selected not in sessions:
        raise ValueError("Recording session is not authorized.")
    return recording_configs(settings)[selected]
