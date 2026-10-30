# Slice 5 design: optional Meta SAM tracking adapter

## Goal

Add an explicit Meta SAM provider to the existing local tracking API. OpenCV CSRT remains the default and the offline path. Selecting SAM never silently falls back to OpenCV. This slice builds and tests the adapter offline; it makes no hosted requests and claims no measured SAM results.

## Decisions

- Scope is SAM adapter first; Muse is a later slice.
- Keep the current ROI JSON body and select the provider with `?provider=opencv|meta_sam`; default to `opencv`.
- Reuse the validated first-frame integer ROI as SAM's frame-zero box prompt, and propagate forward.
- Keep the existing v1 `TrackResult` response and physics contract. Derive centers from each returned bounding-box midpoint; do not use mask centroids.
- Associate SAM results by zero-based frame index because results may arrive out of order. Pair them with source PTS decoded from the uploaded file. Missing frames remain null with explicit failure flags; reject duplicate or out-of-range frame records and invalid boxes.
- Upload only when `meta_sam` is explicitly selected. Use the OpenAI async Python SDK against Meta Model API, SAM 3.1, and Meta's official async Python parser; do not hand-parse the stream format. Keep synchronous OpenCV work in FastAPI's threadpool when the tracking route becomes async.
- Request a remote file expiry of one hour and attempt immediate deletion in a `finally` path after the response is consumed, including failed calls. The expiry is a cleanup backstop. Report cleanup failure rather than silently treating remote deletion as successful.
- Read `MODEL_API_KEY` only at request time. If absent, return a clear service-unavailable error. Remote provider errors return a clear gateway error. Neither case changes a previous successful local trace/overlay pair.
- Record provider/model identity and remote request ID when available in provenance. Keep OpenCV-specific provenance populated for OpenCV runs and absent for SAM.
- Use synthetic/local fixtures and fake SDK responses in tests. No API key, paid call, uploaded user video, or synthetic result presented as a real SAM measurement.

## Request and response behavior

`POST /api/observations/{id}/tracking?provider=meta_sam` accepts the same `{x,y,width,height}` body as the current endpoint. The explicit `opencv` selector and omitted selector run the existing CSRT path. Invalid selector values receive 422. `GET /tracks`, `/overlay`, and `/measure` keep their current response formats and consume the selected provider's completed result without physics changes.

SAM boxes are validated against source dimensions and converted to integer pixels using the existing nearest-pixel rule. The trace has one row for every decoded source frame and uses its source PTS. The local overlay is generated from those same source frames and boxes. If SAM returns no valid box for a frame, that row has null box/center and a failure entry; any such row makes status `partial`. A failed run is not published, preserving the prior successful pair.

## Code and documentation scope

- `services/api/src/kineticproof_api/main.py`: optional provider query and explicit dispatch/error mapping.
- `services/api/src/kineticproof_api/sam_tracker.py`: SAM upload/request/parser mapping, cleanup, source-timed trace, and overlay output; reuse existing tracking types, container validation and overlay drawing where practical.
- `services/api/src/kineticproof_api/tracking.py`: only the smallest contract/provenance adjustment needed for SAM while preserving OpenCV and benchmark callers.
- `services/api/pyproject.toml`, `services/api/uv.lock`: official SDK and parser dependencies.
- API/SAM adapter tests: offline request construction, out-of-order results, PTS mapping, gaps/invalid frames, cleanup on success/failure, missing key, explicit-provider errors and failed-rerun preservation.
- `docs/API_CONTRACTS.md`, `docs/TRACKING_CONTRACT.md`, `docs/META_API_VALIDATION.md`, `docs/MODEL_STRATEGY.md`, `README.md`, and evidence-based `docs/PROGRESS.md` updates.

## Risks and limits

- Account access, endpoint entitlement, real output quality, latency and actual billed usage remain unverified until an authorized live evaluation. No results or provider value will be claimed from mocks.
- The existing API is synchronous and local-only. SAM requests add network latency; public deployment still needs resource limits, authentication, spend controls and asynchronous job handling.
- Immediate remote-file deletion can fail. The adapter must surface that failure and the configured one-hour expiry remains the documented fallback.

## Acceptance

- Existing OpenCV API callers and benchmark path continue to work unchanged.
- Explicit SAM calls use the documented SAM 3.1 request and parser, map results onto source PTS, and produce the same trace/overlay/measurement contract.
- Provider failures never silently switch providers and never replace a previous successful run.
- Offline tests exercise success and failure mapping without any live Meta request.
- Docs distinguish implemented request plumbing from unverified real SAM behavior.

## Official references

- [SAM prompts and video tracking](https://dev.meta.ai/docs/sam/segmenting)
- [Official SAM parser libraries](https://dev.meta.ai/docs/sam/client-libraries)
- [File expiration and deletion](https://dev.meta.ai/docs/file-handling)
- [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
