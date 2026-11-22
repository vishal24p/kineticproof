# KineticProof 2.0 — product and implementation documentation (v2)

**Mission:** Make real, low-cost physics experiments investigable with everyday materials and a phone: plan a question, gather genuine observations, derive measurements with transparent algorithms, judge quality and uncertainty, compare evidence against a reference/theory, and propose the next experiment. The pendulum is the **first demonstration**, not the product's identity or permanent limitation.

**Implementation strategy:** Build a complete provider-agnostic pipeline using a genuinely runnable open-source tracking method/model first. Integrate hosted Meta SAM 3.1 and Muse Spark as a **later provider migration/extension**, not a blocker to implementation. Never misrepresent open-model outputs as Meta outputs; the submitted project must genuinely use Meta products, and its value must be demonstrated with real evidence.

**Where to start:** `AGENTS.md` -> `docs/00_INDEX.md` -> `docs/PRODUCT.md` -> `docs/WORKFLOWS.md` -> `docs/ARCHITECTURE.md` -> `docs/IMPLEMENTATION.md`. Read workstream-specific documents before changing that area. No single document is intended to contain everything.

**Project status:** Local API upload, OpenCV CSRT trace and overlay, pendulum measurement with JSON/CSV evidence, and template next-trial planning are implemented and tested with synthetic evidence. Explicit SAM and Muse adapters have offline tests only. Web remains a bootstrap. Authentic footage, tracking and measurement accuracy, benchmarks, deployment, and hosted Meta compatibility, entitlement, quality, latency and cost remain unverified.

## Implemented path and evidence status

The local path is: web bootstrap -> FastAPI upload and tracking API -> app-owned temporary media and in-process observation state -> OpenCV CSRT trace -> pendulum measurement and JSON/CSV evidence. The SAM and Muse adapters are explicit options with offline tests only; hosted behavior and public deployment are unverified. See [architecture](docs/ARCHITECTURE.md) for boundaries, [evaluation](docs/EVALUATION.md) for the benchmark protocol, and [data and annotation](docs/DATA_AND_ANNOTATION.md) for collection and labeling.

| Evidence | Current count/status |
|---|---:|
| Verified dataset clips | 0 |
| Independent reference labels | 0 |
| Benchmark runs/results | 0 |
| Benchmark metrics | Unavailable |

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

The health endpoint returns `{"status":"ok"}`. Local upload, tracking, trace, overlay and period measurement endpoints are described in [API contracts](docs/API_CONTRACTS.md).

OpenCV CSRT is the default tracking provider. The API also has an explicit SAM 3.1 path: set `MODEL_API_KEY` in the API process environment, upload only a permitted clip, then request `provider=meta_sam` with the same first-frame ROI. Do not commit the key. SAM uploads are requested to expire after one hour and are deleted after the response is parsed; no live SAM call or result has been verified. The endpoint may incur Meta charges, so use it only after confirming account access and spend authorization.

PowerShell example, using an observation ID returned by the local upload endpoint:

```powershell
$observationId = '<observation ID from upload>'
$roi = @{ x = 120; y = 80; width = 40; height = 40 } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/observations/$observationId/tracking?provider=meta_sam" `
  -ContentType 'application/json' -Body $roi
```

If `MODEL_API_KEY` is absent, this request returns 503 before any remote upload. SAM errors return 502 without falling back to OpenCV; omit the query parameter to use the offline OpenCV path.

Next-trial planning uses a completed observation trace. `POST /api/observations/{id}/next-trial` defaults to the offline `template` provider and needs no key. Send pendulum context, motion axis, and optional manual references/gravity; the response separates freshly computed local measurements from one suggestion. See [request example, exact fields and errors](docs/API_CONTRACTS.md#implemented-next-trial-planning-api-only).

Hosted Muse requires explicit `?provider=meta_muse` and `MODEL_API_KEY`. It sends context (including question/hypothesis text) and only measurement status, period, cycle MAD, valid-frame fraction, and warnings to Meta; observation IDs and provenance are not sent as separate fields. Question and hypothesis text is forwarded verbatim and may contain identifying information, so keep personal data and secrets out of it. Missing key returns 503; provider/response-validation errors return 502 with no automatic retry or template fallback. The request uses `store=false`; provider retention and live behavior are unverified. Confirm account access and spend authorization before a hosted call. No live or paid Muse request has been made. Planning is stateless and API-only; no experiment record or conversation is stored and the web UI has no planning controls.

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
