# Internal web/backend contracts

## Implemented locally — Slices 1, 2 and 6 API

These endpoints use request/response calls with local, temporary state. Run one API process bound to localhost. No accounts, deployment, job queue or persistent storage is implemented. Uploaded media, traces and overlays remain in the app-owned temporary directory until the API process shuts down, when that directory is removed. Observation endpoints require an anonymous browser session cookie; every observation response, including authorization errors and overlay files, carries `Cache-Control: no-store`. `POST /api/session` also returns `no-store`; `/health` is public and outside this policy. The cookie provides bearer-session ownership only, not account authentication. Before hosted exposure, add aggregate storage and concurrency limits and a host-appropriate retention policy.

- `GET /health`: returns `{"status":"ok"}`.
- `POST /api/session`: establish an anonymous session before upload. Returns `{"status":"ok"}` and sets `kineticproof_session` as an `HttpOnly`, `SameSite=Strict`, `Path=/api` browser-session cookie, without a Domain or expiry. Valid repeat requests preserve the existing cookie; missing or invalid cookies are replaced. The cookie contains a random 256-bit session ID and an HMAC-SHA256 signature made with a process-lifetime random key. Session IDs never appear in the response body. Set `KINETICPROOF_COOKIE_SECURE=1` behind hosted TLS; local HTTP defaults to a non-Secure cookie. Restarting the process invalidates cookies, consistent with in-memory observation loss.
- `POST /api/observations`: multipart `file`, MP4/MOV only with supported container brand (`isom`, `iso2`, `mp41`, `mp42`, QuickTime, AVC, AV1, or M4V), at most 100,000,000 bytes and 30 seconds. Returns `{observation_id,duration_seconds,width,height,frame_count}`. Source PTS must be available and increasing; at least two frames are required. Duration is the last source PTS minus the first.
- `POST /api/observations/{id}/tracking?provider=opencv|meta_sam`: JSON `{x,y,width,height}`, strict integer pixels within the first frame. The optional provider defaults to `opencv`; that path runs OpenCV CSRT with default parameters. `meta_sam` explicitly uploads the source video to Meta SAM 3.1 and maps returned boxes to the same trace and overlay contract. It requires `MODEL_API_KEY`; without it, the API returns 503 before creating a client. SAM request, parser, or remote-file deletion failures return 502. There is no automatic fallback between providers. Successful calls return `{status,frame_count}` after trace and overlay both succeed; missing per-frame boxes make status `partial`.
- `GET /api/observations/{id}/tracks`: returns the [v1 TrackResult](TRACKING_CONTRACT.md#implemented-local-v1-mapping).
- `GET /api/observations/{id}/overlay`: serves the completed overlay as `video/mp4`, encoded as VP9 in an MP4 container (`vp09`; OpenCV writer `VP90`). Chromium playback is verified; other browsers must support MP4/VP9. Overlay playback uses constant FPS without audio; trace source timestamps remain authoritative.
- `POST /api/observations/{id}/measure?format=json|csv`: measures the completed trace using tracked centers and source timestamps. The query is optional and defaults to `json`.

### Measurement request

Send JSON with required `motion_axis: {x, y}`. Components must be finite and the vector nonzero; it is normalized before projection. Optional `reference_events` is an ordered array of `{event_type, timestamp_seconds, evidence_frame_index, uncertainty_seconds, notes?}`. `event_type` is `leftmost`, `rightmost`, or `same_direction`; timestamps must be finite and strictly increasing, frame indexes are nonnegative integers and must exist in the trace, and uncertainty must be finite and nonnegative. Optional `length_m` and `gravity_m_s2` must be supplied together and both positive. Unknown format, invalid JSON fields, or a reference frame absent from the trace return 422.

### Measurement responses

JSON returns HTTP 200 with `schema_version`, `status` (`succeeded` or `insufficient_data`), normalized `motion_axis`, `valid_frame_count`, `total_frame_count`, `valid_frame_fraction`, `turning_points` (`frame_index`, `timestamp_seconds`, `position_px`, `prominence_px`), `rejected_candidate_count`, aggregate `prominence_threshold_px`, `segment_prominence_thresholds` (frame bounds and threshold per valid segment), `cycles` (frame bounds, timestamps, period and prominence), nullable `measured_period_seconds`, nullable `cycle_mad_seconds`, nullable `source_timing_resolution_seconds`, `gap_ranges`, `manual_reference_intervals`, nullable `manual_reference_period_seconds`, nullable `theoretical_period_seconds`, `warnings`, and `provenance` (`source_video_sha256`, provider/model name and version, run config ID).

JSON also includes explicit `measurement_config`: `{filter_name: "median", filter_window_samples: 3, detector: "local_maximum", prominence_method: "topographic", prominence_fraction: 0.1}`. These fixed measurement settings are distinct from the tracking `provenance.run_config_id`. Any nonempty `gap_ranges` adds a missing-data warning, including for a `succeeded` result. Both length and gravity must be finite; theory uses stable square-root arithmetic, and an unrepresentable derived period returns 422 for JSON and CSV instead of nonfinite output.

At least two complete detected cycles are required for `succeeded` and a measured period. With fewer cycles, the endpoint still returns HTTP 200 and `status: "insufficient_data"`; measured period and cycle MAD are null. CSV returns `text/csv` and the `X-Measurement-Status` header. Its columns are `cycle_index`, `start_frame_index`, `end_frame_index`, `start_timestamp_seconds`, `end_timestamp_seconds`, `period_seconds`, `peak_prominence_px`, `measured_period_seconds`, `cycle_period_mad_seconds`, `source_timing_resolution_seconds`, `manual_reference_period_seconds`, `theoretical_period_seconds`, and `source_video_sha256`. An insufficient result, including exactly one detected cycle, yields a header-only CSV. Measurements are computed per request; no measurement cache is used.

Missing or invalid session cookie: 401. An observation owned by another valid session returns the same 404 as an unknown observation. Existing tracks, measure, and overlay routes return 409 when an owned observation has no completed trace. Invalid measurement request or unavailable reference frame: 422. For existing upload/tracking routes, invalid ROI, decode failure after container validation, or unavailable/nonincreasing source PTS: 422. Overlay writer/server failure: 500. Missing Meta key: 503. Selected SAM request, parser, or remote deletion failure: 502; it never retries or falls back to OpenCV. Uploads exceeding limits: 413; unsupported extension/container: 415.

Reruns publish a matching trace/overlay pair only after both outputs succeed. Failed reruns preserve the previous pair and remove incomplete new media. A `partial` trace is a completed result and can be measured. Superseded successful overlay files remain private until app shutdown so ongoing downloads can finish. An explicitly selected SAM run uploads the source under `user_data`, requests a 3600-second expiry, and attempts deletion after the response is consumed or fails; expiry is the backstop if deletion fails. This temporary retention, network latency and synchronous request/response work are local-development limits; resource controls are required before public deployment. No live SAM call has been verified.

## Implemented next-trial planning (API only)

`POST /api/observations/{id}/next-trial?provider=template|meta_muse` requires an existing completed trace (including a `partial` trace). The default is `template`: deterministic, offline, and does not read credentials or create a remote client. Planning is stateless: every request supplies context and recomputes measurements from the existing local trace; no experiment, suggestion, or conversation is persisted. Existing observation/media state remains process-local. The web UI does not expose this endpoint.

Send JSON:

```json
{
  "context": {
    "question": "How does length affect period?",
    "hypothesis": "A longer pendulum has a longer period.",
    "focus_variable": "length_m",
    "length_m": 0.5,
    "release_angle_degrees": 8,
    "background_condition": "clear",
    "camera_fixed": true
  },
  "motion_axis": {"x": 1, "y": 0},
  "reference_events": [],
  "gravity_m_s2": 9.81
}
```

Required context: `question` and `hypothesis` (1–500 characters each), `focus_variable` (`length_m|background_condition`), finite positive `length_m`, finite `release_angle_degrees` strictly between 0 and 90, `background_condition` (`clear|cluttered_static|moving_background_or_occlusion`), and strict boolean `camera_fixed`. `motion_axis` uses the measurement contract above. `reference_events` is optional (default `[]`) and uses the same manual-reference validation. `gravity_m_s2` is optional/null or finite positive; only when supplied is theory computed using context length. Unknown request/context fields are rejected; client measurements or provenance are not accepted.

HTTP 200 returns `{provider_name, measurement, suggestion}`. `provider_name` is `template|meta_muse`; `measurement` is the full local `MeasurementResult` described above. `suggestion` contains `focus_variable`, `action`, `variable_to_change`, `held_constant`, `rationale`, and `limitation`. With insufficient evidence, action is `record_more_cycles`, changing `recording_duration` while holding `length_m`, `release_angle_degrees`, `camera_position`, and `background_condition` constant. Otherwise action is `vary_length` or `vary_background_condition`, matching the requested focus, with the other three experiment variables held constant. Rationale and limitation are nonempty strings. Suggestions are guidance, not measured facts or validated causal conclusions.

Explicit `provider=meta_muse` reads `MODEL_API_KEY` from the API process environment and constructs the existing async OpenAI SDK client with `base_url=https://api.meta.ai/v1` and `max_retries=0`. It requests model `muse-spark-1.3` through Responses with `store=false`, instructions, and strict JSON-schema output via `text.format`. Local validation enforces the expected action, focus, and held constants; extra measured/predicted fields are rejected. An English lexical guard rejects numeric measurement/prediction prose, but is not a general guarantee of scientific correctness. Model output never replaces measurements.

**Data sent to Meta:** all seven context fields (`question`, `hypothesis`, `focus_variable`, `length_m`, `release_angle_degrees`, `background_condition`, `camera_fixed`), plus only these server-computed measurement fields: `status`, `measured_period_seconds`, `cycle_mad_seconds`, `valid_frame_fraction`, `warnings`. The request also includes instructions and the suggestion schema. Video, frames, media paths, observation IDs and provenance are not sent as separate fields; source hashes/provenance, full traces, motion axis, reference events/notes, gravity, theoretical/manual periods, cycle details, and other measurement fields are excluded from the structured payload. Question and hypothesis text is forwarded verbatim and may contain identifying information; do not put personal information or secrets in it. `store=false` is a request setting, not a verified provider retention guarantee.

Errors: unknown observation 404; no completed trace 422; invalid provider/context/local measurement input (including absent reference frames) 422; absent `MODEL_API_KEY` 503 before client construction; Muse request, incomplete response, parsing/schema, suggestion-validation, or standalone client-close failure 502. The client is closed on success/failure. There are no automatic retries or fallback to template after explicit Muse selection. Hosted compatibility, entitlement, scientific quality, latency and cost remain unverified; only offline tests with fake clients/synthetic traces have run. Confirm account access and spend authorization before any hosted request.

## Future logical design — not implemented

`POST /api/experiments` create an experiment draft with kind, variables, hypotheses and consent state. Observation calibration/consent metadata, provider selection (`opencv|open_model|meta_sam`) and asynchronous jobs remain future extensions. No Meta required for the default.
`GET /api/jobs/{id}` status+error.
`GET /api/experiments/{id}/evidence` original/overlay plots+cycle picks+export. Experiment-level planning remains future; the observation-level route above is implemented.

These future routes are candidates. Aggregate storage/concurrency and budget controls, idempotent jobs and bounded cleanup are required before public deployment. The web UI calls `POST /api/session` before enabling upload; a local Chromium proxy smoke verified cookie forwarding. API tests do not exercise the browser rewrite. The web UI does not yet expose provider selection. Version schemas once implemented; never copy unverified Meta request schema into public API.
