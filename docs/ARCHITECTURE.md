# Architecture — open-first, Meta-ready

## Data flow
Next.js web candidate -> FastAPI upload + job service -> private temporary media -> video decoding/timestamp normalization -> `TrackingProvider` -> versioned timestamped tracks -> physics measurement service -> evaluation/evidence JSON -> evidence-first web UI -> optional structured AI interpretation / next-trial explanation.

## Provider strategy
Tracking has a provider-neutral contract with OpenCV CSRT as the default and an explicitly selected SAM 3.1 adapter implemented locally. SAM live behavior remains unverified. Optional open learned models require demonstrated benefit and verified licensing/budget. Provider identity and version accompany every trace.

`planning.py` implements API-only next-trial planning: the default deterministic template and explicit `meta_muse` adapter share typed context, suggestion, and response contracts. Each call measures the existing completed trace locally with `measure_trace`, then attaches one controlled suggestion separately. No experiment/conversation/suggestion persistence is added; planning is stateless despite existing process-local observation state. The bootstrap web UI has no planning controls. Muse receives only context and a minimized local measurement summary; AI cannot write scientific results into measured fields. Exact fields, exclusions, errors, and no-fallback behavior are in [API contracts](API_CONTRACTS.md#implemented-next-trial-planning-api-only). Only offline adapter tests are verified; live Muse compatibility, entitlement, quality, latency and cost are unknown.

## Compute and persistence
NumPy/SciPy deterministic math; FastAPI and Pydantic contracts; choose between a single simple web+API deployment and two services based on actual host needs. Temporary object storage or private media volume; metadata JSON for initial slices. Database may be introduced if task lifecycle or persistence requires it, with an ADR.

## Important distinctions
Cloud Codex = remote coding workspace; cloud deployment = running app accessible to judges. They are different decisions. Never commit private recordings or `.env` values. Set upload/video/runtime limits and cleanup policy.
