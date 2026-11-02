# Open-model-first -> Meta migration strategy

## Phase A: functioning open stack (no Meta dependency)
- Build video ingestion, frames/timestamp handling and an OpenCV tracking baseline (fully open-source library; not itself a learned model).
- If segmentation of cluttered scenes needs a learned model, evaluate a specific openly available segmentation/tracking model with verified weights/license and affordable cloud runtime; choose **only after** a small reproducible comparison. Candidates aren't commitments.
- Build deterministic physics, independent reference annotation, uncertainty, result audit trail, minimal evidence UI and deploy.
- Implement experiment-plan templates without requiring any LLM.

## Phase B: Meta integration (required for competitive hackathon narrative)
- **SAM adapter implemented locally:** explicit API selection maps SAM 3.1 boxes to the provider-neutral tracking trace. OpenCV stays the default; no automatic fallback occurs. Real account access and live behavior are unverified.
- **Next:** verify participant credits and entitlement before any authorized hosted request, then compare OpenCV and SAM on identical permitted videos and independent labels for period accuracy, usable frames, failures, runtime and actual cost. State weaker results openly.
- **Muse adapter implemented locally:** API-only next-trial planning defaults to an offline deterministic template. Explicit `provider=meta_muse` selects the hosted adapter; measurements are recomputed locally and remain separate from suggestions. Only fake-client/synthetic-trace tests have run. Live compatibility, entitlement, scientific quality, latency and cost remain unverified. See [API contracts](API_CONTRACTS.md#implemented-next-trial-planning-api-only) for exact payload, exclusions and error behavior.
- Use Meta uniquely where it provides actual value (e.g. robust object segmentation amid clutter/occlusion) and demonstrate the incremental benefit or nuanced failure findings; simple logo-wrapping is insufficient for 25% Meta tooling criterion.
- Preserve explicitly selectable offline/demo paths when hosted APIs are unavailable; never silently fall back after a hosted provider is selected. **Visibly label provider and data provenance**.

## Blocking policy
No Meta credits/access **does not block implementation**. It blocks live validation and claims that SAM works or improves results; track that risk. Missing legal rights/consent for a specific video **does block that video's upload**; does not block development with synthetic fixtures clearly marked as synthetic.

## Do not do
Don't download unknown model weights without license/security review. Don't fake SAM/Muse results. Don't claim SAM's capabilities beyond proven documentation/tests.
