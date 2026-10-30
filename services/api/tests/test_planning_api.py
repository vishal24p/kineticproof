import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from kineticproof_api import main
from kineticproof_api.tracking import (
    Provenance, TrackFrame, TrackResult, TrackingRun, VideoMetadata,
)


@pytest.fixture
def planning_client():
    with TestClient(main.app) as client:
        frames = [
            TrackFrame(index, index * 0.1, None, value, 0.0, [])
            for index, value in enumerate(
                [0, 1, 3, 1, 0, -1, 0, 2, 5, 2, 0, -1, 0, 1, 4, 1, 0]
            )
        ]
        trace = TrackResult(
            "1.0.0", None, "tracked", "opencv", "csrt", "test", "run",
            "partial", frames, [], Provenance("hash", "none", 0.1, len(frames), "opencv"),
        )
        main.app.state.observations["tracked"] = main.Observation(
            Path("unused.mp4"), VideoMetadata(1.6, 64, 48, len(frames), 10.0),
            TrackingRun(trace, Path("unused-overlay.mp4")),
        )
        main.app.state.observations["pending"] = main.Observation(
            Path("unused.mp4"), VideoMetadata(1.6, 64, 48, len(frames), 10.0),
        )
        yield client


def payload():
    return {
        "context": {
            "question": "How does length affect period?",
            "hypothesis": "A longer pendulum has a longer period.",
            "focus_variable": "length_m", "length_m": 0.5,
            "release_angle_degrees": 8, "background_condition": "clear",
            "camera_fixed": True,
        },
        "motion_axis": {"x": 1, "y": 0},
    }


def fake_muse(monkeypatch, **response_overrides):
    response = {
        "status": "completed",
        "output_text": json.dumps({
            "focus_variable": "length_m", "action": "vary_length",
            "variable_to_change": "length_m",
            "held_constant": ["release_angle_degrees", "camera_position", "background_condition"],
            "rationale": "Change length while holding the other variables constant.",
            "limitation": "This suggestion is not a measured conclusion.",
        }),
    }
    response.update(response_overrides)
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(**response))),
        close=AsyncMock(),
    )
    constructor = Mock(return_value=client)
    monkeypatch.setattr(main, "AsyncOpenAI", constructor)
    monkeypatch.setattr(main, "getenv", Mock(return_value="fake-test-key"))
    return client, constructor


@pytest.mark.parametrize("query", ["", "?provider=template"])
def test_template_never_reads_key_or_constructs_client(planning_client, monkeypatch, query):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    read_key = Mock(side_effect=AssertionError("template must not read credentials"))
    constructor = Mock(side_effect=AssertionError("template must not construct a client"))
    monkeypatch.setattr(main, "getenv", read_key)
    monkeypatch.setattr(main, "AsyncOpenAI", constructor)

    response = planning_client.post(f"/api/observations/tracked/next-trial{query}", json=payload())

    assert response.status_code == 200
    assert response.json()["provider_name"] == "template"
    assert response.json()["suggestion"]["action"] == "vary_length"
    measured = planning_client.post(
        "/api/observations/tracked/measure", json={"motion_axis": {"x": 1, "y": 0}},
    )
    assert response.json()["measurement"] == measured.json()
    read_key.assert_not_called()
    constructor.assert_not_called()


def test_muse_dispatches_and_closes_client(planning_client, monkeypatch):
    client, constructor = fake_muse(monkeypatch)
    response = planning_client.post(
        "/api/observations/tracked/next-trial?provider=meta_muse", json=payload(),
    )

    assert response.status_code == 200
    assert response.json()["provider_name"] == "meta_muse"
    assert response.json()["measurement"]["status"] == "succeeded"
    main.getenv.assert_called_once_with("MODEL_API_KEY")
    constructor.assert_called_once_with(
        base_url="https://api.meta.ai/v1", api_key="fake-test-key", max_retries=0,
    )
    client.responses.create.assert_awaited_once()
    client.close.assert_awaited_once()


def test_muse_missing_key_short_circuits_client(planning_client, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    constructor = Mock(side_effect=AssertionError("missing key must prevent construction"))
    monkeypatch.setattr(main, "AsyncOpenAI", constructor)

    response = planning_client.post(
        "/api/observations/tracked/next-trial?provider=meta_muse", json=payload(),
    )

    assert response.status_code == 503
    assert "MODEL_API_KEY" in response.json()["detail"]
    constructor.assert_not_called()


@pytest.mark.parametrize("failure", ["network", "schema", "incomplete"])
def test_muse_errors_return_502_without_fallback_and_close(planning_client, monkeypatch, failure):
    client, _ = fake_muse(monkeypatch, **{
        "schema": {"output_text": "{}"},
        "incomplete": {"status": "incomplete"},
    }.get(failure, {}))
    if failure == "network":
        client.responses.create.side_effect = RuntimeError("provider unavailable")
    fallback = Mock(side_effect=AssertionError("route must not fall back to template"))
    monkeypatch.setattr(main, "plan_next_trial", fallback)

    response = planning_client.post(
        "/api/observations/tracked/next-trial?provider=meta_muse", json=payload(),
    )

    assert response.status_code == 502
    fallback.assert_not_called()
    client.close.assert_awaited_once()


@pytest.mark.parametrize("provider", ["template", "meta_muse"])
def test_invalid_context_returns_422_before_client(planning_client, monkeypatch, provider):
    _, constructor = fake_muse(monkeypatch)
    body = payload()
    body["context"]["length_m"] = 0
    response = planning_client.post(
        f"/api/observations/tracked/next-trial?provider={provider}", json=body,
    )
    assert response.status_code == 422
    constructor.assert_not_called()


@pytest.mark.parametrize("provider", ["template", "meta_muse"])
def test_local_measurement_error_returns_422(planning_client, monkeypatch, provider):
    client, _ = fake_muse(monkeypatch)
    body = payload()
    body["reference_events"] = [{
        "event_type": "same_direction", "timestamp_seconds": 1,
        "evidence_frame_index": 99, "uncertainty_seconds": 0,
    }]
    response = planning_client.post(
        f"/api/observations/tracked/next-trial?provider={provider}", json=body,
    )
    assert response.status_code == 422
    client.responses.create.assert_not_awaited()
    if provider == "meta_muse":
        client.close.assert_awaited_once()


@pytest.mark.parametrize("provider", ["template", "meta_muse"])
@pytest.mark.parametrize("observation_id,status", [("unknown", 404), ("pending", 409)])
def test_completed_observation_required(planning_client, monkeypatch, provider, observation_id, status):
    _, constructor = fake_muse(monkeypatch)
    response = planning_client.post(
        f"/api/observations/{observation_id}/next-trial?provider={provider}", json=payload(),
    )
    assert response.status_code == status
    main.getenv.assert_not_called()
    constructor.assert_not_called()


def test_unknown_provider_returns_422(planning_client, monkeypatch):
    _, constructor = fake_muse(monkeypatch)
    response = planning_client.post(
        "/api/observations/tracked/next-trial?provider=other", json=payload(),
    )
    assert response.status_code == 422
    constructor.assert_not_called()
