# Slice 2 — Physics and Evidence Design (Approved)

## Intent

Turn a completed local tracking trace into an inspectable pendulum period measurement. Keep perception, measured period, independent manual timing, and theoretical period separate so none is presented as ground truth for another.

## Goals

- Compute period from the tracked center positions and their source timestamps.
- Report valid frames, detected turning points, complete cycles, timing spread, missing-data warnings, and trace provenance.
- Accept a caller-supplied motion axis and optional independent manual events and theory inputs.
- Return a JSON measurement and an equivalent CSV evidence export through the local API.
- Keep calculations deterministic, testable, and independent of any AI model.

## Non-goals

- No web UI, experiment database, persistence beyond the API process, asynchronous jobs, new tracker, or deployment.
- No metric velocity or acceleration from pixel coordinates.
- No claim of accuracy on authentic footage until a consented clip is measured and checked against independent manual timing.
- No automatic gravity, length, camera calibration, or assumed manual reference.

## Approaches considered

| Concern | Options | Selected |
|---|---|---|
| Delivery | Python calculation only; or a complete local API flow with JSON and CSV | API flow now, reusing the existing in-memory observation and trace |
| Motion direction | Fixed image X; automatically infer the dominant axis; or require a 2D axis | Require an explicit 2D axis in the request so rotated clips do not silently use the wrong direction |
| Period detector | Same-direction turning points; velocity zero-crossings; or sinusoid fitting | Same-direction turning points with median aggregation, as selected by the user |
| Comparisons | Period alone; or independently supplied manual events and optional length/gravity | Include both comparison inputs now; label manual and theoretical values separately |

## Proposed API

- `POST /api/observations/{id}/measure?format=json|csv` consumes the observation's latest successful `TrackResult`; it does not decode the source video again. `json` is the default. Both formats use the same request and calculation, so every export matches the result from that request.
- Request fields: required `motion_axis` `{x,y}` in image coordinates; optional `reference_events[]` using the existing annotation shape (event type, source timestamp, evidence frame index, uncertainty, and note); optional `length_m` and `gravity_m_s2` supplied as a pair.
- Normalize a finite, nonzero motion axis before projection. Project valid centers onto it; axis sign does not affect period.
- Return a JSON result with measured period, per-cycle periods and extrema timestamps, cycle median and median absolute deviation (MAD), source-timing resolution, frame/cycle counts, gap ranges, warnings, optional manual reference period, optional theoretical period, explicit measurement configuration, and source/model provenance.
- `format=csv` returns one row per detected complete cycle with its start/end frame and timestamps, period, and the summary/reference/theory values. The JSON response is the full structured result; existing `/tracks` remains the frame-level trace.
- Do not cache measurement results in `Observation`. The user can save each response; rerunning a calculation cannot silently replace an earlier export. A failed tracking rerun still preserves the prior trace and overlay.

## Proposed calculation

1. Read centers and source timestamps from the latest `TrackResult`; null centers and failed frames remain gaps.
2. Split samples into contiguous valid segments. Do not interpolate across a gap or create a cycle across separate segments. Report a missing-data warning whenever gaps exist, including when enough cycles remain for success.
3. Apply a three-sample median filter within each segment to reduce isolated tracker jitter. Do not smooth across missing frames. Return explicit `measurement_config` with `filter_name: "median"`, `filter_window_samples: 3`, `detector: "local_maximum"`, `prominence_method: "topographic"`, and `prominence_fraction: 0.1`; tracking `provenance.run_config_id` remains separate.
4. Detect positive turning points as local maxima on the projected signal. Require topographic peak prominence of at least 10% of that contiguous segment's peak-to-peak range. Each side's minimum is bounded by a strictly higher sample or the segment boundary; equal-height peaks do not stop the scan. Report the prominence threshold and rejected candidate count; small late cycles in a damped clip may be excluded with a warning. Consecutive accepted maxima in one segment define complete cycles. Use actual timestamps, never `frame_index / fps`.
5. Compute each cycle duration, then use the median as the measured period and the median absolute deviation of cycle durations as cycle-to-cycle spread. Report source timestamp resolution separately; do not present either quantity as a confidence interval.
6. If fewer than two complete cycles are found, return `status="insufficient_data"`, a null measured period, and explicit warnings instead of inventing one.
7. Compute a manual reference period only from successive same-direction manual events. Compute `T_theory = 2π√(L/g)` only when both positive finite length and gravity are provided. Evaluate `(2π√L)/√g` to avoid intermediate ratio overflow/underflow, and reject any derived result that is not finite and positive with HTTP 422 in either format. Do not substitute a default value for either.

## Errors and state

- Unknown observation: 404.
- Observation has no completed trace: 409.
- Invalid axis, malformed reference events, or only one of length/gravity supplied: 422.
- Insufficient complete cycles: 200 with explicit `insufficient_data` result and warnings; CSV has its documented header and no cycle rows, with `X-Measurement-Status: insufficient_data` so the CSV response is machine-readable too.
- Measurement results are returned per request and are not cached by the API.

## Tests and acceptance

- Unit tests use synthetic `TrackResult` data with known period and irregular source timestamps.
- Verify axis projection, turning-point timestamps, median/MAD, missing-gap segmentation, no interpolation, and insufficient-cycle output.
- Verify manual reference events and theoretical period remain separate; no theory is emitted without both inputs.
- API tests verify JSON/CSV response parity, lookup errors, invalid input, and that a failed tracking rerun preserves the trace consumed by a later measurement request.
- A real calculation is accepted as plumbing evidence only. Real-world validity remains unverified until an authorized clip is compared with independently timed events.

## Risks and limits

- Tracker jitter, occlusion, drift, and large gaps can leave too few usable cycles or create spurious extrema. The result exposes the filtered signal's turning points and cycle spread; it must not silently repair missing data.
- The three-sample median filter is a disclosed initial setting, not a calibrated optimum. Change it only with evidence from real clips.
- The API remains local-only. CPU, memory, and aggregate temporary-storage controls are still required before public exposure.

## User-selected decisions

- Local `/measure` API plus JSON and CSV evidence.
- Caller-supplied 2D motion axis.
- Manual reference events and optional measured length/gravity inputs.
- Same-direction turning points with robust median aggregation.
- A documented peak-prominence threshold to reject small jitter extrema.
- JSON or CSV returned from the same request, without a cached latest measurement.

## Builder decisions proposed for approval

- The initial filter is a three-sample median over contiguous valid segments.
- A peak must have topographic prominence at least 10% of its segment's peak-to-peak range; the threshold and rejected-candidate count are included in results.
- Uncertainty is reported as cycle-to-cycle MAD, with source timing resolution reported separately; neither is a confidence interval.
- Theoretical comparison is omitted unless both length and gravity are supplied.
- Insufficient cycles return a successful HTTP response with an explicit `insufficient_data` result so users can inspect warnings and CSV evidence.
- Measurement output is returned per request and not cached in memory.
