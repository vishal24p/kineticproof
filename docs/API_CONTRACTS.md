# Internal web/backend contracts

## Implemented locally — Slice 1

These endpoints are synchronous, local, and temporary. Run one API process bound to localhost. No accounts, deployment, job queue or persistent storage is implemented. Uploaded media, traces and overlays disappear on process shutdown; IDs are not authorization and this API must not be exposed publicly.

- `POST /api/observations`: multipart `file`, MP4/MOV only with supported container brand (`isom`, `iso2`, `mp41`, `mp42`, QuickTime, AVC, AV1, or M4V), at most 100,000,000 bytes and 30 seconds. Returns `{observation_id,duration_seconds,width,height,frame_count}`. Source PTS must be available and increasing; at least two frames are required. Duration is the last source PTS minus the first.
- `POST /api/observations/{id}/tracking`: JSON `{x,y,width,height}`, strict integer pixels within the first frame. Runs OpenCV CSRT with default parameters; returns `{status,frame_count}` after trace and overlay both succeed. Status is `succeeded` or `partial` if updates fail. No provider selection or Meta usage is implemented.
- `GET /api/observations/{id}/tracks`: returns the [v1 TrackResult](TRACKING_CONTRACT.md#implemented-local-v1-mapping).
- `GET /api/observations/{id}/overlay`: serves the completed overlay as `video/mp4`.

Unknown observation: 404. Known observation without a completed result: 409. Invalid ROI/video or unavailable source PTS: 422. Overlay writer/server failure: 500. Uploads exceeding limits: 413; unsupported extension/container: 415.

Reruns publish a matching trace/overlay pair only after both outputs succeed. Failed reruns preserve the previous pair and remove incomplete new media. A `partial` trace is a completed result. Superseded successful overlay files remain private until app shutdown so ongoing downloads can finish. This temporary retention and synchronous work are local-development limits; resource controls are required before public deployment.

## Future logical design — not implemented

`POST /api/experiments` create an experiment draft with kind, variables, hypotheses and consent state.
Observation calibration/consent metadata, provider selection (`opencv|open_model|meta_sam`) and asynchronous jobs remain future extensions. No Meta required for the default.
`GET /api/jobs/{id}` status+error.
`POST /api/observations/{id}/measure` deterministic physics analysis; output values + validity warnings + provenance + reference/theory comparison; no model-authoritative physics.
`GET /api/experiments/{id}/evidence` original/overlay plots+cycle picks+export; `POST /api/experiments/{id}/next-trial` generate grounded next trial via templates or selected validated planner.

These future routes are candidates. Ownership/privacy and budget controls, idempotent jobs and bounded cleanup are required before public deployment. Version schemas once implemented; never copy unverified Meta request schema into public API.
