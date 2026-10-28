# Slice 3 Web MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one complete, local-first pendulum investigation journey from video upload through inspectable measurement evidence and a deterministic next-trial prompt.

**Architecture:** Keep the API unchanged and call its existing contracts through a Next.js same-origin rewrite to the localhost FastAPI service. Keep one guided workspace in the existing app, with local component state and temporary browser object URLs; observations remain process-local.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Biome 2, Playwright Test; FastAPI contracts already implemented.

**Spec:** `docs/superpowers/specs/2026-10-28-slice-3-web-mvp-design.md`

## Global Constraints

- API remains local and bound to localhost; no public deployment in this slice.
- Upload limit stays 100,000,000 bytes and 30 seconds; accepted formats stay MP4/MOV per API contract.
- Use OpenCV CSRT outputs honestly; label provider and preserve partial/gap/insufficient states.
- Encode annotated MP4 overlays with browser-playable VP9 (`VP90`) because the existing `mp4v` overlay is rejected by Chromium; preserve the `video/mp4` route and add no codec dependency.
- Manual reference event time and uncertainty are entered independently from video PTS; scrubbed video frame supplies evidence index only.
- No fabricated measurements, persistence, auth, or new provider. Playwright Test is the single user-approved development dependency for a repeatable frontend regression gate.
- Keep user media local; use synthetic clips for verification and do not commit video files.

## Review Focus

- API unavailable or process restart: show actionable error and explain local observation loss; verify upload/track/measure errors do not look successful.
- Unsupported, oversized, or over-duration media: show the API failure and allow replacement; verify the real rejected response path.
- Poor or partial target track: allow ROI reselection/rerun and preserve prior successful output on failed rerun; verify status and recovery controls.
- Gaps or insufficient cycles: show available trace and warnings while leaving measured period absent; verify no result is invented.
- Manual reference/theory inputs: manual timestamp must remain distinct from scrubbed frame PTS, and theory only appears when length and gravity are both valid; verify request payload and rendered separation.

---

### Task 1: Local API connection and workspace shell

**Files:**
- Modify: `apps/web/next.config.ts`
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/globals.css`
- Create: `apps/web/src/app/workspace.tsx`

**Interfaces:**
- Consume existing `/health` and `/api/observations` through same-origin Next.js rewrites (`/api/health` maps to FastAPI `/health`; observation routes preserve `/api/...`).
- `page.tsx` renders the client `Workspace` entry point; workspace owns the guided stages and transient request state.

- [x] Add rewrites from `/api/health` to FastAPI `/health` and `/api/:path*` to the same FastAPI path, using `KINETICPROOF_API_ORIGIN` (default `http://127.0.0.1:8000`) without adding API CORS policy.
- [x] Build the responsive four-stage workspace shell and local-session notice; keep copy aligned with `docs/UI_UX.md`.
- [x] Run `npm --prefix apps/web run lint` and `npm --prefix apps/web run build`; verify `/api/health` reaches FastAPI when both local servers run.

### Task 2: Upload, target selection, tracking and recovery

**Files:**
- Modify: `apps/web/src/app/workspace.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `services/api/src/kineticproof_api/tracking.py`
- Modify: `services/api/tests/test_tracking.py`
- Modify: `docs/API_CONTRACTS.md`

**Interfaces:**
- Upload: `POST /api/observations` multipart `file`; response supplies `observation_id`, dimensions, duration and frame count.
- Track: `POST /api/observations/{id}/tracking` JSON `{x,y,width,height}`; then read `/tracks` and `/overlay`.
- API keeps previous successful tracking pair after a failed rerun.
- Overlay remains served as `video/mp4`; encode it using OpenCV's `VP90` MP4 writer so Chromium can inspect it in-page.

- [x] Add labelled video upload with client-side format/size feedback and render server validation errors; verify unsupported file and API 413/415 paths.
- [x] Add keyboard-operable video frame ROI selection; convert its displayed rectangle to integer source pixels and reject empty/out-of-bounds boxes before submit.
- [x] Submit tracking, fetch trace and annotated overlay; show loading, success, partial, and failure feedback with OpenCV provider identity.
- [x] Allow target reselection and rerun; retain and display last successful trace/overlay if rerun fails.
- [x] Change overlay encoding from `mp4v` to `VP90` and add a focused API regression asserting the generated MP4 contains a browser-decodable video stream.
- [x] Document overlay video codec and verify through generated synthetic media: upload → choose target → track → inspect overlay; also verify invalid ROI and failed/partial track feedback. Exercise proxy pass-through with a valid synthetic MP4 close to (but within) the 100,000,000-byte file cap when practical.

### Task 3: Axis selection, measurement and evidence

**Files:**
- Modify: `apps/web/src/app/workspace.tsx`
- Modify: `apps/web/src/app/globals.css`
- Create: `apps/web/src/app/measurement-panel.tsx`
- Create: `apps/web/src/app/trajectory-plot.tsx`

**Interfaces:**
- `MeasurementPanel` consumes `observationId`, completed `TrackResult`, and overlay URL from the workspace; it owns measurement inputs/results and passes projected trace samples to `TrajectoryPlot`.
- Measure: `POST /api/observations/{id}/measure?format=json|csv` with required normalized direction `{motion_axis:{x,y}}`, optional independent `reference_events`, and optional paired `length_m`/`gravity_m_s2`.
- Trace fields and evidence response follow `docs/API_CONTRACTS.md`.

- [x] Add keyboard-operable motion-axis drawing in `MeasurementPanel` and map the selected 2D direction to the request.
- [x] Add optional manual events with event type, independently entered timestamp and uncertainty; scrubbed overlay frame selects only `evidence_frame_index`.
- [x] Add paired optional length/gravity controls and submit theory inputs only when both are valid.
- [x] Render trajectory projection and detected cycle picks in `TrajectoryPlot`; render measured period/MAD, manual reference and theoretical results separately, plus warnings, gaps, method and provenance in `MeasurementPanel`.
- [x] Render `insufficient_data` without a measured-period value; allow CSV download from the same request parameters and JSON evidence download.
- [x] Verify complete measure flow with a synthetic clip, including insufficient data, manual timestamp/frame distinction, and optional theory; verify export responses.

### Task 4: Next-trial prompt, finish and evidence

**Files:**
- Modify: `apps/web/src/app/workspace.tsx`
- Modify: `apps/web/src/app/measurement-panel.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`
- Modify: `docs/IMPLEMENTATION.md`

**Interfaces:**
- Next-trial content is a deterministic, clearly labeled pendulum prompt grounded in the observed workflow/limitations; no new API route or AI claim.
- `MeasurementPanel` reports completed measurement status/gaps to the workspace so the prompt can adapt deterministically.

- [x] Add the final stage with a bounded follow-up investigation prompt: advise recapture for missing/partial frames, a longer clip for insufficient cycles, and changing only pendulum length after a successful measurement; label every prompt as a suggestion, not a result.
- [x] Prevent stage panels from stretching to unrelated row heights; check keyboard flow, visible focus, labels/status announcements, contrast, and layouts at 320, 768, 1024, and 1440 px.
- [x] Run `npm --prefix apps/web run lint` and `npm --prefix apps/web run build`.
- [x] Complete one full browser journey using a synthetic local clip; verify next-trial prompts for partial/gapped, insufficient, and successful evidence; record exact commands and results in `docs/PROGRESS.md`, including limitations and unverified authentic footage/deployment.
- [x] Update README and implementation roadmap to describe the local web journey and mark Slice 3 complete; retain Slice 6 as the deployment milestone.
- [ ] Review diff for accidental media/secrets, run `git diff --check`, then use GStack ship workflow before beginning Slice 4.

### Task 5: CI regression for ambiguous tracking outcomes

**User-approved addition:** GStack coverage review found the browser regression was only in ignored local SDD artifacts (77% assessed coverage); user approved adding Playwright Test and CI.

**Files:**
- Modify: `apps/web/package.json` and lockfile
- Create: Playwright test/config for tracking timeout recovery
- Modify: `.github/workflows/ci.yml`

- [x] Add a repeatable browser test for definite 4xx retaining prior evidence, ambiguous 504 blocking measurement/exports/rerun even after late publication, and fresh-upload recovery.
- [x] Run the Playwright test locally with existing Biome lint and production build gates.
- [ ] Confirm the Playwright CI job passes after push; then run `git diff --check` and GStack ship as the final Slice 3 gate.

### Task 6: Action button hover feedback

**User-approved review fix:** GStack design review found `.action-button` lacked pointer hover feedback; user chose a subtle hover color.

**Files:**
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/tests/tracking-recovery.spec.ts`

- [x] Add an enabled-button hover tint from the existing teal palette and a browser assertion that verifies the color changes on hover while disabled buttons stay unchanged.
- [x] Run the focused Playwright test, lint, and production build.
