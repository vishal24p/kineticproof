# Slice 4 Experimental Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only CLI that freezes and scores a session-separated CSRT pendulum test set against independent rater event labels.

**Architecture:** Add one benchmark module to the existing API package, reusing `inspect_video`, `track_video`, `measure_trace`, and current media limits. Keep manifest and label validation, freeze lock, run orchestration, and report writing behind `python -m kineticproof_api.benchmark`; use standard-library JSON/CSV/argparse and existing OpenCV/Pydantic models.

**Tech Stack:** Python 3.12+, FastAPI service package, OpenCV, Pydantic, pytest; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-28-slice-4-benchmark-design.md`

## Global Constraints

- Local-only dataset root and outputs; source videos and reports stay outside version control.
- Resolve paths before containment checks; refuse dataset, manifest, label, lock, or report paths located inside the repository checkout and reject video symlinks that resolve outside the dataset root.
- Relative manifest paths; separate rater event CSV; never merge raters into a consensus.
- Freeze test clips, test scoring inputs, media and label hashes, complete session split map, scoring configuration, and source commit.
- Freeze and scoring require a clean checkout at the locked source commit; refuse to overwrite an existing lock.
- Track each test clip once; reuse that trace for all raters and use existing same-event-type interval/median behavior.
- Include every test clip in denominators; synthetic test media never count as benchmark evidence.
- Report unavailable pixel error/visible coverage and ID switches with reasons; valid-frame fraction is not ground-truth accuracy.

## Review Focus

- Malformed or escaping relative paths, missing files, unapproved/absent rights status, invalid split/condition/ROI/axis, and duplicate clip IDs must fail before media is processed.
- Session split leakage and changed test/split-map inputs must reject freeze/run; dev-only content edits must remain allowed.
- A dirty or different source commit, malformed/edited lock, or existing lock must not produce a score or overwrite frozen evidence.
- Empty, missing, ineligible, or disagreeing rater labels and failed/partial/insufficient tracking must remain visible and never become zero error or disappear from N.
- One clip with multiple raters must contribute one equal-weight clip score while preserving per-rater rows and spread.

---

### Task 1: Validate private benchmark inputs

**Files:**
- Create: `services/api/src/kineticproof_api/benchmark.py`
- Test: `services/api/tests/test_benchmark.py`
- Modify: `docs/DATA_AND_ANNOTATION.md`

**Interfaces:**
- Add JSON manifest loading for `clip_id`, `recording_session_id`, relative `video_path`, `split`, `scene_condition`, `initial_roi`, `motion_axis`, and `rights_status`; resolve media paths before checking dataset-root containment. The manifest and label CSV paths must also resolve within the dataset root.
- Add CSV event loading for `clip_id`, `rater_id`, `event_type`, `timestamp_seconds`, `evidence_frame_index`, and `uncertainty_seconds` (notes optional).
- Require `rights_status` to be explicitly `permitted` before freezing or scoring; split is `demo|train|dev|test`, condition is `clean|static_clutter|moving_background`, and sort each rater's events by timestamp while rejecting duplicate timestamps to satisfy the existing API contract.
- Keep testable functions `load_manifest(path, dataset_root) -> list[dict]`, `load_event_labels(path, dataset_root, clip_ids) -> dict[str, dict[str, list[ReferenceEvent]]]` (clip ID → rater ID → events), and `validate_dataset(manifest, labels, dataset_root) -> None`; use existing `InitialROI`, `MotionAxis`, media caps, and `inspect_video` validation.

- [ ] Add `test_manifest_accepts_permitted_relative_media` and parameterized `test_manifest_rejects_invalid_records` for missing/outside-root paths, duplicate IDs, malformed fields, unapproved rights status, invalid ROI/axis, and unsupported media; document clip/session/rater IDs as pseudonymous.
- [ ] Add `test_event_labels_reject_unknown_clips_and_duplicate_timestamps` for unknown clip IDs, invalid timestamps/uncertainties/frame indexes, and duplicate per-rater timestamps; add `test_event_labels_sort_per_rater` for unsorted CSV rows.
- [ ] Add `test_private_input_paths_must_be_outside_repository` for dataset, manifest, and event-label paths inside the checkout.
- [ ] Add `test_video_symlink_cannot_escape_dataset_root` where symlink creation is supported; retain the traversal-path test on all platforms.
- [ ] Add `test_session_cannot_cross_splits` proving clips in one recording session cannot have different splits.
- [ ] Implement validation and fail with actionable CLI errors before tracker execution.
- [ ] Update `DATA_AND_ANNOTATION.md` with the exact manifest/CSV fields and private local-root rule.
- [ ] Run `uv run --project services/api pytest services/api/tests/test_benchmark.py -q` and confirm all new cases pass.

### Task 2: Freeze immutable test inputs

**Files:**
- Modify: `services/api/src/kineticproof_api/benchmark.py`
- Test: `services/api/tests/test_benchmark.py`

**Interfaces:**
- Add `freeze_dataset(dataset_root, manifest_path, labels_path, lock_path, source_commit)`.
- Lock manifest and label CSV paths relative to the dataset root, canonical test clip records and test label rows, SHA-256 of every test video and canonical test label rows, the full session-to-split map, and benchmark/source configuration in JSON. Do not hash dev-only label contents.
- Store a SHA-256 digest over the canonical lock payload and verify it before scoring; this detects accidental edits, not deliberate recomputation.
- Resolve Git HEAD and worktree cleanliness in the CLI; freeze only at clean HEAD and refuse an existing lock.

- [ ] Add `test_freeze_is_deterministic_and_never_overwrites`, `test_freeze_requires_test_clips`, `test_lock_stores_relative_input_paths`, `test_run_reloads_locked_source_files`, `test_frozen_test_inputs_must_match`, and `test_dev_only_changes_do_not_invalidate_lock` for lock creation, canonical contents, run-time reload, test media/labels/ROI/axis/condition/split mutation rejection, and permitted dev-only edits; missing stored inputs must fail before scoring.
- [ ] Add `test_lock_payload_digest_rejects_edits` for altered or malformed lock payloads.
- [ ] Add `test_lock_path_must_be_outside_repository` for lock files inside the checkout.
- [ ] Add `test_freeze_and_run_require_locked_clean_commit` for source commit mismatch and dirty checkout refusal at the CLI boundary.
- [ ] Implement canonical hashing and lock validation; changed frozen inputs require a new dataset revision/lock path.
- [ ] Run `uv run --project services/api pytest services/api/tests/test_benchmark.py -q`.

### Task 3: Score each test clip once and preserve every outcome

**Files:**
- Modify: `services/api/src/kineticproof_api/benchmark.py`
- Test: `services/api/tests/test_benchmark.py`

**Interfaces:**
- Add `run_benchmark(dataset_root, lock_path, output_dir, source_commit)` and CLI subcommand `run`; resolve the stored relative manifest/label paths, reload both files, and verify the live test records and test labels against the lock before scoring.
- Use `inspect_video`, `track_video`, and `measure_trace`; create a temporary overlay for tracking and remove it after each clip. Reuse one `TrackResult` per clip for each rater's `MeasurementRequest`.
- Compare each returned trace's `provenance.source_video_sha256` to the frozen video hash after tracking; reject any mismatch before scoring. Include locked source commit and lock digest in `summary.json`.
- Emit `results.csv` by retaining the existing template columns and adding `rater_id`, `rater_eligible`, `rater_ineligibility_reason`, `n_reference_intervals`, `rater_reference_period_s`, `reference_period_range_s`, `rater_absolute_error_s`, `clip_median_absolute_error_s`, `tracking_status`, `measurement_status`, `valid_frame_fraction`, and `unavailable_metrics_reason`. Keep unavailable numeric metric fields blank; include a blank-rater `no_reference_annotations` row. Also write `details.jsonl` (trace/provenance/failures and per-rater measurements) and `summary.json`.
- Summary reports all-test N, failed/partial tracking, insufficient results, missing/ineligible reference, scored clips, and per-condition counts. Per-clip score is median eligible-rater absolute error; overall median and MAD weight clips equally.
- Per-rater absolute error is `abs(measured_period_seconds - rater_reference_period_seconds)`; relative error is absolute error divided by the rater reference period, times 100.
- Report per-clip reference-period range as max minus min of eligible raters' median reference periods; set it to null when fewer than two raters are eligible.
- Measure `latency_s` with a monotonic clock around each clip's tracking plus all rater measurements; label it as machine-specific local elapsed time.
- Keep pixel error, matched-visible coverage, and ID switches unavailable with reasons; expose tracker valid-frame fraction/failure segments separately.
- Record external provider cost as zero for local OpenCV runs; leave billing-only and human-effort fields blank because they are not measured.

- [ ] Add `test_clip_is_tracked_once_and_each_rater_is_scored_separately`, verifying same-type event intervals only, combining intervals across event types, and taking the existing median.
- [ ] Add `test_reference_eligibility_requires_same_type_pair`, proving different event types are never paired and a rater with no repeated event type is ineligible.
- [ ] Add `test_scores_weight_clips_equally_and_keep_rater_spread` and `test_report_keeps_missing_failed_partial_and_insufficient_clips`, including blank-rater rows and per-condition denominators.
- [ ] In `test_scores_weight_clips_equally_and_keep_rater_spread`, assert reference-period range from eligible rater medians and null spread with fewer than two eligible raters.
- [ ] Add `test_reports_schema_and_unavailable_metrics` for all existing template columns plus the named per-rater columns, explicit reasons, and output containment under the selected output directory.
- [ ] Add `test_output_path_must_be_outside_repository` for report directories inside the checkout.
- [ ] Add `test_latency_covers_tracking_and_all_rater_measurements` with a controlled monotonic clock to verify the reported machine-specific interval.
- [ ] Add `test_tracking_exception_is_reported_as_failed_clip` so a per-clip decoder/tracker error becomes an explicit failed row and remains in all-test N.
- [ ] Add `test_temporary_overlay_is_removed_after_each_clip` for successful and failed tracking paths.
- [ ] Add `test_source_change_during_tracking_is_not_scored` by changing the source during a controlled tracking call and asserting a failed clip row.
- [ ] Add `test_output_write_error_fails_without_success_summary` for an unwritable output destination.
- [ ] Implement serialization and failure handling without dropping clips or assigning fabricated errors.
- [ ] Run `uv run --project services/api pytest services/api/tests/test_benchmark.py -q`.

### Task 4: Verify CLI behavior and document the benchmark contract

**Files:**
- Modify: `services/api/src/kineticproof_api/benchmark.py`
- Modify: `services/api/tests/test_benchmark.py`
- Modify: `docs/DATA_AND_ANNOTATION.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/benchmark_results_template.csv`
- Modify: `docs/PROGRESS.md` only with checks actually run
- Modify: `README.md`

- [ ] Add CLI usage for `freeze` and `run`, stable exit codes, and help text; add `test_cli_help_and_subcommands` using subprocesses and run `uv run --project services/api python -m kineticproof_api.benchmark --help`.
- [ ] Add `test_synthetic_cli_freeze_run_and_mutation_rejection` using a temporary clean Git repo, generated media, and labels; mark its output synthetic and keep all generated files outside the repo.
- [ ] Keep the existing CSV template columns, add the named per-rater fields, and document blank unsupported metrics plus explicit unavailability reasons, clip-equal aggregation, failure denominators, and freeze policy.
- [ ] Document that `latency_s` is machine-specific elapsed time for tracking and all rater measurements, excluding validation and report writing.
- [ ] Add a concise private dataset example plus local `freeze` and `run` commands to `README.md`; explain the clean locked commit requirement.
- [ ] Run `uv run --project services/api pytest -c services/api/pyproject.toml services/api/tests -q`, `uv lock --check --project services/api`, and `git diff --check`.
- [ ] Record only those exact command results in `docs/PROGRESS.md`; state that authentic benchmark acceptance remains pending permitted clips and labels.

### Task 5: Review and ship Slice 4

**Files:**
- Review all Slice 4 changes and documentation.
- Modify after release decision: `VERSION`, `CHANGELOG.md`

- [ ] Run GStack code review and resolve actionable findings.
- [ ] Run the GStack ship workflow: refresh checks, inspect final diff and private-media/secrets boundary, prepare release notes, and publish the PR against `feature/slice-2-physics-evidence` after user-approved version/release metadata is ready.
- [ ] Confirm CI results and report exact evidence paths; do not claim authentic benchmark results.

## What already exists

- `tracking.inspect_video` validates local media and returns duration/frame metadata; `tracking.track_video` runs local CSRT and returns source-timed provenance/failures plus a temporary overlay.
- `physics.MeasurementRequest`, `physics.measure_trace`, and `physics.measurement_csv` already implement normalized axes, per-rater manual-event period calculation, and trace provenance; the benchmark reuses them rather than duplicating physics.
- `services/api/tests/test_tracking.py` creates synthetic video at runtime; `services/api/tests/test_physics.py` already covers same-type event intervals, measurement eligibility, and deterministic results.
- `docs/DATA_AND_ANNOTATION.md`, `docs/EVALUATION.md`, and `docs/benchmark_results_template.csv` already define dataset rights, independent events, evaluation principles, and broad result fields; Slice 4 makes the local runner and exact fields concrete.
- GitHub Actions already runs the full API pytest suite, so benchmark tests join the existing CI job without a separate workflow.

## NOT in scope

- Authentic clips, labels, and benchmark claims; the user will provide permitted inputs later.
- Additional trackers, Meta providers, cloud calls/deployment, annotation UI, per-frame ground truth, and model comparisons.
- A packaged executable or external distribution pipeline; the CLI runs from the repository's existing `uv` project and README instructions.
- Numeric accuracy thresholds or post-hoc claims of scientific accuracy.
- Creating a second roadmap or `TODOS.md`; follow-up work remains in `docs/IMPLEMENTATION.md`.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture, code quality, tests, performance | 1 | CLEAR (PLAN) | 8 findings resolved; no open implementation decisions |
| Independent plan review | Outside voice (`gpt-6-astra` subagent) | Second opinion on plan gaps | 1 | ADDRESSED | Defined nested clip/rater mapping and lock-stored input paths; user chose both |
| CEO Review | Not run | Local benchmark tooling; no product-direction change | 0 | — | Not needed |
| Design Review | Not run | No UI changes | 0 | — | Not needed |

- **CODEX:** Codex CLI was installed but unavailable without shell authentication; the GStack fallback used an independent `gpt-6-astra` subagent. It identified two gaps, both resolved with the user's choices.
- **CROSS-MODEL:** No remaining review tension; both outside-review findings are reflected in the plan.
- **VERDICT:** ENG CLEARED — ready for implementation-plan approval.

GStack test-plan artifact: `C:\Users\visha\.gstack\projects\kineticproof\visha24p-feature-slice-3-web-mvp-eng-review-test-plan-20261028-123000.md`.

Search check used Python's built-in [`argparse`](https://docs.python.org/3.12/library/argparse.html), [`pathlib`](https://docs.python.org/3.12/library/pathlib.html), and [`hashlib`](https://docs.python.org/3.12/library/hashlib.html); no runtime, dependency, or distribution layer is added. Canonical paths must be resolved before containment checks because `PurePath.is_relative_to()` is string-based.

NO UNRESOLVED DECISIONS

