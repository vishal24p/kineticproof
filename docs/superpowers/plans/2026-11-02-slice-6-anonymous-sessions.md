# Anonymous Browser Session Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict each uploaded observation to the anonymous browser session that created it.

**Architecture:** FastAPI establishes an opaque signed session cookie through `POST /api/session`, before the client uploads media. The API stores each session ID on in-memory observations and checks ownership in the shared lookup. The Slice 3 UI call and Next.js rewrite smoke test are a dependent follow-up PR, keeping this API PR separate.

**Tech Stack:** FastAPI, Starlette responses, Python standard library, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-slice-6-anonymous-sessions-design.md`

## Global Constraints

- No accounts, persistent session store, CORS change, TTL cleanup, quotas, or deployment.
- Existing observation request/response JSON stays unchanged.
- `/health` stays public. Observation and session API responses use `Cache-Control: no-store`.
- Process-lifetime media storage and shutdown cleanup stay unchanged.
- Hosted TLS deployments must set `KINETICPROOF_COOKIE_SECURE=1`.
- Keep API and UI changes in separate dependent PRs. This plan covers API PR only.

## Files

- Modify `services/api/src/kineticproof_api/main.py`: key setup, cookie validation/issuance, session endpoint, observation owner check.
- Modify `services/api/tests/test_tracking.py`: session bootstrap, upload, ownership, and cookie behavior.
- Modify `services/api/tests/test_physics_api.py` and `test_planning_api.py`: seed owned observations and use authenticated clients.
- Modify `docs/API_CONTRACTS.md` and `docs/SECURITY_AND_RISKS.md`: endpoint and limits.
- Modify `VERSION`, `CHANGELOG.md`, and `docs/PROGRESS.md` after verification.

## Task 1: Add session bootstrap and observation ownership

1. Add tests for `POST /api/session`: it issues an opaque cookie with HttpOnly, SameSite=Strict, Path=/api; no Domain or expiry; Secure only when `KINETICPROOF_COOKIE_SECURE=1`; valid repeat calls preserve the cookie; malformed cookies are replaced. Assert response body has no session ID and response is no-store.
2. Add tests asserting observation routes without a valid session return 401, foreign session gets 404, own session can access tracking, tracks, overlay, measure, and next-trial, and `/health` remains public.
3. Add upload tests: upload uses pre-established owner, successful uploads do not rotate the cookie, and rejected uploads create no observation or leftover media.
4. Update direct observation fixtures and existing unknown-observation tests to send a valid session where they intend to exercise 404/409/other route behavior.
5. Run the focused tests and confirm new behavior fails before implementation.
6. In app lifespan, create one random 32-byte signing key. Validate signed cookie format (`token_urlsafe(32)` ID plus 64-character hex HMAC-SHA256) with `hmac.compare_digest`.
7. Add `POST /api/session`: preserve a valid cookie; otherwise mint a random ID, sign it, and set `kineticproof_session` with HttpOnly, SameSite=Strict, Path=/api, and Secure only when the env value is `1`. Never expose the ID in the body.
8. Add the session ID to `Observation`; require valid cookie on upload and every observation route. Return 401 for missing/invalid cookie and 404 for an observation owned by another session.
9. Extend no-store middleware to cover `/api/session`; keep `/health` outside it.
10. Update API and security docs with cookie setup, anonymous bearer-session limitations, process lifetime, and remaining public-host blockers.
11. Bump to `0.7.0.0` and add the changelog entry.
12. Run focused tests, full API suite, and `git diff --check`; record exact evidence in `docs/PROGRESS.md`.

**Verification:** The full offline API suite passes. Session bootstrap returns no identifier; ownership blocks cross-session access; `/health` stays public; sensitive API responses are no-store; diff check is clean.

## Follow-up PR (not this plan)

Update the existing Slice 3 UI branch to call `POST /api/session` before enabling upload. Use its same-origin `/api` rewrite, then verify in a local browser that FastAPI's cookie is stored and returned. Do not claim this proxy behavior verified by API tests.

## Decision Audit Trail

- Use process-local HMAC signing instead of a session table: existing observations are process-local and vanish at restart.
- Establish a cookie through a bootstrap endpoint before upload, per the approved design.
- Keep API and UI PRs separate: narrow diffs; UI PR depends on the API endpoint.
- Use `0.7.0.0` for the new API ownership capability.
- Leave quotas, hosted retention, and deployment out; requirements depend on host and traffic.
