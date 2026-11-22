# Slice 6 Local API Hardening Design

## Goal

Reduce accidental retention of private experiment data in browser and intermediary caches, while keeping the existing local media lifecycle simple and honest.

## Current behavior

- Uploads are limited to 100,000,000 bytes and 30 seconds.
- Source videos, traces, and overlays live in one app-owned temporary directory and are removed when the API process shuts down.
- There is no authentication, per-user ownership, aggregate storage cap, or request concurrency limit. The API is a local development service and is not ready for public exposure.
- Observation routes currently do not explicitly prevent response caching.

## Decision

Add `Cache-Control: no-store` to every response under `/api/observations`, including success, validation/error, JSON, and overlay responses. Keep `/health` outside this policy. Preserve process-lifetime temporary storage and shutdown cleanup. Do not add a one-hour expiry timer: it can race active tracking or overlay downloads and would require activity and in-flight response coordination.

Document that process-lifetime cleanup is the local policy, not a public-service retention policy. Public deployment remains blocked until authentication/ownership, aggregate storage and concurrency limits, and a host-appropriate retention period are defined and implemented.

## Scope

- Add one small API middleware that sets the response header by observation-route path.
- Add focused tests for a successful observation response, an observation error response, an overlay `FileResponse`, and `/health` remaining outside the policy.
- Update API and security docs to state the local retention behavior and public-deployment blockers.
- Leave upload limits, tracking behavior, measurement behavior, hosted providers, web UI, and cloud deployment unchanged.

## Acceptance criteria

1. Every `/api/observations` response includes `Cache-Control: no-store`, even when the endpoint returns an HTTP error.
2. `/health` does not receive the observation-specific cache header.
3. App shutdown continues to delete only files in the app-owned temporary directory.
4. Docs distinguish local process-lifetime cleanup from a future hosted retention policy and clearly prohibit public exposure before the named controls exist.
5. Offline API tests and `git diff --check` pass; no live provider or deployment call is made.

## Risks and limits

`no-store` reduces accidental caching but does not provide authorization, isolate users, bound resource use, or delete already downloaded files. This slice does not make the API safe to expose publicly.
