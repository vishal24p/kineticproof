import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from kineticproof_api.physics import MeasurementRequest, measure_trace
from kineticproof_api.planning import (
    NextTrialSuggestion,
    MusePlanningError,
    PlanningRequest,
    plan_next_trial,
    plan_next_trial_muse,
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


def muse_client(suggestion, *, status="completed", error=None):
    create = AsyncMock(
        return_value=SimpleNamespace(status=status, output_text=json.dumps(suggestion)),
        side_effect=error,
    )
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def test_muse_request_is_minimized_strict_and_keeps_local_measurement(monkeypatch):
    source_trace = trace([0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 3, 1, 0])
    planning_request = request(gravity_m_s2=9.81)
    local = plan_next_trial(source_trace, planning_request)
    before = local.measurement.model_dump()
    source_before = repr(source_trace)
    calls = []

    def measure(received_trace, measurement_request):
        calls.append((received_trace, measurement_request))
        return local.measurement

    monkeypatch.setattr("kineticproof_api.planning.measure_trace", measure)
    client = muse_client(local.suggestion.model_dump())
    result = asyncio.run(plan_next_trial_muse(source_trace, planning_request, client))

    assert result.provider_name == "meta_muse"
    assert result.measurement is local.measurement
    assert result.measurement.model_dump() == before
    assert repr(source_trace) == source_before
    assert len(calls) == 1
    assert calls[0][0] is source_trace
    client.responses.create.assert_awaited_once()
    sent = client.responses.create.call_args.kwargs
    assert set(sent) == {"model", "store", "instructions", "input", "text"}
    assert sent["model"] == "muse-spark-1.3"
    assert sent["store"] is False
    assert "Never supply measured values or numeric period predictions" in sent["instructions"]
    assert json.loads(sent["input"]) == {
        "context": planning_request.context.model_dump(mode="json"),
        "measurement": {
            "status": "succeeded",
            "measured_period_seconds": local.measurement.measured_period_seconds,
            "cycle_mad_seconds": local.measurement.cycle_mad_seconds,
            "valid_frame_fraction": 1.0,
            "warnings": local.measurement.warnings,
        },
    }
    schema = NextTrialSuggestion.model_json_schema()
    schema["properties"]["focus_variable"]["enum"] = ["length_m"]
    schema["properties"]["action"]["enum"] = ["vary_length"]
    schema["properties"]["variable_to_change"]["enum"] = ["length_m"]
    assert sent["text"] == {"format": {
        "type": "json_schema", "name": "next_trial_suggestion",
        "strict": True, "schema": schema,
    }}
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("focus", ["length_m", "background_condition"])
@pytest.mark.parametrize("sufficient", [False, True])
def test_muse_accepts_only_expected_action_for_focus_and_evidence(focus, sufficient):
    values = [0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 3, 1, 0] if sufficient else [0, 1, 0]
    context = request().context.model_dump()
    context["focus_variable"] = focus
    planning_request = request(context=context)
    local = plan_next_trial(trace(values), planning_request)
    client = muse_client(local.suggestion.model_dump())

    result = asyncio.run(plan_next_trial_muse(trace(values), planning_request, client))

    assert result.suggestion == local.suggestion
    assert result.measurement == local.measurement
    assert result.provider_name == "meta_muse"
    client.responses.create.assert_awaited_once()


@pytest.mark.parametrize("override", [
    {"measured_period_seconds": 123.0},
    {"predicted_period_seconds": 123.0},
    {"variable_to_change": "release_angle_degrees"},
    {"focus_variable": "background_condition"},
    {"held_constant": ["length_m"]},
    {"rationale": ""},
    {"rationale": 42},
    {"action": "vary_length", "variable_to_change": "length_m",
     "held_constant": ["release_angle_degrees", "camera_position", "background_condition"]},
])
def test_muse_rejects_invalid_suggestion_without_retry_or_fallback(override):
    source_trace = trace([0, 1, 0])
    suggestion = plan_next_trial(source_trace, request()).suggestion.model_dump()
    client = muse_client({**suggestion, **override})

    with pytest.raises(MusePlanningError) as caught:
        asyncio.run(plan_next_trial_muse(source_trace, request(), client))

    assert isinstance(caught.value.__cause__, ValueError)
    client.responses.create.assert_awaited_once()


def test_muse_rejects_recording_action_when_measurement_succeeds():
    source_trace = trace([0, 0, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 3, 1, 0])
    suggestion = plan_next_trial(trace([0, 1, 0]), request()).suggestion.model_dump()
    client = muse_client(suggestion)

    with pytest.raises(MusePlanningError):
        asyncio.run(plan_next_trial_muse(source_trace, request(), client))
    client.responses.create.assert_awaited_once()


@pytest.mark.parametrize("status,output", [
    ("incomplete", "{}"), ("failed", "{}"), ("completed", "invalid JSON"),
    ("completed", ""), ("completed", None),
])
def test_muse_rejects_incomplete_or_malformed_response(status, output):
    client = muse_client({})
    client.responses.create.return_value = SimpleNamespace(status=status, output_text=output)

    with pytest.raises(MusePlanningError):
        asyncio.run(plan_next_trial_muse(trace([0, 1, 0]), request(), client))
    client.responses.create.assert_awaited_once()


def test_muse_provider_failure_surfaces_without_retry_or_fallback():
    error = RuntimeError("provider unavailable")
    client = muse_client({}, error=error)

    with pytest.raises(MusePlanningError) as caught:
        asyncio.run(plan_next_trial_muse(trace([0, 1, 0]), request(), client))

    assert caught.value.__cause__ is error
    client.responses.create.assert_awaited_once()


@pytest.mark.parametrize("field", ["rationale", "limitation"])
@pytest.mark.parametrize("claim", [
    "The measured period is 123 seconds",
    "The measured period is one point two seconds.",
    "The next period is predicted to be 1.25 seconds.",
    "Expected frequency: TWO hertz.",
    "Estimated uncertainty is half a second.",
    "The measured period is 123 seconds after recording two complete cycles.",
    "The measured frequency is two cycles per second.",
    "Record two cycles per second.",
])
def test_muse_rejects_numeric_measurement_or_prediction_in_prose(field, claim):
    source_trace = trace([0, 1, 0])
    suggestion = plan_next_trial(source_trace, request()).suggestion.model_dump()
    client = muse_client({**suggestion, field: claim})

    with pytest.raises(MusePlanningError) as caught:
        asyncio.run(plan_next_trial_muse(source_trace, request(), client))

    assert "numeric measurements or predictions" in str(caught.value.__cause__)
    client.responses.create.assert_awaited_once()


@pytest.mark.parametrize("rationale", [
    "Record at least two complete cycles.",
    "Record two complete cycles to improve period estimation.",
])
def test_muse_allows_cycle_guidance_and_qualitative_limitations(rationale):
    source_trace = trace([0, 1, 0])
    suggestion = plan_next_trial(source_trace, request()).suggestion.model_dump()
    suggestion["rationale"] = rationale
    suggestion["limitation"] = "This is not a predicted period. Record 2 more cycles."
    client = muse_client(suggestion)

    result = asyncio.run(plan_next_trial_muse(source_trace, request(), client))

    assert result.suggestion.model_dump() == suggestion
    client.responses.create.assert_awaited_once()

