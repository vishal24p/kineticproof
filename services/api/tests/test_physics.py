from math import sqrt

import pytest
from pydantic import ValidationError

from kineticproof_api.physics import MeasurementRequest, measure_trace, measurement_csv
from kineticproof_api.tracking import Provenance, TrackFrame, TrackResult


def trace(values, times=None):
    times = times or [i * .1 for i in range(len(values))]
    frames = [TrackFrame(i, times[i], None,
                         None if value is None else value,
                         None if value is None else 0.0,
                         [] if value is not None else ["tracking_failed"])
              for i, value in enumerate(values)]
    return TrackResult("1", None, "video", "opencv", "csrt", "v1", "run",
                       "partial", frames, [], Provenance("hash", "none", .1, len(values), "cv"))


def test_axis_must_be_finite_nonzero_and_is_normalized():
    with pytest.raises(ValidationError):
        MeasurementRequest(motion_axis={"x": 0, "y": 0})
    request = MeasurementRequest(motion_axis={"x": 3, "y": 4})
    assert request.motion_axis.x == pytest.approx(.6)
    assert request.motion_axis.y == pytest.approx(.8)


def test_periods_use_irregular_source_times_and_do_not_cross_gaps():
    values = [0, 2, 0, -2, 0, 2, 0, None, 2, 0, -2, 0, 2, 0]
    times = [0, .07, .19, .31, .5, .62, .8, .9, 1.01, 1.13, 1.3, 1.49, 1.7, 1.85]
    result = measure_trace(trace(values, times), MeasurementRequest(motion_axis={"x": 1, "y": 0}))
    assert result.gap_ranges[0].start_frame_index == 7
    assert result.gap_ranges[0].end_frame_index == 7
    valid_segments = [(0, 6), (8, 13)]
    assert all(any(start <= cycle.start_frame_index <= cycle.end_frame_index <= end
                   for start, end in valid_segments) for cycle in result.cycles)
    assert all(c.period_seconds != pytest.approx(times[8] - times[5]) for c in result.cycles)
    assert result.source_timing_resolution_seconds == pytest.approx(.12)


def test_prominence_thresholds_are_reported_for_each_amplitude_segment():
    values = [0, 1, 4, 1, 0, -1, 0, 1, 4, 1, 0, None,
              0, 10, 40, 10, 0, -10, 0, 10, 40, 10, 0]
    result = measure_trace(trace(values), MeasurementRequest(motion_axis={"x": 1, "y": 0}))
    thresholds = result.segment_prominence_thresholds
    assert [(t.start_frame_index, t.end_frame_index) for t in thresholds] == [(0, 10), (12, 22)]
    assert [t.threshold_px for t in thresholds] == pytest.approx([.1, 1])
    assert result.prominence_threshold_px == max(t.threshold_px for t in thresholds)


def test_turning_points_manual_reference_theory_and_csv():
    # Two accepted same-direction maxima, with irregular source timestamps.
    vals = [0, 1, 3, 1, 0, -1, 0, 2, 5, 2, 0, -1, 0, 1, 4, 1, 0]
    times = [i * .1 for i in range(len(vals))]
    times[8] = .83
    req = MeasurementRequest(motion_axis={"x": 1, "y": 0}, length_m=1,
        gravity_m_s2=9.81, reference_events=[
            {"event_type": "same_direction", "timestamp_seconds": 1, "evidence_frame_index": 0, "uncertainty_seconds": .02},
            {"event_type": "same_direction", "timestamp_seconds": 2.02, "evidence_frame_index": 1, "uncertainty_seconds": .03},
        ])
    result = measure_trace(trace(vals, times), req)
    assert result.status == "succeeded"
    assert result.measured_period_seconds == pytest.approx(.6)
    assert result.cycle_mad_seconds == pytest.approx(.03)
    assert result.manual_reference_period_seconds == pytest.approx(1.02)
    assert result.manual_reference_intervals[0].start_uncertainty_seconds == .02
    assert result.theoretical_period_seconds == pytest.approx(2 * 3.141592653589793 * sqrt(1 / 9.81))
    assert "cycle_index,start_frame_index,end_frame_index" in measurement_csv(result)


def test_insufficient_data_still_has_stable_csv_header():
    result = measure_trace(trace([0, 1, 0]), MeasurementRequest(motion_axis={"x": 1, "y": 0}))
    assert result.status == "insufficient_data"
    assert result.measured_period_seconds is None
    assert len(measurement_csv(result).splitlines()) == 1


def test_length_and_gravity_must_be_paired_and_positive():
    with pytest.raises(ValidationError):
        MeasurementRequest(motion_axis={"x": 1, "y": 0}, length_m=1)
    with pytest.raises(ValidationError):
        MeasurementRequest(motion_axis={"x": 1, "y": 0}, length_m=-1, gravity_m_s2=9.8)
