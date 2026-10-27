# Codex entrypoint — KineticProof 2.0

First read `README.md` and `docs/00_INDEX.md`. Then read only the workstream documents relevant to your current task. Don't infer the entire project from `EXPERIMENT.md`: pendulum is the first validation case, not the whole mission.

## Operating mode
- **Implement; do not stall waiting for Meta credits or SAM access.** Begin with an honestly identified open-source/OpenCV tracker and a working local/cloud-independent pipeline. Provider adapters must share `docs/TRACKING_CONTRACT.md`.
- Design for later Meta migration, but never silently substitute Meta results, present mock data as measured, or claim Meta-model usage before demonstrated.
- Meta participation requires genuine Meta AI integration before final submission; escalate only that final acceptance risk, not day-to-day implementation.
- Use existing GStack/ECC skills when they actually exist in the executing Codex environment; absence is not a blocker. Do not install arbitrary third-party agent skills or run installation scripts without review.
- Favor end-to-end vertical slices over many empty files. No needless database, mobile app, microservices, RAG or speculative features.
- Tests are expected during implementation; do not mark them passed unless run. Never invent measurements, data, licenses, costs, account entitlements or API results.
- Keep video files private, scrub personally identifying media, keep secrets out of source control; ask before paid calls, cloud deployments or destructive operations.
- Review official documentation for provider-specific contract details. Record unverified behavior explicitly.

## Task loop
1. Select the next unchecked item in `docs/IMPLEMENTATION.md`; identify the affected docs/contracts.
2. Implement a bounded vertical slice with observable acceptance criteria and tests.
3. Provide exact run evidence (or report not run), include failures and limitations.
4. Update `docs/PROGRESS.md` and `docs/DECISIONS.md` only when actual evidence or a decision changes.
5. Offer the next concrete task; do not ask what to build when the next milestone is defined.

## Required handoff format
Task completed; changed files; tested/not tested with exact commands; real evidence paths; remaining issues; next bounded task.
