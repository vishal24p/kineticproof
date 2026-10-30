# Muse next-trial implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use subagent-driven-development task-by-task after user approval. Keep commits explicit; review each task before continuing.

**Goal:** Add an API-only stateless next-trial response for a current pendulum observation. A deterministic template works offline by default. Hosted Muse Spark 1.3 is called only by explicit provider selection.

**Architecture:** Add a small `planning.py` module that validates pendulum context, runs the existing `measure_trace` against the observation's completed trace, and defines the response contract. Its template path returns one controlled suggestion. Its Muse path uses the existing `AsyncOpenAI` dependency from Slice 5, Meta Model API, and JSON-schema output via Responses `text.format`. The endpoint returns the deterministic measurement separately from the suggestion; no experiment record or persistence is added.

**Tech stack:** Existing FastAPI, Pydantic, `MeasurementResult`, OpenAI async SDK, pytest. Tests inject fake clients and use synthetic traces only. No live or paid calls.

---

### Task 1: Add typed planning context and deterministic template

**Files:** `services/api/src/kineticproof_api/planning.py`, `services/api/tests/test_planning.py`.

1. Define the smallest pendulum request/response models needed for question, hypothesis, explicit focus variable (`length_m|background_condition`), current setup, motion axis, optional reference events, optional gravity, provider identity, measurement, and one suggestion.
2. Reuse `MeasurementRequest` and `measure_trace`; do not accept client-supplied measured period or source provenance.
3. Implement the deterministic template path: request a longer/clearer recording if evidence is insufficient; otherwise vary the explicit focus variable while holding other experiment variables constant.
4. Keep suggestion fields separate from all measured fields. No numeric prediction.
5. Test validation, measurement reuse, template output for sufficient and insufficient data, and one-variable constraints.

**Acceptance:** Template output requires no key or network and includes a separately calculated `MeasurementResult`.

### Task 2: Add the explicit Muse Spark planner adapter

**Files:** `services/api/src/kineticproof_api/planning.py`, `services/api/tests/test_planning.py`.

1. Use injected `AsyncOpenAI` client and `muse-spark-1.3`; disable automatic retries.
2. Send only question, hypothesis, pendulum setup, and the minimized server-calculated measurement fields needed for planning. Exclude video, media path, source hash, and private identifiers.
3. Use `text.format` with a strict JSON Schema for exactly one controlled change, held-constant conditions, rationale, and limitations. Require the suggested change to match the explicit focus variable; validate locally and reject unsupported variables or any model output that attempts to supply measured values.
4. Surface provider/schema failures; do not silently fall back to the template when Muse was explicitly selected.
5. Test exact request construction, output validation, provider failure, schema failure, and no retries using a fake client. No live calls.

**Acceptance:** A mocked Muse response can produce a `meta_muse`-labeled suggestion while measurement values remain unchanged and computed locally.

### Task 3: Expose the endpoint without adding experiment state

**Files:** `services/api/src/kineticproof_api/main.py`, `services/api/tests/test_planning_api.py`.

1. Add `POST /api/observations/{observation_id}/next-trial?provider=template|meta_muse`, default `template`.
2. Require an existing completed track. Validate request context, calculate measurement from that track, and return both measurement and suggestion.
3. Read `MODEL_API_KEY` only for explicit `meta_muse`; missing key returns 503 before client construction. Map provider/schema errors to 502, invalid local input to 422, and never fall back between providers.
4. Close the async client on success/failure. Keep the existing upload/tracking/measurement routes unchanged.
5. Test template without key, Muse dispatch and client close with a fake client, missing-key short circuit, provider errors/no fallback, invalid context, and no completed observation.

**Acceptance:** No persistence or paid API use; existing APIs retain their behavior.

### Task 4: Document, verify, and ship

**Files:** `docs/API_CONTRACTS.md`, `docs/MODEL_STRATEGY.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `VERSION`, `CHANGELOG.md`.

1. Document request/response shape, template default, explicit Muse selection, data sent to Meta, key/errors, and the no-live-validation boundary.
2. Record actual local test evidence and update roadmap status without claiming Muse was used or evaluated.
3. Select release version during GStack ship; do not choose it in advance.
4. Run the complete API suite, `uv lock --check --project services/api`, `git diff --check`, and relevant CI. Review the final diff before pushing/creating the PR.

**Acceptance:** Docs match actual behavior and test output; all tests stay offline.

---

## Final review checklist

- Template is the default and works with no `MODEL_API_KEY`.
- Muse calls require explicit selection and never silently fall back.
- Muse sees only setup and server-calculated measurement; response cannot alter measurements.
- One controlled suggestion is returned; no unsupported numeric prediction or scientific conclusion is claimed.
- The required focus variable matches the returned controlled change.
- No experiment persistence, web screen, live call, or paid request is added.
