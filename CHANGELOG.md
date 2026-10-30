# Changelog

## [0.5.0.0] - 2026-10-30

### Added

- Select Meta SAM 3.1 explicitly for tracking; OpenCV remains the default and selected-provider failures do not fall back.
- Map SAM boxes to source-timed traces and local overlays, with one-hour remote-file expiry and deletion attempts.
- Add offline adapter/API tests using synthetic media and parser fixtures; no hosted calls or SAM measurements were made.

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
