"""Pendulum next-trial planning kept separate from measured evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictBool, model_validator

from kineticproof_api.physics import (
    MeasurementRequest,
    MeasurementResult,
    MotionAxis,
    ReferenceEvent,
    measure_trace,
)
from kineticproof_api.tracking import TrackResult


class PendulumContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    hypothesis: str = Field(min_length=1, max_length=500)
    focus_variable: Literal["length_m", "background_condition"]
    length_m: FiniteFloat = Field(gt=0)
    release_angle_degrees: FiniteFloat = Field(gt=0, lt=90)
    background_condition: Literal["clear", "cluttered_static", "moving_background_or_occlusion"]
    camera_fixed: StrictBool


class PlanningRequest(BaseModel):
    """Experiment context and raw manual evidence; measurements are server-derived."""

    model_config = ConfigDict(extra="forbid")

    context: PendulumContext
    motion_axis: MotionAxis
    reference_events: list[ReferenceEvent] = Field(default_factory=list)
    gravity_m_s2: FiniteFloat | None = Field(default=None, gt=0)


class NextTrialSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_variable: Literal["length_m", "background_condition"]
    action: Literal["record_more_cycles", "vary_length", "vary_background_condition"]
    variable_to_change: Literal["recording_duration", "length_m", "background_condition"]
    held_constant: list[Literal[
        "length_m", "release_angle_degrees", "camera_position", "background_condition"
    ]]
    rationale: str = Field(min_length=1)
    limitation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_single_change(self):
        expected_variable = {
            "record_more_cycles": "recording_duration",
            "vary_length": "length_m",
            "vary_background_condition": "background_condition",
        }[self.action]
        if self.variable_to_change != expected_variable:
            raise ValueError("suggestion must describe exactly one action variable")
        if self.action != "record_more_cycles" and self.variable_to_change != self.focus_variable:
            raise ValueError("suggested change must match focus_variable")

        experiment_variables = {
            "length_m", "release_angle_degrees", "camera_position", "background_condition"
        }
        expected_held_constant = (
            experiment_variables
            if self.action == "record_more_cycles"
            else experiment_variables - {self.focus_variable}
        )
        if (len(self.held_constant) != len(set(self.held_constant))
                or set(self.held_constant) != expected_held_constant):
            raise ValueError("hold constant every experiment variable except the one being changed")
        return self


class PlanningResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: Literal["template", "meta_muse"]
    measurement: MeasurementResult
    suggestion: NextTrialSuggestion


def _template_suggestion(
    measurement: MeasurementResult, focus_variable: Literal["length_m", "background_condition"]
) -> NextTrialSuggestion:
    if measurement.status == "insufficient_data":
        return NextTrialSuggestion(
            focus_variable=focus_variable,
            action="record_more_cycles",
            variable_to_change="recording_duration",
            held_constant=[
                "length_m", "release_angle_degrees", "camera_position", "background_condition"
            ],
            rationale=(
                "Record a longer clip with the full swing visible so the trace can contain "
                "at least two complete cycles."
            ),
            limitation="The current trace does not support a measured period.",
        )
    if focus_variable == "length_m":
        return NextTrialSuggestion(
            focus_variable=focus_variable,
            action="vary_length",
            variable_to_change="length_m",
            held_constant=["release_angle_degrees", "camera_position", "background_condition"],
            rationale=(
                "Change pendulum length for the next trial and keep the release angle, "
                "camera position, and background condition the same."
            ),
            limitation="This is a controlled-trial suggestion, not a predicted period.",
        )
    return NextTrialSuggestion(
        focus_variable=focus_variable,
        action="vary_background_condition",
        variable_to_change="background_condition",
        held_constant=["length_m", "release_angle_degrees", "camera_position"],
        rationale=(
            "Change the background condition for the next trial and keep pendulum length, "
            "release angle, and camera position the same."
        ),
        limitation="This is a controlled-trial suggestion, not a predicted period.",
    )


def plan_next_trial(trace: TrackResult, request: PlanningRequest) -> PlanningResponse:
    """Calculate fresh evidence, then attach an offline deterministic suggestion."""
    measurement_request = MeasurementRequest(
        motion_axis=request.motion_axis,
        reference_events=request.reference_events,
        length_m=request.context.length_m if request.gravity_m_s2 is not None else None,
        gravity_m_s2=request.gravity_m_s2,
    )
    measurement = measure_trace(trace, measurement_request)
    return PlanningResponse(
        provider_name="template",
        measurement=measurement,
        suggestion=_template_suggestion(measurement, request.context.focus_variable),
    )
