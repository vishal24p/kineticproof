# Slice 0 — Local Repository Bootstrap Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan task-by-task.

**Goal:** Make the local KineticProof repository boot as a minimal Next.js web app and FastAPI service, with repeatable checks and CI.

**Architecture:** Keep the existing `apps/web` and `services/api` layout. Add one FastAPI health endpoint and one small Next.js landing page; run independent Python and Node checks in GitHub Actions.

**Tech Stack:** Python 3.12+, uv, FastAPI, pytest, httpx, Next.js, React, TypeScript, npm, GitHub Actions.

## Constraints

- Keep the open-source tracking pipeline independent of Meta access.
- Do not commit secrets or private video; retain the existing `.env.example` and `.gitignore` protections.
- Public repository creation is an external step; do not publish or choose an owner/repository name without the user.

---

## Task 1: Bootable local web and API scaffold

**Files:**
- Create: `services/api/pyproject.toml`, `services/api/uv.lock`
- Create: `services/api/src/kineticproof_api/__init__.py`, `services/api/src/kineticproof_api/main.py`
- Create: `services/api/tests/test_health.py`
- Create: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/tsconfig.json`, `apps/web/next.config.ts`, `apps/web/app/layout.tsx`, `apps/web/app/page.tsx`, `apps/web/app/globals.css`
- Modify: `README.md`, `docs/PROGRESS.md`

**Interfaces:**
- API exports FastAPI app as `kineticproof_api.main:app`; `GET /health` returns JSON `{"status":"ok"}`.
- Web app supports `npm run dev` and `npm run build`.

- [ ] **Step 1: Add API project metadata and a health test** in `services/api/pyproject.toml` and `services/api/tests/test_health.py`. Declare FastAPI and Uvicorn as runtime dependencies, pytest and httpx as development dependencies, and pytest `pythonpath = ["src"]`. Test that `GET /health` returns HTTP 200 and exactly `{"status":"ok"}`.
- [ ] **Step 2: Run the test before adding the app.** Run `uv run --project services/api pytest services/api/tests/test_health.py -q`; it must fail because the API module is missing.
- [ ] **Step 3: Add the minimal FastAPI app.** Implement only `GET /health` in `services/api/src/kineticproof_api/main.py`.
- [ ] **Step 4: Generate and check the Python lockfile.** Run `uv lock --project services/api`, then `uv run --project services/api pytest services/api/tests/test_health.py -q`; expect one passing test.
- [ ] **Step 5: Scaffold the smallest Next.js TypeScript app in `apps/web`.** Landing page identifies KineticProof and says real video tracking is the next milestone; it must not imply tracking is already implemented.
- [ ] **Step 6: Install and lock frontend dependencies.** Run `npm install --prefix apps/web`.
- [ ] **Step 7: Verify both local entry points.** Run `uv run --project services/api uvicorn kineticproof_api.main:app --app-dir services/api/src --host 127.0.0.1 --port 8000` and `npm --prefix apps/web run build`; verify the API response with `Invoke-RestMethod http://127.0.0.1:8000/health`.
- [ ] **Step 8: Document exact start and check commands** in `README.md`; update `docs/PROGRESS.md` only with observed results.

## Task 2: CI for the boot checks

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- CI runs the same API test and frontend production build as the local checks.

- [ ] **Step 1: Add a GitHub Actions workflow** for pushes and pull requests, using Python 3.12 and Node 22.
- [ ] **Step 2: Run the Python API test and Next.js build** in separate jobs. Use `uv.lock` with `uv sync --locked --project services/api` and `apps/web/package-lock.json` with `npm ci`.
- [ ] **Step 3: Check workflow syntax and local command parity.** Do not claim a remote Actions run unless a push or PR actually triggers it.

## External handoff

- Public GitHub repository creation needs the user's chosen owner/name and confirmation of public visibility.
- These external steps do not block the local scaffold or open-tracking work.

## Review focus

- No token, media, or local `.env` value enters tracked files.
- Web copy does not imply video tracking is already operational.
- CI commands match documented local commands.
- API imports from the documented launch command.
