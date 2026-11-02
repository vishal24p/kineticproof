# Muse next-trial design

## Goal

Add an API-only, stateless next-trial suggestion for the first supported pendulum experiment. Use hosted Muse Spark 1.3 only when explicitly selected. Keep the local path usable without a key, and never let model text replace deterministic measurements.

## Accepted scope

- Hosted `muse-spark-1.3`; Muse Spark Open weights are out of scope.
- No live or paid calls in development, tests, or this PR.
- Take the current experiment setup and server-calculated deterministic measurement as explicit prompt input.
- API only; no web screen or persisted experiment entity in this slice.

## Proposed contract

`POST /api/observations/{id}/next-trial?provider=template|meta_muse` accepts the experiment question/hypothesis, explicit focus variable (`length_m` or `background_condition`), current pendulum setup (length, release angle, background condition, and whether the camera is fixed), motion axis, optional reference events, and optional gravity. Requiring the focus variable lets the template and Muse suggest one controlled change without guessing the study goal. It uses the observation's existing trace to calculate a fresh `MeasurementResult`; clients cannot supply or alter the measurement passed to Muse. The observation/trace must still be present in the current API process.

The endpoint returns the measurement separately from a `NextTrialSuggestion`: one proposed controlled change, what to keep constant, a short rationale, and limitations. The model receives only the setup and the measurement fields needed for planning—no video, media path, or source hash. It cannot return predicted periods or write measured fields. `meta_muse` uses the Responses API with `text.format` JSON Schema and model `muse-spark-1.3`; response validation still runs locally. No implicit provider fallback occurs.

`template` is the default and makes no external call. It returns a deterministic instruction to improve the recording when measurement is insufficient, or to vary the declared focus variable while holding other experiment variables fixed after a valid measurement. The response labels `provider_name` so users can distinguish template output from Muse output.

For `meta_muse`, read `MODEL_API_KEY` only after explicit selection; missing key returns 503, provider/schema failure returns 502, and no automatic retries or fallback occur. Return 422 for a missing track or invalid measurement/setup. No experiment state is persisted.

## Safety and scientific boundaries

- Keep all deterministic measurement fields server-calculated and immutable in the response.
- Require exactly one suggested variable change; keep the supported change within the pendulum context.
- Do not ask Muse for numeric period predictions. Explain its rationale as a suggestion, not a measurement or validated causal conclusion.
- Include data-quality warnings and source measurement provenance in the API response, but exclude source video hashes and media from the model prompt.
- Offline tests use an injected fake async client and synthetic trace data only.

## Code and documentation scope

- Add a small planning module using existing `MeasurementRequest`, `measure_trace`, `TrackResult`, and OpenAI async client patterns.
- Add one API route with template default and explicit Muse selection.
- Add focused API/module tests for request validation, deterministic template behavior, strict structured output, missing key, errors, and no live calls.
- Update `API_CONTRACTS.md`, `MODEL_STRATEGY.md`, `ARCHITECTURE.md`, `README.md`, `DECISIONS.md`, and evidence-based `PROGRESS.md`.

## Acceptance

- A caller with a completed local trace can receive a deterministic, labeled template suggestion without credentials.
- Explicit `meta_muse` sends only bounded setup and server-derived measurement data to `muse-spark-1.3`, validates the structured result, and labels it as Muse.
- Provider failure is visible; no fallback, persistence, fabricated measurement, live API request, or paid call occurs in tests.
- Existing tracking and measurement APIs remain unchanged.

## Official references

- [Muse Spark Model API](https://dev.meta.ai/docs/models)
- [Responses API structured output uses `text.format`](https://dev.meta.ai/docs/protocols/responses)
- [Meta structured-output guide](https://dev.meta.ai/docs/structured-output)
