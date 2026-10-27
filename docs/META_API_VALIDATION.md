# Meta integration — later phase, not pre-code gate

The project implements open-source computer vision first. **Do not wait for credits to start building.** These checks are the migration tasks, not the implementation entry condition.

1. Check first-party Meta Model API SAM 3.1 / Muse documentation, exact model identifiers, available endpoints, request/response formats, limits, supported media, timing and billing.
2. Confirm real participant entitlement, applied credits, billing conditions, spend controls and user authorization before paid calls.
3. Run a limited original/consented pendulum video through Meta (only when authorized). Preserve sanitized request/response shapes, indexing, output quality, observed latency and actual cost.
4. Implement `MetaSAMTracker` mapping to `TRACKING_CONTRACT.md`, including out-of-order frames, missing masks, occlusion, async jobs and errors as observed.
5. If Muse available, implement structured next-trial planning/interpretation with schema validation, no invented measurements and fallback to deterministic templates.
6. Evaluate open vs Meta on identical media and independent reference annotations before making impact claims.

**Status:** unverified account behavior; no hosted calls in this documentation revision. Sources: https://dev.meta.ai/docs/sam/overview and official current model/API reference pages.
