# Slice 2 — Physics and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each task gets a fresh implementer and an independent review before the next task; finish with a whole-branch review.

**Goal:** Derive a traceable pendulum period measurement from the latest local tracking trace and return it as JSON or CSV.

**Architecture:** Add a pure `physics.py` calculation module that consumes the existing `TrackResult`; add one synchronous FastAPI route that serializes the same calculation as JSON or CSV per request. Keep all state in the existing app-lifetime observation map, with no measurement cache or new persistence.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, standard-library `csv`, pytest. Add no dependencies.

**Spec:** `docs/superpowers/specs/2026-10-28-slice-2-physics-and-evidence-design.md`

## Global Constraints

- Keep the API local, synchronous, temporary, and in-memory; add no database, job queue, or measurement cache.
- Use source `timestamp_seconds`; never derive time from `frame_index / fps`.
- Require a finite, nonzero 2D motion axis and normalize it before projecting centers.
- Keep null centers as gaps; do not interpolate or form cycles across gaps.
- Apply a three-sample median filter only within contiguous valid segments.
- Disclose `measurement_config` (`filter_name: "median"`, `filter_window_samples: 3`, `detector: "local_maximum"`, `prominence_method: "topographic"`, `prominence_fraction: 0.1`) separately from tracking provenance.
- Require peak prominence ≥10% of the segment's peak-to-peak range; report the threshold and rejected-candidate count.
- Bound each prominence side scan by a strictly higher sample or the segment boundary; report missing-data warnings whenever gaps exist, including successful results.
- Aggregate complete same-direction peak intervals with the median; report cycle-to-cycle MAD and source timing resolution separately, not as a confidence interval.
- Return `insufficient_data` with a null measured period unless at least two complete cycles are available.
- Compute theoretical period only when both positive finite `length_m` and `gravity_m_s2` are supplied.
- Avoid intermediate theory ratio overflow/underflow with `(2π√L)/√g`; return 422 for a nonfinite or nonpositive derived period in either output format.
- Report measured, manual-reference, and theoretical periods separately; do not infer metric velocity or acceleration from pixels.

## Review Focus

- Zero, nonfinite, or malformed axis values must return a clear 422 response; test the axis request model.
- Missing centers split the signal into separate segments; test that no peak pair crosses a gap.
- Jitter peaks below the prominence threshold must be excluded and counted; test a synthetic noisy trace with known cycles.
- Alternating left/right manual events must not be mistaken for full periods; test grouping by event type and timestamp order.
- Supplying only length or only gravity must fail validation; test both partial-input cases.

---

### Task 1: Deterministic period calculation

**Files:**
- Create: `services/api/src/kineticproof_api/physics.py`
- Create: `services/api/tests/test_physics.py`

**Interfaces:**
- Consumes: `kineticproof_api.tracking.TrackResult`, `TrackFrame`, and their source timestamps/centers.
- `MeasurementRequest`: Pydantic model with finite nonzero `motion_axis: MotionAxis(x: FiniteFloat, y: FiniteFloat)`, `reference_events: list[ReferenceEvent]` defaulting via `Field(default_factory=list)`, and optional finite `length_m` / `gravity_m_s2`.
- `ReferenceEvent`: Pydantic model with `event_type: Literal["leftmost", "rightmost", "same_direction"]`, finite `timestamp_seconds`, strict nonnegative `evidence_frame_index`, finite nonnegative `uncertainty_seconds`, and optional `notes`.
- `MeasurementResult`: Pydantic model with `schema_version`, `status: Literal["succeeded", "insufficient_data"]`, motion axis, explicit `measurement_config` with the fixed filter/detector settings above, valid/total frame counts and fraction, accepted turning points, rejected candidate count, prominence threshold in pixels, cycle list, measured period or null, cycle MAD or null, source timing resolution or null, gap ranges, manual reference intervals and median, theoretical period or null, warnings, and provenance.
- Nested output records: `TurningPoint(frame_index, timestamp_seconds, position_px, prominence_px)`; `CyclePeriod(start_frame_index, end_frame_index, start_timestamp_seconds, end_timestamp_seconds, period_seconds, prominence_px)`; `ManualReferenceInterval(event_type, start_timestamp_seconds, end_timestamp_seconds, period_seconds, start_uncertainty_seconds, end_uncertainty_seconds)`; `FrameRange(start_frame_index, end_frame_index)`; `MeasurementProvenance(source_video_sha256, provider_name, model_name, model_version, run_config_id)`.
- Produces `measure_trace(trace: TrackResult, request: MeasurementRequest) -> MeasurementResult` and `measurement_csv(result: MeasurementResult) -> str`.

- [x] **Step 1: Write failing tests for axis validation, projection, segment boundaries, and source timestamps**

Test finite nonzero axis normalization; use synthetic `TrackResult` values with irregular timestamps; verify missing centers split segments and no cycle spans a gap.

- [x] **Step 2: Run the focused tests and verify they fail**

Run: `uv run --project services/api pytest services/api/tests/test_physics.py -q`
Expected: FAIL because the measurement models and calculation do not exist.

- [x] **Step 3: Implement request/result models and segmented projection in `physics.py`**

Validate axis, manual-event ordering/type/frame index, and the all-or-none positive finite length/gravity pair. Project each valid center onto the normalized axis. Filter interior points with a three-sample median while leaving segment endpoints intact.

- [x] **Step 4: Add failing turning-point, prominence, median/MAD, manual-reference, theory, and insufficient-data tests**

Assert that same-direction positive maxima are accepted only at ≥10% of the segment range; candidate periods use source times; fewer than two complete intervals yield `insufficient_data`; manual periods pair only matching event types and preserve both endpoint uncertainties; theory uses `2π√(L/g)` only for a complete input pair.

- [x] **Step 5: Run the focused tests and verify the new cases fail**

Run: `uv run --project services/api pytest services/api/tests/test_physics.py -q`
Expected: FAIL for the not-yet-implemented detector and comparison calculations.

- [x] **Step 6: Implement peak prominence, cycle summaries, comparisons, warnings, and CSV serialization**

Report accepted turning points and each complete cycle with its start/end frame and source timestamp, period, and peak prominence. Return median and MAD; report median positive timestamp step separately. CSV columns are `cycle_index,start_frame_index,end_frame_index,start_timestamp_seconds,end_timestamp_seconds,period_seconds,peak_prominence_px,measured_period_seconds,cycle_period_mad_seconds,source_timing_resolution_seconds,manual_reference_period_seconds,theoretical_period_seconds,source_video_sha256`. CSV contains one row per complete cycle and a stable header even when insufficient data produces no cycle rows.

- [x] **Step 7: Run focused physics tests and commit**

Run: `uv run --project services/api pytest services/api/tests/test_physics.py -q`
Expected: PASS for all calculation and CSV cases.

```bash
git add services/api/src/kineticproof_api/physics.py services/api/tests/test_physics.py
git commit -m "feat: calculate pendulum periods from tracking traces"
```

### Task 2: Measurement API response formats

**Files:**
- Modify: `services/api/src/kineticproof_api/main.py`
- Create: `services/api/tests/test_physics_api.py`

**Interfaces:**
- Consumes: `MeasurementRequest`, `MeasurementResult`, `measure_trace(...)`, and `measurement_csv(...)` from Task 1.
- Produces: `POST /api/observations/{observation_id}/measure?format=json|csv`, defaulting to JSON and calculating from the observation's latest successful trace on each request.

- [x] **Step 1: Write failing API tests for unknown observations and observations without a trace**

Assert unknown IDs return 404 and known IDs without a completed trace return 409.

- [x] **Step 2: Run focused API tests and verify they fail**

Run: `uv run --project services/api pytest services/api/tests/test_physics_api.py -q`
Expected: FAIL because the route does not exist.

- [x] **Step 3: Add failing JSON and CSV endpoint tests**

Assert JSON returns `MeasurementResult`; CSV for the same payload returns `text/csv` with rows matching the JSON cycle periods; `format=json` and the default format are equivalent; insufficient data returns HTTP 200 with explicit status in JSON, `X-Measurement-Status: insufficient_data` in CSV, and a header-only CSV.

- [x] **Step 4: Implement the synchronous measurement route in `main.py`**

Resolve the current completed trace with `get_tracking_run`, map calculation validation errors to 422, and serialize either the result or CSV. Do not write measurement results to app state.

- [x] **Step 5: Run API and existing tracking tests and commit**

Run: `uv run --project services/api pytest services/api/tests/test_physics_api.py services/api/tests/test_tracking.py -q`
Expected: PASS; existing upload/tracking behavior remains intact.

```bash
git add services/api/src/kineticproof_api/main.py services/api/tests/test_physics_api.py
git commit -m "feat: expose JSON and CSV measurement responses"
```

### Task 3: Contracts and evidence documentation

**Files:**
- Modify: `docs/API_CONTRACTS.md`
- Modify: `docs/SCIENCE_ENGINE.md`
- Modify: `docs/PROGRESS.md`

**Interfaces:**
- Consumes: finalized API and result fields from Tasks 1–2.
- Produces: local request/response, algorithm, warnings, and verification documentation that matches the code.

- [x] **Step 1: Update the API contract**

Document the request fields, `format=json|csv`, response fields, 404/409/422 behavior, and HTTP 200 `insufficient_data` result.

- [x] **Step 2: Update the science engine contract**

Document axis projection, three-sample median filter, gap handling, prominence threshold, median/MAD definition, optional manual reference events, and conditional theoretical period. State that authentic-clip validity remains unverified.

- [x] **Step 3: Run the full API suite, lock check, and diff check; update evidence**

Run: `uv run --project services/api pytest services/api/tests -q`
Expected: PASS with exact count recorded in `docs/PROGRESS.md`.

Run: `uv lock --check --project services/api`
Expected: PASS; no dependency changes.

Run: `git diff --check`
Expected: no whitespace errors.

- [x] **Step 4: Commit docs and evidence**

```bash
git add docs/API_CONTRACTS.md docs/SCIENCE_ENGINE.md docs/PROGRESS.md
git commit -m "docs: record physics measurement contract"
```

## Final acceptance

- Broad shoulder peaks must survive filtering but be rejected by topographic prominence; gaps must leave actual cycles on both sides with exact source timestamps and no cross-gap interval.
- JSON discloses measurement configuration; successful gapped measurements warn about missing data. JSON and CSV preserve representable extreme theoretical periods and reject unrepresentable periods with 422.
- A synthetic trace with known period produces matching cycle intervals from source timestamps, without interpolation across gaps.
- JSON and CSV responses represent the same request and calculation.
- Manual reference and theoretical values remain separate from the measured period.
- Tests and local runtime prove plumbing only; no authentic-footage accuracy claim is made.

