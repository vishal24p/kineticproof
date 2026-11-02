# Anonymous browser session ownership

## Goal

Isolate uploaded observations by anonymous browser session so one visitor cannot read or change another visitor's media and results.

## Current behavior

- The API keeps observations and media in one process and removes media at shutdown.
- Observation IDs are UUIDs, but possession of an ID currently grants access to every observation endpoint.
- The Slice 3 web client calls relative `/api/...` URLs through a same-origin Next.js rewrite. The browser can retain a cookie set by the FastAPI response without a frontend token store.
- User accounts remain outside the MVP. Public hosting also needs aggregate resource limits and host-specific retention.

## Decision

- Treat a browser session as a 256-bit random ID signed with HMAC-SHA256 using a random process-lifetime key. Carry `session_id.hex_signature` in an `HttpOnly`, `SameSite=Strict`, `Path=/api` cookie named `kineticproof_session`. Reject malformed token lengths/characters and compare signatures with `hmac.compare_digest`. Do not set `Domain`, `Max-Age`, or `Expires`; it is a browser-session cookie.
- Add `POST /api/session` to establish a session before upload. It returns no session identifier in the body and sets the cookie; repeat calls preserve a valid cookie and replace a missing or invalid one. Reuse the established cookie for uploads. Set `Secure` only when `KINETICPROOF_COOKIE_SECURE=1`; local HTTP stays usable, and hosted TLS deployments must set the variable.
- Store the random session ID as `owner_session_id` on each `Observation`. Require and verify the signed cookie for all other observation routes. Missing or invalid cookie returns 401; a different session's observation returns 404 to avoid disclosing its existence.
- Keep `/health` public. Preserve all observation response bodies and existing `Cache-Control: no-store` behavior; apply `no-store` to `/api/session` too. The Slice 3 UI bootstrap call is a separate dependent PR, so this API PR does not claim to verify Next.js cookie forwarding.
- Prefer the signed cookie over a session registry (which adds server state) or accounts (which remain outside MVP scope). Verify cookie forwarding through the Slice 3 same-origin rewrite in the follow-up UI PR; API unit tests cannot cover that browser/proxy path.
- Keep process-lifetime observation storage and shutdown cleanup unchanged. No account, persistent session table, cross-origin CORS policy, timer, resource quota, or deployment is added.

## Acceptance criteria

1. `POST /api/session` issues a session cookie without exposing its identifier; valid-cookie repeats preserve it. Upload uses the established session, and failed uploads do not create owned observations.
2. A client can access its own tracking, track, overlay, measure, and next-trial routes; another client receives 404 for the same observation ID.
3. Missing cookies cannot access observation routes; `/health` remains public.
4. Cookie flags are `HttpOnly`, `SameSite=Strict`, and `Path=/api`; `Secure` follows `KINETICPROOF_COOKIE_SECURE=1`.
5. Observation responses, including authorization failures, keep `Cache-Control: no-store`.
6. Offline API tests pass. Docs state that this is anonymous bearer-session isolation, not account authentication, and public deployment still requires aggregate storage/concurrency limits and host-specific retention.

## Risks and limits

- Anyone who steals a session cookie can act as that browser session.
- Observation IDs and state remain process-local; restart loses them, and multiple workers do not share them.
- The process-random signing key invalidates old session cookies on restart, matching the existing loss of process-local observations.
- Session ownership does not limit upload volume or processing concurrency and does not make public deployment ready.
- A hosted TLS-terminating setup must set `KINETICPROOF_COOKIE_SECURE=1`; no host is selected in this slice.

## Delivery boundary

- PR 1: API session bootstrap, cookie verification, observation ownership, tests, and API/security docs, based on the Slice 6 branch.
- PR 2: update the existing Slice 3 UI branch to call `POST /api/session` before upload; verify the same-origin rewrite stores and returns the cookie. Keep this dependent UI change separate so each PR stays reviewable.
