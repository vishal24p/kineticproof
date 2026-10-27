# Internal web/backend contracts — logical design, not deployed endpoints

`POST /api/experiments` create an experiment draft with kind, variables, hypotheses and consent state.
`POST /api/observations` upload a bounded consented video + effective length and calibration metadata; returns observation/job ids.
`POST /api/observations/{id}/tracking` choose `opencv|open_model|meta_sam` and target selection; async if long-running. No Meta required for default.
`GET /api/jobs/{id}` status+error; `GET /api/observations/{id}/tracks` returns `TRACKING_CONTRACT.md` results.
`POST /api/observations/{id}/measure` deterministic physics analysis; output values + validity warnings + provenance + reference/theory comparison; no model-authoritative physics.
`GET /api/experiments/{id}/evidence` original/overlay plots+cycle picks+export; `POST /api/experiments/{id}/next-trial` generate grounded next trial via templates or selected validated planner.

These routes are candidates. Backend validates size/duration/media type, secrets, ownership/privacy and budget; idempotent jobs and cleanup are required before public deployment. Version schemas once implemented; never copy unverified Meta request schema into public API.
