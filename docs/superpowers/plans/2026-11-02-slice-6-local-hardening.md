# Slice 6 Local API Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent caching of private observation API responses and document the boundary between local cleanup and future hosted retention.

**Architecture:** Add a small ASGI middleware around the existing FastAPI app. It adds `Cache-Control: no-store` to responses whose path is `/api/observations` or a child path, including errors and file responses. Keep the existing temporary-directory lifecycle unchanged.

**Tech Stack:** FastAPI/Starlette ASGI middleware, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-02-slice-6-local-hardening-design.md`

## Global Constraints

- Upload limits remain 100,000,000 bytes and 30 seconds.
- Source videos, traces, and overlays remain in the app-owned temporary directory and are removed on process shutdown.
- No public deployment, hosted provider call, or paid call is part of this slice.
- `no-store` does not provide authentication, user isolation, resource limits, or a hosted retention policy.

## Review Focus

- Observation route matching must include `/api/observations` and its children but exclude similarly prefixed unrelated paths.
- Error responses, including upload middleware rejections, must also receive `no-store`.
- Overlay `FileResponse` must receive the same header as JSON responses.
- `/health` must remain outside observation data policy.
- Existing shutdown cleanup must continue deleting only app-owned temporary media.

## Decision Audit Trail

- Keep process-lifetime cleanup instead of a one-hour timer: active tracking and overlay downloads can race expiry; current shutdown cleanup is already tested.
- Apply one path-scoped middleware instead of adding headers route-by-route: this covers success and framework errors consistently. Register it outside `UploadBodyLimit` so its early 413 response is covered.
- Use patch version `0.6.1.0`: this hardens existing API behavior without adding a user workflow.
- Defer hosting, authentication, aggregate quotas, and hosted retention values until the deployment target is selected; this change must not be described as public-deployment approval.

---

### Task 1: Apply no-store policy and document local retention

**Files:**
- Modify: `services/api/src/kineticproof_api/main.py`
- Test: `services/api/tests/test_tracking.py`
- Test: `services/api/tests/test_physics_api.py`
- Modify: `docs/API_CONTRACTS.md`
- Modify: `docs/SECURITY_AND_RISKS.md`
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `docs/PROGRESS.md` after verification

**Interfaces:**
- Preserve all existing API request/response bodies and status codes.
- Add one ASGI middleware that applies `Cache-Control: no-store` to observation API response starts.
- Register that middleware outside `UploadBodyLimit` so early upload rejections also receive the header.

- [x] Add tests for a successful observation JSON response, an observation error, an overlay response, and `/health` exclusion; include a request rejected by the upload body limit.
- [x] Run the focused tests and confirm the new assertions fail before middleware is added.
- [x] Implement the smallest middleware that sets the header on `/api/observations` and `/api/observations/...` responses, including errors.
- [x] Update API/security docs to describe process-lifetime local retention and list authentication/ownership, aggregate storage/concurrency limits, and host-specific retention as pre-deployment requirements.
- [x] Bump `VERSION` from `0.6.0.0` to `0.6.1.0` and add a matching patch entry to `CHANGELOG.md`.
- [x] Run `uv run --offline --project services/api pytest -c services/api/pyproject.toml services/api/tests -q` and `git diff --check`.
- [x] Update `docs/PROGRESS.md` with exact local verification evidence only.

**Verification:** The API suite passes; observation responses carry `Cache-Control: no-store`; `/health` does not; shutdown cleanup test remains green; `git diff --check` is clean.
