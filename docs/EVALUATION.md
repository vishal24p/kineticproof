# Benchmark — preregister hypotheses and report failures

**Purpose:** Evaluate the entire measurement chain and the incremental value of model-assisted tracking. The project goal is scientific accessibility, not maximization of segmentation accuracy alone.

**Comparisons:** OpenCV baseline versus optional licensed open model, then Meta SAM on same held-out clips. Independent manual/reference periods are the primary period-comparison target; ideal pendulum theory is separately shown as model assumption check, not ground truth. Muse proposals assessed for groundedness/safety and no invented observations, not for numerical physics accuracy.

**Per clip:** provider+version, scene condition, valid tracked frame fraction, ID switches/visible failure segments, valid cycles count, reference period source/uncertainty, computed period, absolute error seconds, relative error %, processing time, model usage/cost when measured, and success/failure. Never exclude hard clips silently.

**Across clips:** report N and failed N per condition, median abs period error and spread, tracked coverage and run-time/cost, plus paired difference by provider. Explicitly define how failed clips count; avoid averages only on survivors.

**Acceptance of initial open slice:** real uploaded clip -> actual time-indexed tracking -> traceable period with at least two cycles -> inspectable warning/failure states -> repeatable results under pinned config, verified by tests and manual reference. No numeric pass thresholds without preregistration/evidence. **Meta readiness:** same pipeline receives real Meta output through adapter, paired benchmark and credible demo before final submission.

**Current evidence:** zero measured results, zero benchmark runs in this documentation revision.
