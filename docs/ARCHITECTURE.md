# Architecture — open-first, Meta-ready

## Data flow
Next.js web candidate -> FastAPI upload + job service -> private temporary media -> video decoding/timestamp normalization -> `TrackingProvider` -> versioned timestamped tracks -> physics measurement service -> evaluation/evidence JSON -> evidence-first web UI -> optional structured AI interpretation / next-trial explanation.

## Provider strategy
`TrackingProvider` has a stable contract and at least `OpenCVTracker` implementation first; optional open model (e.g. community YOLO segmentation or another verified licensed method) only if it offers measurable benefit and fits cloud CPU/GPU budget. `MetaSAMTracker` is a separate later adapter. Provider identity and version must accompany every result.

`PlanningProvider` begins with deterministic safe pendulum experiment templates, then may use an open-weight LLM when justified. A `MetaMusePlanner` later receives only verified measurements, limits and relevant context. AI cannot write scientific results into measured fields.

## Compute and persistence
NumPy/SciPy deterministic math; FastAPI and Pydantic contracts; choose between a single simple web+API deployment and two services based on actual host needs. Temporary object storage or private media volume; metadata JSON for initial slices. Database may be introduced if task lifecycle or persistence requires it, with an ADR.

## Important distinctions
Cloud Codex = remote coding workspace; cloud deployment = running app accessible to judges. They are different decisions. Never commit private recordings or `.env` values. Set upload/video/runtime limits and cleanup policy.
