# Physics engine — separate measurements from perception

The provider returns per-frame target observations, not period/velocity or physics truth. Deterministic code extracts an interpretable signal from tracked centers and timestamps, handles gaps, filters with disclosed parameters, detects repeated cycles or same-direction extrema, and calculates multiple periods with robust aggregation.

For a small-angle simple pendulum theoretical reference: `T_theory = 2π sqrt(L/g)` given measured **effective** pivot-to-center-of-mass length `L`, assumed local gravity, and documented assumptions. This is **not independently observed ground truth**. Optional speed/displacement in metric units requires scale and camera geometry calibration; pixel coordinates alone do not justify meters/second or true 3-D acceleration.

Report number of detected cycles, frame validity, timestamps, uncertainty definition and rationale (e.g. cycle-to-cycle variation plus timing resolution where justified); expose missing cycles and avoid numerical confidence with no calibration. Do not let a language model fill measurement fields.
