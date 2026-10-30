# Implementation plan — tasks to execute without recurring permission prompts

## Slice 0 — local repository scaffolding
Create the public GitHub repo (no secrets/private footage), Python `uv` API, frontend workspace and basic CI. Document local start/check commands. Codex Cloud setup is deferred and does not block implementation. Acceptance: the API and web app boot locally and CI runs their tests, lint and build.

## Slice 1 — authentic video through open tracking (first priority)
Video validator -> safe temporary storage -> media timestamps -> OpenCV baseline provider -> provider-neutral trace with missing-frame flags -> saved/inspectable overlay. Use real authorized sample or clearly synthetic fixture for plumbing. Acceptance: repeatable timestamped output on a consented clip and explicit failures.

## Slice 2 — physics and evidence
**Status:** Implementation complete (Oct 28, 2026). Authentic validation remains pending a consented clip and independently timed events.
Trajectory extraction -> cycle detection -> multi-cycle period -> uncertainty estimate -> reference/theory separation -> CSV/JSON evidence and quality warnings. Unit tests and independent manual timing. Acceptance: real calculation with traceable inputs and no hidden interpolation.

## Slice 3 — web MVP
Setup/recording instructions; upload/target select; track review; evidence; next-trial prompt. Thin Next.js frontend, minimal accessible design. Acceptance: complete real open-stack user journey in deployed demo.

## Slice 4 — experimental benchmark
Record permitted home pendulum videos (clean/clutter/moving background), annotate independent reference cycles, run OpenCV baseline and optional open model, publish denominators and failures. Freeze test split before comparison.

## Slice 5 — Meta migration
**Status:** Optional SAM 3.1 API adapter implemented locally; no hosted calls or real SAM results verified. OpenCV remains the default and SAM errors do not fall back silently. Next, validate SAM on permitted footage after confirming account access and spend authorization; compare with OpenCV using independent labels. Muse is next after SAM validation. Do not claim Meta value until measured.

## Slice 6 — hardening and submission
Cloud-host working link; secrets/retention/security/reproducibility; public GitHub README with architecture and benchmarks; a real three-minute narrated demo hosted at public video URL; answer Meta relevance and user problem in portal before deadline.

**Schedule:** Oct 27–28 slices 0–2; Oct 29–31 slices 3–4; Nov 1–3 slice 5 and final evaluations; Nov 4 quality/release/submission margin. These are targets, not claims, and can be reordered with evidence. Record state in `PROGRESS.md`.
