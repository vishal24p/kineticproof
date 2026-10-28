# Slice 1 Open Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each task gets a fresh implementer and an independent review before the next task; finish with a whole-branch review.

**Goal:** Accept a short local video, track a user-selected object with OpenCV CSRT, and return a timestamped provider-neutral trace plus annotated MP4.

**Architecture:** FastAPI owns uploads and synchronous tracking. A focused tracking module validates and decodes media, runs CSRT, and writes trace/overlay files in an app-lifetime temporary directory; API state maps opaque observation IDs to those files and metadata. OpenCV FFmpeg PTS is authoritative; missing PTS fails explicitly.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, `opencv-contrib-python-headless>=4.13.0.92,<4.14` (for FFmpeg PTS), pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-10-27-slice-1-open-tracking.md`

## Global Constraints

- Accept MP4/MOV uploads only; maximum 100,000,000 bytes and 30 seconds.
- Require integer pixel coordinates in the initial bounding box `{x, y, width, height}` on the first frame; return detected boxes in that object shape.
- Do not replace missing timestamps with `frame_index / fps`; fail if usable PTS is unavailable.
- Missing tracker updates have null centers and explicit flags; do not interpolate or relink.
- Keep media temporary and private; do not commit video fixtures or add a database/job queue.
- Label synthetic test media as synthetic; it is plumbing evidence, not measured footage.
- The overlay labels source timestamps; JSON trace is authoritative for timing.

## Review Focus

- Truncated or malformed uploads must be rejected and partial temporary files removed (test cleanup on decode failure).
- A timestamp of zero is valid; missing PTS must fail without FPS fallback (test both cases).
- Bounding boxes must have positive dimensions and fit fully within the decoded first frame (test zero, negative, and out-of-bounds cases).
- Failed CSRT updates must preserve the frame and timestamp while returning null centers (test a controlled failed update).
- In-memory observation IDs must not expose filesystem paths and unknown IDs must return 404 (test response shape and lookup).

---

### Task 1: Media upload and validation

**Files:**
- Modify: `services/api/pyproject.toml` (add multipart and OpenCV contrib headless runtime dependencies)
- Modify: `services/api/uv.lock`
- Create: `services/api/src/kineticproof_api/tracking.py` (video inspection and PTS validation)
- Modify: `services/api/src/kineticproof_api/main.py` (app lifespan, upload route, observation registry, shutdown cleanup)
- Test: `services/api/tests/test_tracking.py`

**Interfaces:**
- Produces `POST /api/observations` accepting multipart `file`; returns `{observation_id, duration_seconds, width, height, frame_count}` without echoing user filenames or filesystem paths.
- Stores an opaque ID and private source path in app state; returns 413 for size/duration limits, 415 for unsupported formats, and 422 for corrupt or undecodable video.
- `inspect_video(path: Path) -> VideoMetadata` in `tracking.py` decodes with OpenCV's FFmpeg backend, requires monotonic `CAP_PROP_PTS` (including valid initial zero), and returns duration as last source timestamp minus first, dimensions, frame count, and FPS.

- [x] Write tests for accepted MP4/MOV, unsupported extension, >100 MB stream (lower the module limit in the test), >30-second video, corrupt data, valid zero PTS, missing PTS, and partial-file cleanup after rejection.
- [x] Run the new focused tests and confirm failure.
- [x] Implement streaming upload with a 100,000,000-byte counter and validated decoder pass; ensure partial files are deleted on every failure.
- [x] Resolve/install dependencies and run `uv run --project services/api pytest -c services/api/pyproject.toml services/api/tests/test_tracking.py -q`.
- [x] Test lifespan shutdown removes its app-owned temporary files; leave files outside that directory untouched.

### Task 2: Provider-neutral CSRT trace and overlay

**Files:**
- Modify: `services/api/src/kineticproof_api/tracking.py` (trace models, PTS decoding, ROI validation, CSRT run, overlay write)
- Modify: `services/api/src/kineticproof_api/main.py` (tracking/trace/overlay routes)
- Modify: `docs/TRACKING_CONTRACT.md` (record the implemented v1 mapping)
- Modify: `docs/API_CONTRACTS.md` (mark Slice 1 endpoints as implemented and state local/synchronous limits)
- Test: `services/api/tests/test_tracking.py`

**Interfaces:**
- `POST /api/observations/{observation_id}/tracking` accepts `{x, y, width, height}` and returns `{status, frame_count}`.
- `GET /api/observations/{observation_id}/tracks` returns the `TRACKING_CONTRACT.md` v1 fields: `schema_version`, nullable `experiment_id`, `video_id` (the observation ID for this slice), `provider_name`, `model_name`, `model_version`, `run_config_id`, `status`, `frames`, `failures`, and `provenance`.
- Each frame records index, source `timestamp_seconds`, optional `bbox_px`, nullable center coordinates, and quality flags. Provenance includes source SHA-256, OpenCV version, PTS timebase, and requested frame count. Use `experiment_id: null` until experiment creation exists.
- Failed reruns preserve the previous successful trace and overlay; only replace them after a new run completes.
- `GET /api/observations/{observation_id}/overlay` serves `video/mp4`.

- [x] Write tests for invalid/non-integer ROI, increasing source timestamps, explicit failed updates with null centers, trace shape/provenance, overlay response, failed-rerun preservation, and unknown IDs.
- [x] Run focused tests and confirm failure.
- [x] Implement the smallest tracking module using FFmpeg-backed OpenCV PTS and CSRT; preserve source timestamps in JSON and draw them on overlay frames.
- [x] Run the focused tests and full API suite; validate the lockfile and API startup/health check, capturing exact results.
- [x] Update `docs/PROGRESS.md` with observed evidence and state that synthetic tests do not validate real-world tracking; complete plan checkboxes and request an independent whole-branch review before GStack ship.
