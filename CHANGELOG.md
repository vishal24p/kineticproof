# Changelog

## [0.7.0.0] - 2026-11-02

### Security

- Add anonymous session bootstrap and signed HttpOnly cookie ownership for uploaded observations.
- Require the owning session for upload, tracking, tracks, overlay, measurement and next-trial routes; keep session and observation responses no-store.
- Document session limits and hosted TLS cookie configuration. The UI bootstrap remains a separate follow-up.

## [0.6.1.0] - 2026-11-02

### Security

- Prevent caching of observation API responses, including errors and overlay files; document process-lifetime local retention and hosted deployment requirements.

## [0.6.0.0] - 2026-11-02

### Added

- API-only next-trial planning from existing traces, with a default offline template and one controlled suggestion separate from locally computed measurements.
- Explicit `meta_muse` adapter with minimized context/measurement payload, strict suggestion validation, no retries or automatic fallback, and no planning persistence or web UI.
- Offline synthetic-trace and fake-client tests; hosted Muse compatibility, entitlement, scientific quality, latency and cost remain unverified. No hosted or paid request was made.

## [0.5.0.0] - 2026-10-30

### Added

- Select Meta SAM 3.1 explicitly for tracking; OpenCV remains the default and selected-provider failures do not fall back.
- Map SAM boxes to source-timed traces and local overlays, with one-hour remote-file expiry and deletion attempts.
- Add offline adapter/API tests using synthetic media and parser fixtures; no hosted calls or SAM measurements were made.

## [0.3.0.0] - 2026-10-28

### Added

- Complete a local video investigation from upload and target selection through tracking, period measurement, and JSON or CSV evidence export.
- Review annotated tracks and motion plots, add independent manual timing references, and get a controlled prompt for the next trial.
- Keep uncertain tracking failures from publishing stale measurements, with a browser regression test in CI.

### Changed

- Bind local web servers to loopback and clarify the effective pendulum length used for theory comparisons.

## [0.2.0.0] - 2026-10-28

### Added

- Measure periods from tracked video with an explicit motion axis, per-cycle evidence, JSON or CSV output, and separate manual and theoretical references.
- Inspect detected turning points, source timestamps, missing-frame warnings, detector settings, and measurement provenance.

### Fixed

- Reject small shoulder peaks using bounded topographic prominence and prevent invalid results from extreme theory inputs.
- Keep insufficient-data CSV exports header-only and report gaps even when enough cycles remain for a measurement.

## [0.1.1.0] - 2026-10-28

### Added

- Use the local API to upload a short MP4 or MOV clip, provide a target box from its first frame, and retrieve a timestamped OpenCV trace plus annotated video. See [API contracts](docs/API_CONTRACTS.md).
- See source timestamps and explicit tracking failures in the trace; failed reruns preserve the last successful result.
- Validate upload size, duration, media timestamps, and video container brands before accepting a clip.

## [0.1.0.0] - 2026-10-27

### Added

- Start KineticProof locally with a web landing page and API health check.
- Run API tests, frontend lint, and the web production build through GitHub Actions on pushes and pull requests.
