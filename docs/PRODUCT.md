# Product vision and scope

## Problem / user
Students without expensive laboratory equipment need a way to conduct real experiments, extract inspectable numerical evidence, and learn whether results are trustworthy. They may have only a phone, string, a padlock and household supports.

## Product identity
**KineticProof 2.0 is an evidence-first scientific investigation companion**, not a pendulum tracker and not a chatbot that fabricates answers. It supports an iterative loop: investigate question -> design a safe procedure -> record authentic observation -> locate and track relevant physical object(s) -> compute measurements with deterministic algorithms -> inspect uncertainty/failures -> compare to independent references and theory -> revise hypothesis/plan next trial.

## MVP proof, not product limit
Implement one complete **simple pendulum** vertical slice first, including clean/clutter/moving-background tests and comparison with an OpenCV baseline. Architect entities around `Experiment`, `Observation`, `Track`, `Measurement`, `Evidence`, `Comparison` and `NextTrial`, not hard-coded `PendulumApp` concepts. New experiments require distinct physics methods and explicit scientific validation.

## Essential product outcomes
1. User understands the experimental question, inputs and safety.
2. Original phone video is reviewable and target selection/correction is visible.
3. Trajectory includes frame timestamps and missing/occluded-frame quality flags.
4. Measured period and uncertainty link back to original frames, settings and algorithm.
5. Independent timing is visibly separate from ideal small-angle theoretical prediction.
6. System explains limitations, asks for missing scale/calibration, and declines unsupported measurements.
7. User sees a grounded suggested next trial; AI explanation is optional and non-authoritative.

## Boundaries
No claim of laboratory-grade accuracy; no unverified experiments presented as functional; no mobile native app, auth, RAG, real-time cameras or complex persistence for MVP. Website works on desktop first, preferably responsive for phone viewing.
