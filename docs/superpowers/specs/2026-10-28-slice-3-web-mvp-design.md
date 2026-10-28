# Slice 3 web MVP design

## Intent

Give a learner one complete local journey from a pendulum video to inspectable measurement evidence and a grounded next-trial prompt. The UI must show real API results and explicit failures; it must never make up tracking or measurement data.

## Scope

- One guided workspace with four stages: Investigate, Observe, Evidence, Next trial.
- Supported pendulum recording instructions, including framing, lighting, safety and a visible reference for scale where relevant.
- Upload MP4/MOV using the existing 100,000,000-byte and 30-second API limits.
- Select the first-frame target with a drag rectangle and submit it as the initial ROI.
- Run OpenCV CSRT tracking; show provider identity, status, and the annotated overlay.
- Let users reject a poor track, select a corrected initial target, and rerun tracking while preserving any prior successful result if the rerun fails.
- Draw the motion axis on the video; send the resulting explicit 2D direction to `/measure`.
- Show a trajectory plot with detected cycle picks, measured period/MAD, manual reference inputs when supplied, theory inputs when supplied, warnings and provenance distinctly.
- For manual reference events, let users scrub the annotated video to select an evidence frame, then independently enter the event type, manual timestamp, and timing uncertainty. Do not derive manual reference time from video PTS.
- Allow JSON or CSV evidence export from the existing measurement endpoint.
- Give a deterministic, clearly labeled pendulum next-trial prompt based on current evidence/limitations.
- Provide loading, API-unavailable, invalid upload, tracking failure/partial, insufficient-cycle, and measurement-error states.
- Responsive, keyboard-accessible labels and controls; local frontend/API only.

## Non-goals

- Public deployment, authentication, accounts, persistent projects, jobs, database, other experiment types, Meta integration, AI-generated explanations, or fabricated/demo measurements.
- Replacing or changing the API schemas unless implementation reveals a blocking contract defect.

## Approaches considered

1. **One guided workspace (chosen):** preserve the short in-memory workflow in one place and progressively reveal the next stage. This fits the API’s process-local observation IDs and reduces navigation/state complexity.
2. **Separate pages:** clearer route boundaries, but adds navigation/state handling without persistence and risks losing the active workflow on refresh.

## Constraints and decisions

- Use current Next.js, React, Tailwind and Biome setup; no new dependencies unless an existing platform capability proves insufficient.
- Use a local Next.js API proxy/rewrite or an equally simple same-origin arrangement to connect to FastAPI. Keep the API bound to localhost; do not expose it publicly.
- Reuse existing response contracts in `docs/API_CONTRACTS.md` and `docs/UI_UX.md`.
- Uploads/observations vanish when the API process stops. State this near the workflow and treat refresh/restart as a recoverable local-session loss.
- Manual reference events and theory inputs remain optional, matching the API. Clearly distinguish entered reference values, measured values, and calculated theory.
- No real footage is committed or uploaded by automated UI checks.

## Open to implementation

- Exact layout, copy and small interaction details, within the agreed one-workspace flow and existing visual/accessibility guidance.
- Keep implementation concentrated in the current app page and existing app styles unless a genuinely reusable component is needed.

## Acceptance

- A user can complete upload → target selection → tracking/reselection → axis selection → measurement → evidence inspection/export → next-trial prompt against a locally running API.
- Every asynchronous action has visible loading and failure feedback.
- Partial tracking and insufficient measurement are shown honestly without suppressing available evidence or presenting null values as results.
- Keyboard and narrow-screen users can operate the workflow.
- Local lint, production build, and relevant browser/API integration checks pass; checks use synthetic fixtures only.
- No public deployment or real footage operation occurs in this slice.
