# KineticProof 2.0 — product and implementation documentation (v2)

**Mission:** Make real, low-cost physics experiments investigable with everyday materials and a phone: plan a question, gather genuine observations, derive measurements with transparent algorithms, judge quality and uncertainty, compare evidence against a reference/theory, and propose the next experiment. The pendulum is the **first demonstration**, not the product's identity or permanent limitation.

**Implementation strategy:** Build a complete provider-agnostic pipeline using a genuinely runnable open-source tracking method/model first. Integrate hosted Meta SAM 3.1 and Muse Spark as a **later provider migration/extension**, not a blocker to implementation. Never misrepresent open-model outputs as Meta outputs; the submitted project must genuinely use Meta products, and its value must be demonstrated with real evidence.

**Where to start:** `AGENTS.md` -> `docs/00_INDEX.md` -> `docs/PRODUCT.md` -> `docs/WORKFLOWS.md` -> `docs/ARCHITECTURE.md` -> `docs/IMPLEMENTATION.md`. Read workstream-specific documents before changing that area. No single document is intended to contain everything.

**Project status:** Local API upload, OpenCV CSRT trace and overlay implemented and tested with synthetic media. Web remains a bootstrap. Authentic footage, tracking accuracy, benchmarks, deployment and Meta integration remain unverified.

**Hackathon:** Meta Global AI Developer Hackathon, Indie Developer track; public GitHub repository and 3-minute demo-video URLs required by the user-inspected submission form. Deadline: Nov 4, 2026, 9:00 PM US Eastern per event; re-confirm time and local conversion at submission. See `docs/HACKATHON_RULES.md` and `docs/SUBMISSION.md`.

**Non-goals for the MVP:** native mobile app, live-streaming capture, user accounts, generalized arbitrary physics interpretation, invented measurements, complex infra. Future experiments are extensibility targets; do not silently claim they work.

## Local development

Run commands from the repository root. Requirements: Python 3.12+, uv, Node.js 20.9+, and npm. Local checks used uv 0.11.28, Python 3.14.5, Node 24.14.1, and npm 11.15.0.

Install dependencies from the lockfiles:

```powershell
uv sync --locked --project services/api
npm ci --prefix apps/web
```

Start the API:

```powershell
uv run --project services/api uvicorn kineticproof_api.main:app --app-dir services/api/src --host 127.0.0.1 --port 8000
```

In another terminal, check the live endpoint and run the API suite:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
uv run --project services/api pytest -c services/api/pyproject.toml services/api/tests -q
```

The health endpoint returns `{"status":"ok"}`. Local upload, tracking, trace and overlay endpoints are described in [API contracts](docs/API_CONTRACTS.md). Measurement endpoints are not implemented yet.

Start the web app in another terminal, then open [localhost:3000](http://localhost:3000):

```powershell
npm --prefix apps/web run dev
```

Check the frontend production build and lint:

```powershell
npm --prefix apps/web run build
npm --prefix apps/web run lint
```

The web app uses Biome for linting and formatting checks.

The landing page is a bootstrap placeholder. No upload or tracking controls are available yet.
