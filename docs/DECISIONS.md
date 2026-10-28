# Architecture decision log

- **ADR-001 accepted Oct 27:** build **open-first, Meta-later**. Rationale: no dependency on distributed event credits; project remains executable. Meta-specific integration and comparative value required before credible Meta-focused submission.
- **ADR-002 accepted:** provider-neutral tracks and physics/measurement boundaries. No model output is scientific truth by itself.
- **ADR-003 accepted:** one validated pendulum experiment first, broad scientific investigation product vision, explicitly extensible data entities. Do not imply other experiments are implemented.
- **ADR-004 accepted:** desktop-first website and simple cloud dev + host; not a native app.
- **ADR-005 accepted:** modular documentation with short AGENTS.md and workstream docs. Agent executes next implementation slice without repetitively requesting task specification.
- **ADR-006 accepted Oct 28:** round fractional CSRT bounding-box coordinates to the nearest pixel using Python `round` (ties-to-even) before writing the integer trace; compute centers from the rounded box.
- **ADR-007 accepted Oct 28:** accept recognized video brands `avc1`, `av01`, and `M4V ` alongside the MP4/QuickTime brands already supported; keep 3GP and image brands rejected.
- **Pending:** specific optional open learned model (if any), deploy vendor, auth/persistence, retention, media release permissions and spend ceiling. These are decisions as-needed, not blanket blockers.
