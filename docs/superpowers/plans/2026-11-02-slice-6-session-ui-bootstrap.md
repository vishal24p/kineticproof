# Slice 6 UI Session Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Slice 3 browser establish its anonymous API session before it enables video upload.

**Architecture:** `Workspace` calls the existing same-origin `/api/...` rewrite with `POST /api/session` on mount. Upload remains disabled until success; failures show a retry action. The API-issued HttpOnly cookie stays browser-managed. This UI PR depends on API PR #9.

**Tech Stack:** Next.js 16, React, Playwright.

**Approved design:** API session ownership spec in PR #9: <https://github.com/vishal24p/kineticproof/pull/9>

## Scope and constraints

- Update the existing `feature/slice-3-web-mvp` branch and PR #4; keep API implementation in separate PR #9.
- Use the existing same-origin `/api/:path*` rewrite. Do not expose cookie values to JavaScript or store tokens in app state.
- Disable upload until session bootstrap succeeds; allow retry after bootstrap failure.
- Do not bump version or add a second changelog release; UI bootstrap completes the same 0.7 session-ownership release introduced by PR #9.
- Keep current observation states and request/response shapes unchanged.
- Do not change CI or Playwright server configuration. At initial verification, this branch did not contain the API endpoint, so the real proxy smoke used the API PR #9 worktree; the branch is now stacked on PR #9.

## Files

- Modify `apps/web/src/app/workspace.tsx`: bootstrap state, API call, disabled gate, retry UI.
- Modify `apps/web/src/app/observation-api.ts`: explain that a 401 means the session expired and the user must refresh/re-upload.
- Modify `apps/web/tests/tracking-recovery.spec.ts`: assert bootstrap and retry behavior.
- Record exact verification in `docs/PROGRESS.md` only if evidence changes.

## Task 1: Bootstrap browser session before upload

1. Add a Playwright test that holds `POST /api/session`, checks the upload input is disabled, releases the request, and confirms upload begins only after success. Cover a first 503 followed by retry success.
2. Implement the smallest React state and retry action in `Workspace`; keep the session identifier out of response handling and browser-readable state.
3. Explain API 401 responses as an expired local session that needs refresh and re-upload; assert the message in Playwright.
4. Run the focused Playwright suite, Biome lint, Next production build, and `git diff --check`.
5. For real proxy verification, run the API from PR #9's worktree and Next from this Slice 3 worktree. In a real browser, POST `/api/session` through Next, then request an unknown observation route through the same rewrite; expect 404 (401 would mean the cookie was not forwarded). No API or UI mocks for this smoke.
6. Record exact verification in `docs/PROGRESS.md` and commit the UI follow-up to the existing Slice 3 branch.

**Verification:** Browser test proves session setup precedes upload, retry works, and expired-session guidance is clear; real proxy smoke returns 404 for the unknown observation with the established cookie; Playwright, Biome, Next build, and `git diff --check` pass.

## Decision trail

- Reuse the existing Slice 3 PR rather than combine API and UI histories; user selected two dependent PRs.
- Keep release version at 0.7.0.0 from API PR #9; this UI follow-up does not create another release version.
- A proxy-level 404 after session creation proves the cookie was accepted and forwarded without requiring a permitted video clip.
