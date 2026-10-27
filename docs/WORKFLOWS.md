# Learner and evidence workflow

1. **Question** — choose a supported investigation and enter hypothesis, variables and safety constraints. Initially: period vs length of a homemade pendulum.
2. **Capture** — record/upload real footage; provide length, approximate angle, frame-rate/timestamp metadata and reference timing if available.
3. **Inspect target** — choose target point/region and inspect video; no hidden auto-selection when ambiguous.
4. **Track** — default open-source tracker or classical CV provides time-indexed object observations; retain missing segments and flags.
5. **Measure** — physics-specific deterministic algorithm computes periods from valid repeated cycles and propagates justified uncertainty. No unsupported real-world units without calibration.
6. **Review evidence** — playback + overlay, trajectory, cycle boundaries, period estimate, warnings and independent timing/theory comparison. User can reject a bad track.
7. **Next investigation** — propose a controlled variation, e.g. changing length, with explanation and an explicit distinction between plan vs result.

**Failure journey:** Invalid video, poor framing, occlusion, too few cycles, moving camera, ambiguous tracking, no timestamps, inconsistent timing -> flag reason and offer re-record/manual correction; never invent a result.

**Extensibility path:** The same evidence and provider contracts can later accommodate another independently validated experiment, such as rolling motion; not part of initial acceptance.
