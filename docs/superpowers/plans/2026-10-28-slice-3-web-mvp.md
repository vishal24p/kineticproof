# Slice 3 Web MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one complete, local-first pendulum investigation journey from video upload through inspectable measurement evidence and a deterministic next-trial prompt.

**Architecture:** Keep the API unchanged and call its existing contracts through a Next.js same-origin rewrite to the localhost FastAPI service. Keep one guided workspace in the existing app, with local component state and temporary browser object URLs; observations remain process-local.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Biome 2; FastAPI contracts already implemented. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-28-slice-3-web-mvp-design.md`

## Global Constraints

- API remains local and bound to localhost; no public deployment in this slice.
- Upload limit stays 100,000,000 bytes and 30 seconds; accepted formats stay MP4/MOV per API contract.
- Use OpenCV CSRT outputs honestly; label provider and preserve partial/gap/insufficient states.
- Manual reference event time and uncertainty are entered independently from video PTS; scrubbed video frame supplies evidence index only.
- No fabricated measurements, persistence, auth, new provider, or new dependency.
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

**Interfaces:**
- Upload: `POST /api/observations` multipart `file`; response supplies `observation_id`, dimensions, duration and frame count.
- Track: `POST /api/observations/{id}/tracking` JSON `{x,y,width,height}`; then read `/tracks` and `/overlay`.
- API keeps previous successful tracking pair after a failed rerun.

- [ ] Add labelled video upload with client-side format/size feedback and render server validation errors; verify unsupported file and API 413/415 paths.
- [ ] Add keyboard-operable video frame ROI selection; convert its displayed rectangle to integer source pixels and reject empty/out-of-bounds boxes before submit.
- [ ] Submit tracking, fetch trace and annotated overlay; show loading, success, partial, and failure feedback with OpenCV provider identity.
- [ ] Allow target reselection and rerun; retain and display last successful trace/overlay if rerun fails.
- [ ] Verify with a generated synthetic clip: upload → choose target → track → inspect overlay; also verify invalid ROI and failed/partial track feedback. Exercise proxy pass-through with a valid synthetic MP4 close to (but within) the 100,000,000-byte file cap when practical.

### Task 3: Axis selection, measurement and evidence

**Files:**
- Modify: `apps/web/src/app/workspace.tsx`
- Modify: `apps/web/src/app/globals.css`

**Interfaces:**
- Measure: `POST /api/observations/{id}/measure?format=json|csv` with required normalized direction `{motion_axis:{x,y}}`, optional independent `reference_events`, and optional paired `length_m`/`gravity_m_s2`.
- Trace fields and evidence response follow `docs/API_CONTRACTS.md`.

- [ ] Add keyboard-operable motion-axis drawing and map the selected 2D direction to the request.
- [ ] Add optional manual events with event type, independently entered timestamp and uncertainty; scrubbed overlay frame selects only `evidence_frame_index`.
- [ ] Add paired optional length/gravity controls and submit theory inputs only when both are valid.
- [ ] Render trajectory projection and detected cycle picks, measured period/MAD, manual reference and theoretical results separately, plus warnings, gaps, method and provenance.
- [ ] Render `insufficient_data` without a measured-period value; allow CSV download from the same request parameters and JSON evidence download.
- [ ] Verify complete measure flow with a synthetic clip, including insufficient data, manual timestamp/frame distinction, and optional theory; verify export responses.

### Task 4: Next-trial prompt, finish and evidence

**Files:**
- Modify: `apps/web/src/app/workspace.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`

**Interfaces:**
- Next-trial content is a deterministic, clearly labeled pendulum prompt grounded in the observed workflow/limitations; no new API route or AI claim.

- [ ] Add the final stage with a bounded follow-up investigation prompt and label it as a suggested plan, not a measured result.
- [ ] Check keyboard flow, visible focus, labels/status announcements, contrast, narrow viewport layout, and all loading/error/partial/insufficient states.
- [ ] Run `npm --prefix apps/web run lint` and `npm --prefix apps/web run build`.
- [ ] Complete one full browser journey using a synthetic local clip; record exact commands and results in `docs/PROGRESS.md`, including limitations and unverified authentic footage/deployment.
- [ ] Review diff for accidental media/secrets, run `git diff --check`, then use GStack ship workflow before beginning Slice 4.

