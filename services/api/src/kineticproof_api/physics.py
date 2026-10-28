"""Deterministic period measurements from tracked center positions."""

import csv
from io import StringIO
from math import hypot, isfinite, pi, sqrt
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat, StrictInt, model_validator

from kineticproof_api.tracking import TrackResult


class MotionAxis(BaseModel):
    x: FiniteFloat
    y: FiniteFloat

    @model_validator(mode="after")
    def normalize(self):
        norm = hypot(self.x, self.y)
        if not isfinite(norm) or norm == 0:
            raise ValueError("motion_axis must be finite and nonzero")
        self.x, self.y = self.x / norm, self.y / norm
        return self


class ReferenceEvent(BaseModel):
    event_type: Literal["leftmost", "rightmost", "same_direction"]
    timestamp_seconds: FiniteFloat
    evidence_frame_index: StrictInt = Field(ge=0)
    uncertainty_seconds: FiniteFloat = Field(ge=0)
    notes: str | None = None


class MeasurementRequest(BaseModel):
    motion_axis: MotionAxis
    reference_events: list[ReferenceEvent] = Field(default_factory=list)
    length_m: FiniteFloat | None = None
    gravity_m_s2: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_inputs(self):
        if (self.length_m is None) != (self.gravity_m_s2 is None):
            raise ValueError("length_m and gravity_m_s2 must be supplied together")
        if self.length_m is not None and (self.length_m <= 0 or self.gravity_m_s2 <= 0):
            raise ValueError("length_m and gravity_m_s2 must be positive")
        if any(a.timestamp_seconds >= b.timestamp_seconds for a, b in
               zip(self.reference_events, self.reference_events[1:])):
            raise ValueError("reference events must be in increasing timestamp order")
        return self


class TurningPoint(BaseModel):
    frame_index: int
    timestamp_seconds: float
    position_px: float
    prominence_px: float


class CyclePeriod(BaseModel):
    start_frame_index: int
    end_frame_index: int
    start_timestamp_seconds: float
    end_timestamp_seconds: float
    period_seconds: float
    prominence_px: float


class ManualReferenceInterval(BaseModel):
    event_type: str
    start_timestamp_seconds: float
    end_timestamp_seconds: float
    period_seconds: float
    start_uncertainty_seconds: float
    end_uncertainty_seconds: float


class FrameRange(BaseModel):
    start_frame_index: int
    end_frame_index: int


class SegmentProminenceThreshold(BaseModel):
    start_frame_index: int
    end_frame_index: int
    threshold_px: float


class MeasurementProvenance(BaseModel):
    source_video_sha256: str
    provider_name: str
    model_name: str
    model_version: str
    run_config_id: str


class MeasurementResult(BaseModel):
    schema_version: str
    status: Literal["succeeded", "insufficient_data"]
    motion_axis: MotionAxis
    valid_frame_count: int
    total_frame_count: int
    valid_frame_fraction: float
    turning_points: list[TurningPoint]
    rejected_candidate_count: int
    prominence_threshold_px: float = Field(description="Maximum of the per-segment thresholds below.")
    segment_prominence_thresholds: list[SegmentProminenceThreshold]
    cycles: list[CyclePeriod]
    measured_period_seconds: float | None
    cycle_mad_seconds: float | None
    source_timing_resolution_seconds: float | None
    gap_ranges: list[FrameRange]
    manual_reference_intervals: list[ManualReferenceInterval]
    manual_reference_period_seconds: float | None
    theoretical_period_seconds: float | None
    warnings: list[str]
    provenance: MeasurementProvenance


def _prominence(samples, peak):
    height = samples[peak][2]
    left_min = min(item[2] for item in samples[:peak])
    right_min = min(item[2] for item in samples[peak + 1:])
    return height - max(left_min, right_min)


def _manual_intervals(events):
    previous = {}
    intervals = []
    for event in events:
        if event.event_type in previous:
            start = previous[event.event_type]
            intervals.append(ManualReferenceInterval(
                event_type=event.event_type,
                start_timestamp_seconds=start.timestamp_seconds,
                end_timestamp_seconds=event.timestamp_seconds,
                period_seconds=event.timestamp_seconds - start.timestamp_seconds,
                start_uncertainty_seconds=start.uncertainty_seconds,
                end_uncertainty_seconds=event.uncertainty_seconds))
        previous[event.event_type] = event
    return intervals


def measure_trace(trace: TrackResult, request: MeasurementRequest) -> MeasurementResult:
    frames = trace.frames
    frame_indexes = {frame.frame_index for frame in frames}
    if any(event.evidence_frame_index not in frame_indexes for event in request.reference_events):
        raise ValueError("reference event evidence_frame_index must exist in the trace")
    segments, segment = [], []
    gaps = []
    gap_start = None
    valid_count = 0
    for frame in frames:
        valid = (frame.center_x_px is not None and frame.center_y_px is not None
                 and isfinite(frame.center_x_px) and isfinite(frame.center_y_px)
                 and "tracking_failed" not in frame.quality_flags)
        if not valid:
            if segment:
                segments.append(segment)
                segment = []
            if gap_start is None:
                gap_start = frame.frame_index
            continue
        if gap_start is not None:
            gaps.append(FrameRange(start_frame_index=gap_start, end_frame_index=frame.frame_index - 1))
            gap_start = None
        valid_count += 1
        projected = frame.center_x_px * request.motion_axis.x + frame.center_y_px * request.motion_axis.y
        segment.append((frame.frame_index, frame.timestamp_seconds, projected))
    if segment:
        segments.append(segment)
    if gap_start is not None:
        gaps.append(FrameRange(start_frame_index=gap_start, end_frame_index=frames[-1].frame_index))

    turns, cycles, rejected, thresholds = [], [], 0, []
    for raw in segments:
        samples = raw[:]
        for i in range(1, len(raw) - 1):
            samples[i] = (raw[i][0], raw[i][1], median([raw[i-1][2], raw[i][2], raw[i+1][2]]))
        span = max(p[2] for p in samples) - min(p[2] for p in samples)
        threshold = .1 * span
        thresholds.append(SegmentProminenceThreshold(
            start_frame_index=samples[0][0], end_frame_index=samples[-1][0], threshold_px=threshold))
        candidates = []
        i = 1
        while i < len(samples) - 1:
            end = i
            while end + 1 < len(samples) and samples[end + 1][2] == samples[i][2]:
                end += 1
            if (samples[i][2] > samples[i - 1][2]
                    and end < len(samples) - 1 and samples[end][2] > samples[end + 1][2]):
                candidates.append((i + end) // 2)
            i = end + 1
        accepted = []
        for i in candidates:
            prominence = _prominence(samples, i)
            if prominence < threshold:
                rejected += 1
                continue
            accepted.append((i, prominence))
            frame_index, timestamp, position = samples[i]
            turns.append(TurningPoint(frame_index=frame_index, timestamp_seconds=timestamp,
                                      position_px=position, prominence_px=prominence))
        for (a, pa), (b, pb) in zip(accepted, accepted[1:]):
            first, last = samples[a], samples[b]
            cycles.append(CyclePeriod(start_frame_index=first[0], end_frame_index=last[0],
                start_timestamp_seconds=first[1], end_timestamp_seconds=last[1],
                period_seconds=last[1]-first[1], prominence_px=min(pa, pb)))

    periods = [cycle.period_seconds for cycle in cycles]
    measured = median(periods) if len(periods) >= 2 else None
    mad = median([abs(p - measured) for p in periods]) if measured is not None else None
    time_steps = [b.timestamp_seconds - a.timestamp_seconds for a, b in zip(frames, frames[1:])
                  if b.timestamp_seconds > a.timestamp_seconds]
    timing = median(time_steps) if time_steps else None
    manual = _manual_intervals(request.reference_events)
    manual_period = median([item.period_seconds for item in manual]) if manual else None
    warnings = []
    if len(cycles) < 2:
        warnings.append("At least two complete cycles are required to report a measured period.")
    if rejected:
        warnings.append("Some candidate turning points did not meet the prominence threshold.")
    return MeasurementResult(schema_version="1.0.0",
        status="succeeded" if measured is not None else "insufficient_data",
        motion_axis=request.motion_axis, valid_frame_count=valid_count,
        total_frame_count=len(frames), valid_frame_fraction=valid_count / len(frames) if frames else 0,
        turning_points=turns, rejected_candidate_count=rejected,
        prominence_threshold_px=max((item.threshold_px for item in thresholds), default=0),
        segment_prominence_thresholds=thresholds, cycles=cycles,
        measured_period_seconds=measured, cycle_mad_seconds=mad,
        source_timing_resolution_seconds=timing, gap_ranges=gaps,
        manual_reference_intervals=manual, manual_reference_period_seconds=manual_period,
        theoretical_period_seconds=(2*pi*sqrt(request.length_m/request.gravity_m_s2)
            if request.length_m is not None else None), warnings=warnings,
        provenance=MeasurementProvenance(source_video_sha256=trace.provenance.source_video_sha256,
            provider_name=trace.provider_name, model_name=trace.model_name,
            model_version=trace.model_version, run_config_id=trace.run_config_id))


CSV_COLUMNS = ["cycle_index", "start_frame_index", "end_frame_index", "start_timestamp_seconds",
    "end_timestamp_seconds", "period_seconds", "peak_prominence_px", "measured_period_seconds",
    "cycle_period_mad_seconds", "source_timing_resolution_seconds", "manual_reference_period_seconds",
    "theoretical_period_seconds", "source_video_sha256"]


def measurement_csv(result: MeasurementResult) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    if result.status == "succeeded":
        for index, cycle in enumerate(result.cycles, 1):
            writer.writerow(dict(zip(CSV_COLUMNS, [index, cycle.start_frame_index, cycle.end_frame_index,
                cycle.start_timestamp_seconds, cycle.end_timestamp_seconds, cycle.period_seconds,
                cycle.prominence_px, result.measured_period_seconds, result.cycle_mad_seconds,
                result.source_timing_resolution_seconds, result.manual_reference_period_seconds,
                result.theoretical_period_seconds, result.provenance.source_video_sha256])))
    return output.getvalue()
