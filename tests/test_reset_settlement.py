"""Reset must allow a settled interruption but retain unfinished action evidence."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from operations.demo_reset import resettable_sessions


def fixture_app(status="interrupted"):
    session = SimpleNamespace(id="dinner", status=status)
    pending = SimpleNamespace(actions=[], issues=[], has_more=False, next_cursor=None)
    store = SimpleNamespace(
        list_sessions=AsyncMock(return_value=SimpleNamespace(sessions=[session], next_cursor=None)),
        query_pending_actions=AsyncMock(return_value=pending),
        load_active_model_completion_stage=AsyncMock(return_value=None),
    )
    return SimpleNamespace(session_store=store, interruption_cascade_status=AsyncMock(return_value="none"))


@pytest.mark.parametrize("status", ["completed", "interrupted"])
def test_reset_accepts_settled_session(status):
    app = fixture_app(status)
    sessions = asyncio.run(resettable_sessions(app))
    assert [s.id for s in sessions] == ["dinner"]


@pytest.mark.parametrize("status", ["running", "pending", "failed"])
def test_reset_rejects_unsettled_or_unclassified_session(status):
    with pytest.raises(HTTPException) as error:
        asyncio.run(resettable_sessions(fixture_app(status)))
    assert error.value.status_code == 409


@pytest.mark.parametrize("field,value", [
    ("actions", ["approval"]), ("actions", ["user_input"]),
    ("issues", ["uncertain_effect"]), ("has_more", True), ("next_cursor", "more"),
])
def test_reset_preserves_pending_or_incomplete_evidence(field, value):
    app = fixture_app()
    setattr(app.session_store.query_pending_actions.return_value, field, value)
    with pytest.raises(HTTPException) as error:
        asyncio.run(resettable_sessions(app))
    assert error.value.status_code == 409


@pytest.mark.parametrize("blocker", ["cascade", "provider", "session_page"])
def test_reset_requires_settlement_and_complete_session_inventory(blocker):
    app = fixture_app()
    if blocker == "cascade":
        app.interruption_cascade_status.return_value = "pending"
    elif blocker == "provider":
        app.session_store.load_active_model_completion_stage.return_value = object()
    else:
        app.session_store.list_sessions.return_value.next_cursor = "more"
    with pytest.raises(HTTPException) as error:
        asyncio.run(resettable_sessions(app))
    assert error.value.status_code == 409


def test_reset_endpoint_accepts_interrupted_once(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from operations.demo_reset import DemoReset

    app = fixture_app()
    app.discard_parked_egress_allocations = AsyncMock(return_value=True)
    (tmp_path / "worker.json").write_text('{"pid":123,"start_time":"test"}')
    launches = []

    async def auth(request):
        return None

    server = FastAPI()
    DemoReset(tmp_path, app, auth, "https://demo.test", launcher=launches.append).install(server)
    with TestClient(server) as client:
        body = {"request_id": "ba36f6c7-5753-421b-9c80-c6f50b5d3353", "confirm": True}
        assert client.post("/demo/reset", json=body).status_code == 403
        for _ in range(2):
            response = client.post("/demo/reset", json=body, headers={"Origin": "https://demo.test"})
            assert response.status_code == 202, response.text
    assert len(launches) == 1
    app.discard_parked_egress_allocations.assert_awaited_once_with("dinner")


def test_reset_endpoint_refuses_unsettled_browser_cleanup(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from operations.demo_reset import DemoReset

    app = fixture_app()
    app.discard_parked_egress_allocations = AsyncMock(return_value=False)
    launches = []

    async def auth(request):
        return None

    server = FastAPI()
    DemoReset(tmp_path, app, auth, "https://demo.test", launcher=launches.append).install(server)
    with TestClient(server) as client:
        response = client.post(
            "/demo/reset", headers={"Origin": "https://demo.test"},
            json={"request_id": "ba36f6c7-5753-421b-9c80-c6f50b5d3353", "confirm": True},
        )
        assert response.status_code == 409
    assert launches == []
    assert not (tmp_path / "reset-job.json").exists()
