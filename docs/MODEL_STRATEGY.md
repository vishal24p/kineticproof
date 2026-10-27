# Open-model-first -> Meta migration strategy

## Phase A: functioning open stack (no Meta dependency)
- Build video ingestion, frames/timestamp handling and an OpenCV tracking baseline (fully open-source library; not itself a learned model).
- If segmentation of cluttered scenes needs a learned model, evaluate a specific openly available segmentation/tracking model with verified weights/license and affordable cloud runtime; choose **only after** a small reproducible comparison. Candidates aren't commitments.
- Build deterministic physics, independent reference annotation, uncertainty, result audit trail, minimal evidence UI and deploy.
- Implement experiment-plan templates without requiring any LLM.

## Phase B: Meta integration (required for competitive hackathon narrative)
- Verify current Meta Model API documentation, participant credits and entitlement; map SAM 3.1 tracking to `TrackingProvider` and Muse structured planning to `PlanningProvider`.
- On identical videos, compare open tracker and SAM for period accuracy, usable frames, failures, runtime and cost. If Meta is weaker on some clips, state this openly.
- Use Meta uniquely where it provides actual value (e.g. robust object segmentation amid clutter/occlusion) and demonstrate the incremental benefit or nuanced failure findings; simple logo-wrapping is insufficient for 25% Meta tooling criterion.
- Preserve an offline/demo fallback when hosted API unavailable, **visibly label provider and data provenance**.

## Blocking policy
No Meta credits/access **does not block implementation**. It does block claims that Meta integration works and can jeopardize hackathon submission quality; track as timed risk with escalation. Missing legal rights/consent for a specific video **does block that video's upload**; does not block development with synthetic fixtures clearly marked as synthetic.

## Do not do
Don't download unknown model weights without license/security review. Don't fake SAM/Muse results. Don't claim SAM's capabilities beyond proven documentation/tests.
