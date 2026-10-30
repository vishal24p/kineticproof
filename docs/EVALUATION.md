# Benchmark — preregister hypotheses and report failures

**Purpose:** Evaluate the entire measurement chain and the incremental value of model-assisted tracking. The project goal is scientific accessibility, not maximization of segmentation accuracy alone.

**Comparisons:** OpenCV baseline versus optional licensed open model, then Meta SAM on same held-out clips. Independent manual/reference periods are the primary period-comparison target; ideal pendulum theory is separately shown as model assumption check, not ground truth. Muse proposals assessed for groundedness/safety and no invented observations, not for numerical physics accuracy.

**Per clip:** provider+version, scene condition, valid tracked frame fraction, ID switches/visible failure segments, valid cycles count, reference period source/uncertainty, computed period, absolute error seconds, relative error %, processing time, model usage/cost when measured, and success/failure. Never exclude hard clips silently.

**Across clips:** report N and failed N per condition, median abs period error and spread, tracked coverage and run-time/cost, plus paired difference by provider. Explicitly define how failed clips count; avoid averages only on survivors.

**Acceptance of initial open slice:** real uploaded clip -> actual time-indexed tracking -> traceable period with at least two cycles -> inspectable warning/failure states -> repeatable results under pinned config, verified by tests and manual reference. No numeric pass thresholds without preregistration/evidence. **Meta readiness:** same pipeline receives real Meta output through adapter, paired benchmark and credible demo before final submission.

**Current evidence:** zero measured results, zero benchmark runs in this documentation revision.

## Local benchmark report contract

`results.csv` uses the columns in `benchmark_results_template.csv`, including `rater_id`, `rater_eligible`, `rater_ineligibility_reason`, `n_reference_intervals`, `rater_reference_period_s`, `reference_period_range_s`, `rater_absolute_error_s`, `clip_median_absolute_error_s`, `tracking_status`, `measurement_status`, `valid_frame_fraction`, and `unavailable_metrics_reason`. It has one row per test clip and rater. A clip without any labels has one row with blank `rater_id` and `no_reference_annotations`; it is never omitted.

Raters remain independent. A rater is eligible only with one or more successive same-event-type reference intervals. Each eligible rater receives its own error. A clip score is the median of its eligible rater absolute errors; aggregate median error and MAD use those clip scores, so every scored clip has equal weight regardless of rater count. `reference_period_range_s` is the max-minus-min of eligible rater reference medians and is blank with fewer than two eligible raters.

Every frozen test clip remains in the total and per-condition denominators. `tracking_failed_count`, `tracking_partial_count`, `insufficient_measurement_count`, `missing_reference_clip_count`, `ineligible_reference_clip_count`, and `scored_clip_count` identify why a clip did not become a numeric score. Failures, partial traces, insufficient measurements, and missing or ineligible references are not converted to zero error and are not silently excluded.

Unsupported numeric metrics remain blank with an explicit `unavailable_metrics_reason`: pixel center error and matched-visible coverage require frame-level ground-truth labels, which this slice does not collect; ID switches do not apply to its single-target CSRT tracker. `valid_frame_fraction` is observable tracker coverage, not ground-truth accuracy. Human clicks/minutes are blank unless independently recorded. Local OpenCV has zero external-provider cost; this is not a claim about labor or hardware cost.

`latency_s` is machine-specific local elapsed time for tracking and all rater measurements for that clip. It excludes manifest/label validation and report writing. Reports are descriptive only: no numeric accuracy threshold or authentic benchmark claim is established until permitted clips and independent labels are supplied.
