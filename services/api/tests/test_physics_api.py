import csv
from io import StringIO
from math import isfinite
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kineticproof_api import main
from kineticproof_api.tracking import (
    Provenance, TrackFrame, TrackResult, TrackingRun, VideoMetadata,
)


def make_trace(values):
    frames = [TrackFrame(index, index * 0.1, None, value, 0.0,
                         [] if value is not None else ["tracking_failed"])
              for index, value in enumerate(values)]
    return TrackResult("1.0.0", None, "observation", "opencv", "csrt", "test", "run",
                       "succeeded", frames, [], Provenance("hash", "none", 0.1,
                                                               len(frames), "opencv"))


@pytest.fixture
def measurement_client():
    with TestClient(main.app) as client:
        yield client


def add_observation(client, observation_id, values=None):
    observation = main.Observation(
        Path("unused.mp4"), VideoMetadata(1.0, 64, 48, 10, 10.0)
    )
    if values is not None:
        observation.tracking_run = TrackingRun(make_trace(values), Path("unused-overlay.mp4"))
    main.app.state.observations[observation_id] = observation


def payload():
    return {"motion_axis": {"x": 1, "y": 0}}


def test_measure_unknown_observation_returns_404(measurement_client):
    response = measurement_client.post("/api/observations/unknown/measure", json=payload())
    assert response.status_code == 404


def test_measure_without_completed_trace_returns_409(measurement_client):
    add_observation(measurement_client, "pending")
    response = measurement_client.post("/api/observations/pending/measure", json=payload())
    assert response.status_code == 409


def test_measure_json_and_csv_share_cycle_periods(measurement_client):
    values = [0, 1, 3, 1, 0, -1, 0, 2, 5, 2, 0, -1, 0, 1, 4, 1, 0]
    add_observation(measurement_client, "measured", values)
    url = "/api/observations/measured/measure"

    default = measurement_client.post(url, json=payload())
    explicit = measurement_client.post(f"{url}?format=json", json=payload())
    csv_response = measurement_client.post(f"{url}?format=csv", json=payload())

    assert default.status_code == explicit.status_code == csv_response.status_code == 200
    assert default.json() == explicit.json()
    assert default.json()["status"] == "succeeded"
    assert default.json()["measurement_config"] == {
        "filter_name": "median", "filter_window_samples": 3,
        "detector": "local_maximum", "prominence_method": "topographic",
        "prominence_fraction": 0.1,
    }
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert csv_response.headers["x-measurement-status"] == "succeeded"
    rows = list(csv.DictReader(StringIO(csv_response.text)))
    assert [float(row["period_seconds"]) for row in rows] == pytest.approx(
        [cycle["period_seconds"] for cycle in default.json()["cycles"]]
    )


def test_insufficient_measurement_returns_status_and_header_only_csv(measurement_client):
    add_observation(measurement_client, "short", [0, 1, 0])
    url = "/api/observations/short/measure"

    result = measurement_client.post(url, json=payload())
    csv_response = measurement_client.post(f"{url}?format=csv", json=payload())

    assert result.status_code == 200
    assert result.json()["status"] == "insufficient_data"
    assert result.json()["measured_period_seconds"] is None
    assert csv_response.status_code == 200
    assert csv_response.headers["x-measurement-status"] == "insufficient_data"
    assert len(csv_response.text.splitlines()) == 1


def test_successful_measurement_reports_missing_data_warning(measurement_client):
    segment = [0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0]
    add_observation(measurement_client, "gapped", segment + [None] + segment)
    response = measurement_client.post("/api/observations/gapped/measure", json=payload())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    assert result["gap_ranges"] == [{"start_frame_index": 13, "end_frame_index": 13}]
    assert "Missing or invalid tracked frames split the trace; cycles do not cross gaps." in result["warnings"]


@pytest.mark.parametrize("response_format", ["json", "csv"])
@pytest.mark.parametrize("length,gravity,expected", [
    (1e308, 1e-306, 6.283185307179586e307),
    (1e-308, 1e308, 6.283185307179586e-308),
])
def test_theory_avoids_intermediate_overflow_and_underflow(
    measurement_client, response_format, length, gravity, expected,
):
    values = [0, 1, 3, 1, 0, -1, 0, 2, 5, 2, 0, -1, 0, 1, 4, 1, 0]
    add_observation(measurement_client, "theory", values)
    response = measurement_client.post(
        f"/api/observations/theory/measure?format={response_format}",
        json={**payload(), "length_m": length, "gravity_m_s2": gravity},
    )
    assert response.status_code == 200
    if response_format == "json":
        period = response.json()["theoretical_period_seconds"]
    else:
        period = float(next(csv.DictReader(StringIO(response.text)))["theoretical_period_seconds"])
    assert isfinite(period) and period > 0
    assert period == pytest.approx(expected, rel=1e-12, abs=0)


@pytest.mark.parametrize("response_format", ["json", "csv"])
def test_unrepresentable_theory_returns_422(measurement_client, response_format):
    add_observation(measurement_client, "overflow", [0, 1, 0])
    response = measurement_client.post(
        f"/api/observations/overflow/measure?format={response_format}",
        json={**payload(), "length_m": 1e308, "gravity_m_s2": 1e-308},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "theoretical period must be finite and positive"}


def test_one_cycle_insufficient_measurement_csv_has_no_rows(measurement_client):
    add_observation(measurement_client, "one-cycle", [0, 1, 3, 1, 0, -1, 0, 2, 5, 2, 0])
    url = "/api/observations/one-cycle/measure"

    result = measurement_client.post(url, json=payload())
    csv_response = measurement_client.post(f"{url}?format=csv", json=payload())

    assert result.json()["status"] == "insufficient_data"
    assert len(result.json()["cycles"]) == 1
    assert csv_response.headers["x-measurement-status"] == "insufficient_data"
    assert len(csv_response.text.splitlines()) == 1


@pytest.mark.parametrize("request_body", [
    {"motion_axis": {"x": 0, "y": 0}},
    {"motion_axis": {"x": 1, "y": 0}, "length_m": 1},
    {"motion_axis": {"x": 1, "y": 0}, "reference_events": [
        {"event_type": "same_direction", "timestamp_seconds": 1,
         "evidence_frame_index": 99, "uncertainty_seconds": 0}
    ]},
])
def test_invalid_measurement_requests_return_422(measurement_client, request_body):
    add_observation(measurement_client, "invalid", [0, 1, 0])
    response = measurement_client.post(
        "/api/observations/invalid/measure", json=request_body
    )
    assert response.status_code == 422


def test_unknown_format_returns_422(measurement_client):
    add_observation(measurement_client, "format", [0, 1, 0])
    response = measurement_client.post(
        "/api/observations/format/measure?format=xml", json=payload()
    )
    assert response.status_code == 422
