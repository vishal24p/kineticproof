# Slice 5 implementation plan: optional Meta SAM tracking adapter

> **For agentic workers:** REQUIRED SUB-SKILL: use subagent-driven-development to execute this plan task-by-task after user approval. Keep commits explicit. Each task ends with focused tests and review.

**Goal:** Add an explicitly selected Meta SAM 3.1 adapter to the existing local tracking endpoint while preserving OpenCV as the offline default and keeping trace, overlay, and measurement contracts stable.

**Architecture:** Keep `tracking.track_video` as the existing OpenCV entry point used by the benchmark. Add one SAM adapter module that uploads only when selected, requests forward video tracking from the frame-zero ROI, consumes the official Meta response parser, maps records by frame index onto locally decoded source PTS, and publishes the same `TrackResult` plus local MP4 overlay. Extend only the shared provenance fields needed to describe the provider and request. The API route dispatches explicitly; it never falls back between providers.

**Tech stack:** Existing FastAPI, OpenCV, Pydantic, pytest; OpenAI async Python SDK pointed at Meta Model API and Meta's official `meta-sam-parser` package. Resolve and lock compatible package versions during implementation. Tests use injected fake clients/streams only; no hosted calls or real user media.

---

### Task 1: Add provider-neutral provenance support and SAM dependencies

**Files:** `services/api/src/kineticproof_api/tracking.py`, `services/api/pyproject.toml`, `services/api/uv.lock`, `services/api/tests/test_tracking.py`, `docs/TRACKING_CONTRACT.md`.

1. Verify the installed official SDK/parser APIs against current Meta documentation; add only these needed dependencies and lock them.
2. Make OpenCV-specific provenance nullable for non-OpenCV providers and add a nullable provider request ID. Preserve current OpenCV serialized values and all existing `track_video` callers.
3. Update the provider-neutral contract to explain provider-specific nullable metadata and the SAM mapping.
4. Run focused tracking tests and lock validation.

**Acceptance:** Existing OpenCV trace assertions remain valid; no response consumer or benchmark call site changes; `uv lock --check --project services/api` passes.

### Task 2: Implement the offline-testable SAM adapter

**Files:** `services/api/src/kineticproof_api/sam_tracker.py`, `services/api/tests/test_sam_tracker.py`.

1. Accept the same source path, validated metadata, ROI and observation ID as OpenCV. Reject an ROI outside the first frame before any remote call.
2. Use the official async client to create a `user_data` upload with a one-hour expiration, then request `sam-3.1` with the documented frame-zero box prompt and forward propagation. `meta-sam-parser` exposes an async stream parser; use its official parser/builder, not custom prompt or stream parsing.
3. Always attempt remote-file deletion after the response is consumed or fails. Surface a deletion failure; the one-hour expiry remains the backup.
4. Decode source frames locally and use their actual PTS for the output. Associate parser records by zero-based frame index, tolerate out-of-order records, reject duplicates/out-of-range records/invalid boxes, and leave absent frames explicitly failed. Use integer boxes and bbox midpoints. Ignore masks and uncalibrated confidence for this slice.
5. Write the overlay using the existing timestamp/box drawing behavior. Build the common `TrackResult` with provider/model identity, source hash and request ID where available. Publish output only when trace and overlay both succeed; remove incomplete overlay on failure.
6. Add offline tests for request construction and expiry, response mapping including reordered records, source PTS, missing/invalid/duplicate frame records, cleanup on both success and provider failure, parser failures, and overlay failure. Fake output is test plumbing only.

**Acceptance:** Focused tests prove deterministic mapping and cleanup without network access. Explicit SAM failures do not create a completed trace.

### Task 3: Expose explicit provider selection through the tracking API

**Files:** `services/api/src/kineticproof_api/main.py`, `services/api/tests/test_tracking.py`.

1. Make the tracking route async and add `provider=opencv|meta_sam` as a query parameter, default `opencv`; keep the current strict ROI body unchanged. Await the SAM adapter. Run the synchronous OpenCV path in Starlette's threadpool so it does not block the event loop.
2. Dispatch only to the selected implementation. If SAM is selected without `MODEL_API_KEY`, return 503 before upload. Map remote/parser/cleanup failures to a clear 502 response and invalid local media/ROI to the existing 422 contract.
3. Preserve atomic publication: a failed SAM rerun leaves any previous trace/overlay pair intact. Existing tracks, overlay and measurement routes continue to consume the selected completed result unchanged.
4. Add API tests for default and explicit OpenCV compatibility, invalid selector, missing key without client construction, SAM success wiring, no silent fallback, and prior-result preservation after SAM failure.

**Acceptance:** Existing API tests pass unchanged except any intentional assertion for the additive provenance fields; new tests do not make live requests.

### Task 4: Document the real boundary and verify the complete slice

**Files:** `docs/API_CONTRACTS.md`, `docs/META_API_VALIDATION.md`, `docs/MODEL_STRATEGY.md`, `docs/IMPLEMENTATION.md`, `docs/DECISIONS.md`, `README.md`, `docs/PROGRESS.md`, `VERSION`, `CHANGELOG.md`.

1. Document selector, configuration, remote upload/deletion/expiry behavior, error responses and local-only limits.
2. Mark SAM request plumbing as implemented only after tests pass; clearly state that access, live behavior, quality, latency and actual cost remain unverified because no hosted call ran.
3. Add one local command/endpoint example without printing or committing secrets.
4. Update version/changelog using the GStack ship workflow; ask for the release bump choice when shipping.
5. Run the complete API suite, lock check, `git diff --check`, and documented local lint/build checks only if changed frontend/config files require them. Capture exact evidence and report any failures or unverified behavior.

**Acceptance:** Documentation matches observed code and test output; no hosted call or claim of measured SAM quality exists.

---

## Final review checklist

- OpenCV remains default; benchmark still imports `tracking.track_video` unchanged.
- No silent fallback, fake measurements, secret logging, or remote media retained beyond the attempted delete and one-hour expiry.
- Out-of-order/missing SAM frames cannot be mistaken for frame-order timestamps or silently interpolated.
- Failed selected-provider reruns preserve the last successful pair.
- Full local test suite and repository diff are reviewed before GStack ship.
