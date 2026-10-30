import pytest
from pydantic import ValidationError

from kineticproof_api.physics import MeasurementRequest, measure_trace
from kineticproof_api.planning import (
    NextTrialSuggestion,
    PlanningRequest,
    plan_next_trial,
)
from kineticproof_api.tracking import Provenance, TrackFrame, TrackResult


def trace(values):
    frames = [
        TrackFrame(i, i * 0.1, None, value, 0.0, [] if value is not None else ["tracking_failed"])
        for i, value in enumerate(values)
    ]
    return TrackResult(
        "1", None, "video", "opencv", "csrt", "v1", "run", "partial", frames, [],
        Provenance("hash", "none", 0.1, len(values), "cv"),
    )


def request(**overrides):
    values = {
        "context": {
            "question": "How does length affect period?",
            "hypothesis": "A longer pendulum has a longer period.",
            "focus_variable": "length_m",
            "length_m": 0.5,
            "release_angle_degrees": 8,
            "background_condition": "clear",
            "camera_fixed": True,
        },
        "motion_axis": {"x": 1, "y": 0},
    }
    values.update(overrides)
    return PlanningRequest.model_validate(values)


def test_planning_request_validates_context_and_rejects_client_measurements():
    with pytest.raises(ValidationError):
        request(context={"question": "?"})
    with pytest.raises(ValidationError):
        request(measured_period_seconds=1.2)
    with pytest.raises(ValidationError):
        request(context={
            "question": "?", "hypothesis": "?", "focus_variable": "length_m", "length_m": 0,
            "release_angle_degrees": 8, "background_condition": "clear", "camera_fixed": True,
        })
    invalid_focus = request().context.model_dump()
    invalid_focus["focus_variable"] = "release_angle_degrees"
    with pytest.raises(ValidationError):
        request(context=invalid_focus)


def test_planning_measures_trace_with_existing_measurement_request(monkeypatch):
    source_trace = trace([0, 1, 0])
    expected = measure_trace(source_trace, MeasurementRequest(motion_axis={"x": 1, "y": 0}))
    captured = {}

    def measure(received_trace, measurement_request):
        captured["trace"] = received_trace
        captured["request"] = measurement_request
        return expected

    monkeypatch.setattr("kineticproof_api.planning.measure_trace", measure)
    response = plan_next_trial(source_trace, request())

    assert captured["trace"] is source_trace
    assert isinstance(captured["request"], MeasurementRequest)
    assert captured["request"].length_m is None
    assert captured["request"].gravity_m_s2 is None
    assert response.measurement == expected


def test_insufficient_trace_suggests_a_longer_recording():
    response = plan_next_trial(trace([0, 1, 0]), request())

    assert response.provider_name == "template"
    assert response.measurement.status == "insufficient_data"
    assert response.suggestion.action == "record_more_cycles"
    assert response.suggestion.variable_to_change == "recording_duration"
    assert response.measurement.measured_period_seconds is None


def test_sufficient_trace_suggests_only_a_length_change():
    values = [0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 3, 1, 0]
    response = plan_next_trial(trace(values), request(gravity_m_s2=9.81))

    assert response.measurement.status == "succeeded"
    assert response.suggestion.action == "vary_length"
    assert response.suggestion.variable_to_change == "length_m"
    assert response.suggestion.held_constant == [
        "release_angle_degrees", "camera_position", "background_condition",
    ]
    assert response.measurement.theoretical_period_seconds is not None
    assert "predicted_period_seconds" not in response.suggestion.model_dump()


def test_sufficient_trace_suggests_declared_background_change():
    values = [0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 3, 1, 0]
    context = request().context.model_dump()
    context["focus_variable"] = "background_condition"
    response = plan_next_trial(trace(values), request(context=context))

    assert response.suggestion.action == "vary_background_condition"
    assert response.suggestion.focus_variable == "background_condition"
    assert response.suggestion.variable_to_change == "background_condition"
    assert response.suggestion.held_constant == [
        "length_m", "release_angle_degrees", "camera_position",
    ]


def test_suggestion_rejects_a_change_that_conflicts_with_focus_or_constants():
    base = {
        "focus_variable": "background_condition",
        "held_constant": ["length_m", "release_angle_degrees", "camera_position"],
        "rationale": "Try one background condition.",
        "limitation": "This is a suggestion.",
    }
    with pytest.raises(ValidationError):
        NextTrialSuggestion(
            **base, action="vary_length", variable_to_change="length_m"
        )
    with pytest.raises(ValidationError):
        NextTrialSuggestion(
            **{**base, "held_constant": ["length_m", "release_angle_degrees"]},
            action="vary_background_condition",
            variable_to_change="background_condition",
        )

