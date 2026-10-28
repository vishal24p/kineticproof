# Task 2 report: Measurement API response formats

## Status
Completed and committed the measurement response route and API tests.

## Changed files
- `services/api/src/kineticproof_api/main.py`: added `POST /api/observations/{observation_id}/measure`. Each request reads the latest successful `TrackingRun`, calls `measure_trace`, returns `MeasurementResult` JSON by default or CSV when `format=csv`, and maps calculation validation errors to HTTP 422. CSV includes `X-Measurement-Status` for both result statuses.
- `services/api/tests/test_physics_api.py`: covers unknown observation (404), missing trace (409), JSON default/explicit equivalence, matching CSV cycle periods, insufficient data responses, invalid measurement requests (422), and invalid format (422).

## Verification
Command: `uv run --project services/api pytest services/api/tests/test_physics_api.py services/api/tests/test_tracking.py -q`
Result: **74 passed** in 3.69s.

Command: `git diff --check`
Result: passed.

## Evidence and limitations
No measurement cache is written. Tests use deterministic in-memory traces and verify API plumbing; they are not measurements from authentic footage. Existing tracking tests also passed.

## Commit
`feat: expose JSON and CSV measurement responses`

## Round 1 review fix
The reviewer found that a trace with exactly one cycle has `insufficient_data` status but the shared Task 1 CSV serializer still emitted that cycle row. Updated `measurement_csv` to emit cycle rows only for `succeeded` results, preserving the existing CSV columns and successful output. Added an API regression test with exactly one cycle; it asserts the JSON status and cycle count, plus a header-only CSV and `X-Measurement-Status: insufficient_data`.

Verification command: `uv run --project services/api pytest services/api/tests/test_physics.py services/api/tests/test_physics_api.py -q`
Result: **15 passed** in 0.88s.

`git diff --check`: passed.
