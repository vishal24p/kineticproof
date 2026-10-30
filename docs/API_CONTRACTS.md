# Internal web/backend contracts

## Implemented locally — Slice 1 and Slice 2

These endpoints use request/response calls with local, temporary state. Run one API process bound to localhost. No accounts, deployment, job queue or persistent storage is implemented. Uploaded media, traces and overlays disappear on process shutdown; IDs are not authorization and this API must not be exposed publicly.

- `GET /health`: returns `{"status":"ok"}`.
- `POST /api/observations`: multipart `file`, MP4/MOV only with supported container brand (`isom`, `iso2`, `mp41`, `mp42`, QuickTime, AVC, AV1, or M4V), at most 100,000,000 bytes and 30 seconds. Returns `{observation_id,duration_seconds,width,height,frame_count}`. Source PTS must be available and increasing; at least two frames are required. Duration is the last source PTS minus the first.
- `POST /api/observations/{id}/tracking?provider=opencv|meta_sam`: JSON `{x,y,width,height}`, strict integer pixels within the first frame. The optional provider defaults to `opencv`; that path runs OpenCV CSRT with default parameters. `meta_sam` explicitly uploads the source video to Meta SAM 3.1 and maps returned boxes to the same trace and overlay contract. It requires `MODEL_API_KEY`; without it, the API returns 503 before creating a client. SAM request, parser, or remote-file deletion failures return 502. There is no automatic fallback between providers. Successful calls return `{status,frame_count}` after trace and overlay both succeed; missing per-frame boxes make status `partial`.
- `GET /api/observations/{id}/tracks`: returns the [v1 TrackResult](TRACKING_CONTRACT.md#implemented-local-v1-mapping).
- `GET /api/observations/{id}/overlay`: serves the completed overlay as `video/mp4`.
- `POST /api/observations/{id}/measure?format=json|csv`: measures the completed trace using tracked centers and source timestamps. The query is optional and defaults to `json`.

### Measurement request

Send JSON with required `motion_axis: {x, y}`. Components must be finite and the vector nonzero; it is normalized before projection. Optional `reference_events` is an ordered array of `{event_type, timestamp_seconds, evidence_frame_index, uncertainty_seconds, notes?}`. `event_type` is `leftmost`, `rightmost`, or `same_direction`; timestamps must be finite and strictly increasing, frame indexes are nonnegative integers and must exist in the trace, and uncertainty must be finite and nonnegative. Optional `length_m` and `gravity_m_s2` must be supplied together and both positive. Unknown format, invalid JSON fields, or a reference frame absent from the trace return 422.

### Measurement responses

JSON returns HTTP 200 with `schema_version`, `status` (`succeeded` or `insufficient_data`), normalized `motion_axis`, `valid_frame_count`, `total_frame_count`, `valid_frame_fraction`, `turning_points` (`frame_index`, `timestamp_seconds`, `position_px`, `prominence_px`), `rejected_candidate_count`, aggregate `prominence_threshold_px`, `segment_prominence_thresholds` (frame bounds and threshold per valid segment), `cycles` (frame bounds, timestamps, period and prominence), nullable `measured_period_seconds`, nullable `cycle_mad_seconds`, nullable `source_timing_resolution_seconds`, `gap_ranges`, `manual_reference_intervals`, nullable `manual_reference_period_seconds`, nullable `theoretical_period_seconds`, `warnings`, and `provenance` (`source_video_sha256`, provider/model name and version, run config ID).

JSON also includes explicit `measurement_config`: `{filter_name: "median", filter_window_samples: 3, detector: "local_maximum", prominence_method: "topographic", prominence_fraction: 0.1}`. These fixed measurement settings are distinct from the tracking `provenance.run_config_id`. Any nonempty `gap_ranges` adds a missing-data warning, including for a `succeeded` result. Both length and gravity must be finite; theory uses stable square-root arithmetic, and an unrepresentable derived period returns 422 for JSON and CSV instead of nonfinite output.

At least two complete detected cycles are required for `succeeded` and a measured period. With fewer cycles, the endpoint still returns HTTP 200 and `status: "insufficient_data"`; measured period and cycle MAD are null. CSV returns `text/csv` and the `X-Measurement-Status` header. Its columns are `cycle_index`, `start_frame_index`, `end_frame_index`, `start_timestamp_seconds`, `end_timestamp_seconds`, `period_seconds`, `peak_prominence_px`, `measured_period_seconds`, `cycle_period_mad_seconds`, `source_timing_resolution_seconds`, `manual_reference_period_seconds`, `theoretical_period_seconds`, and `source_video_sha256`. An insufficient result, including exactly one detected cycle, yields a header-only CSV. Measurements are computed per request; no measurement cache is used.

Unknown observation: 404. Known observation without a completed trace: 409. Invalid measurement request or unavailable reference frame: 422. For existing upload/tracking routes, invalid ROI, decode failure after container validation, or unavailable/nonincreasing source PTS: 422. Overlay writer/server failure: 500. Missing Meta key: 503. Selected SAM request, parser, or remote deletion failure: 502; it never retries or falls back to OpenCV. Uploads exceeding limits: 413; unsupported extension/container: 415.

Reruns publish a matching trace/overlay pair only after both outputs succeed. Failed reruns preserve the previous pair and remove incomplete new media. A `partial` trace is a completed result and can be measured. Superseded successful overlay files remain private until app shutdown so ongoing downloads can finish. An explicitly selected SAM run uploads the source under `user_data`, requests a 3600-second expiry, and attempts deletion after the response is consumed or fails; expiry is the backstop if deletion fails. This temporary retention, network latency and synchronous request/response work are local-development limits; resource controls are required before public deployment. No live SAM call has been verified.

## Future logical design — not implemented

`POST /api/experiments` create an experiment draft with kind, variables, hypotheses and consent state. Observation calibration/consent metadata, provider selection (`opencv|open_model|meta_sam`) and asynchronous jobs remain future extensions. No Meta required for the default.
`GET /api/jobs/{id}` status+error.
`GET /api/experiments/{id}/evidence` original/overlay plots+cycle picks+export; `POST /api/experiments/{id}/next-trial` generate grounded next trial via templates or selected validated planner.

These future routes are candidates. Ownership/privacy and budget controls, idempotent jobs and bounded cleanup are required before public deployment. The web UI does not yet expose provider selection. Version schemas once implemented; never copy unverified Meta request schema into public API.
