# Slice 4 — Local Pendulum Benchmark Design

## Intent

Build a repeatable, offline benchmark runner for the existing OpenCV CSRT tracking and pendulum-period pipeline. The runner should be ready for permitted home pendulum clips and independent timing labels that the user will provide later. It must make failed, partial, insufficient, and unscored clips visible in the report instead of presenting results from only successful cases.

The repository has tracking and measurement functions, a results CSV template, and documentation for clip metadata and timing events. It has no benchmark runner or collected authentic clips. Synthetic videos may test the runner but never count as benchmark evidence.

## User and success

- The maintainer runs the CLI locally against a private dataset root.
- The maintainer can freeze a session-separated test set, run the same OpenCV configuration, inspect per-clip/per-rater results, and see totals and failures by scene condition.
- Each clip is counted once in the aggregate error summary, regardless of its rater count. Per-rater scores and spread remain visible; the tool does not invent a consensus label.
- A changed frozen video, label file, manifest, or split cannot be scored under the old lock.
- No authentic result is emitted until real permitted clips and independent labels are supplied.

## Goals

1. Validate a local clip manifest and separate event-label CSV.
2. Freeze the test clip IDs, session-level split map, source video hashes, event-label hashes, and benchmark configuration before scoring.
3. Run the current OpenCV CSRT provider once per clip, then measure against each rater's events separately using the existing physics engine.
4. Write a per-clip/per-rater CSV, a JSON summary, and machine-readable per-clip trace/measurement details. Keep every test clip in the denominators and report failed, insufficient, missing-reference, and scored counts by condition.
5. Record accurate unavailability: pixel center error and matched-visible coverage need frame-level labels, which this slice will not collect; identity switches do not apply to this single-target CSRT run. Report tracker valid-frame fraction and failure segments without calling them ground-truth accuracy.
6. Test the runner with generated synthetic clips and never label those test outputs as experimental results.

## Non-goals and anti-goals

- No footage capture, cloud calls, web annotation UI, public media, paid service, Meta model, or new open-weight model in this slice.
- No per-frame ground-truth position labels. The current annotation burden is independent event times only.
- No fabricated measurements, implied physical accuracy, silent clipping/exclusions, or thresholds chosen after looking at test results.
- No requirement to collect twelve clips before the first code or harness run. Real benchmark claims still require user-provided permitted footage and labels.

## Approaches considered

1. **Local CLI (selected):** reads a private local dataset and uses the existing tracking and measurement functions. It is repeatable, keeps media out of Git, and adds no runtime dependency.
2. **Web annotation and benchmark UI:** convenient for entering labels, but adds a private-media workflow not needed for this slice; the user will supply labels separately.
3. **Spreadsheet-only process:** reuses the CSV template, but cannot freeze inputs, run the existing pipeline reproducibly, or preserve failures reliably.

## Data contract

- The dataset root is local and outside version control. Paths inside the manifest are relative to that root. Original videos and generated reports stay private.
- A JSON manifest describes each clip: stable `clip_id`, `recording_session_id`, relative video path, split (`demo`, `train`, `dev`, or `test`), scene condition (`clean`, `static_clutter`, or `moving_background`), initial integer pixel ROI, motion axis, and a recorded permission/rights status. Hashes are computed and stored by freeze; the user does not hand-copy them.
- A separate CSV contains `clip_id`, pseudonymous `rater_id`, event type, source timestamp, evidence frame index, timing uncertainty, and optional notes. Event types match the existing API (`leftmost`, `rightmost`, `same_direction`). A clip can have one or more raters; two are encouraged when feasible. Labels from different raters are never merged before scoring.
- **Reference eligibility:** a rater is eligible when at least two events of one exact event type produce one or more intervals. Pair only successive events of the same type; if multiple event types produce intervals, combine those full-period intervals and take their median, matching the current measurement API. Never pair different event types.
- All clips from one recording session must have the same split. Split assignment is explicit; the tool does not randomize clips or sessions.
- **Implementation call:** JSON for nested manifest fields, CSV for labels and tabular results, and JSON for the lock and aggregate summary. These formats use the standard library and existing repository conventions without another package.

## Execution and scoring

- Provide `freeze` and `run` CLI commands. `freeze` validates the dataset and writes an immutable lock snapshot for the test split, including the test clip/session/split mapping, exact test media and reference-label hashes, test-scoring inputs (including ROI and axis), CSRT/measurement configuration, and source Git commit. It captures every recording session's split assignment so a session cannot leak across test/dev/train/demo. Dev-only media or label edits do not invalidate the lock as long as the session split map and frozen test records stay unchanged. It refuses to overwrite an existing lock; a changed test dataset or source commit is a new benchmark revision/root.
- `freeze` and `run` require a clean checkout at the locked source commit. `run` rejects a different commit or dirty code tree, and validates container, timestamps, frame bounds, ROI, axis, labels, and the API's 100,000,000-byte / 30-second media limits.
- For each test clip, inspect and track once using the existing `inspect_video`, `track_video`, and `measure_trace` path. Use a temporary overlay only because the current tracker requires one; remove it after the run. Reuse the trace for each rater's independent measurement.
- Emit one CSV row per clip and rater, including a blank `rater_id` row with `no_reference_annotations` when a test clip has no rater rows, so it remains visible. Export trace provenance/failures and each rater's measurement in a local JSONL details artifact; write a JSON summary with total test N, tracking failures/partial runs, insufficient periods, missing/ineligible references, scored clip N, and counts by scene condition.
- For each clip, take the median absolute error across its eligible rater scores. Across clips report median absolute error and median absolute deviation (MAD), giving each clip equal weight. Report scored N alongside all test N and each exclusion/failure count; do not impute failures as zero or hide them from the denominator.
- Leave pixel error, matched-visible coverage, and ID-switch values empty with an explicit `unavailable_metrics_reason`; valid tracked-frame fraction and failure segments remain directly observable. Human annotation time/clicks are not inferred. Local API cost is zero; no external provider is called.
- No numeric quality threshold is set in advance by this code. The report is descriptive until an evidence-based preregistration establishes thresholds.

## Verification and acceptance

- Tests generate a clearly synthetic MP4/MOV at runtime. They verify manifest/annotation validation, session split leakage rejection, lock creation and refusal after media/label/manifest change, one track pass reused across raters, error aggregation with equal clip weight, and rows/counts for failed, partial, insufficient, and unreferenced clips.
- Existing API tests continue to verify tracking and period measurement. CI runs the benchmark tests through the existing API test job; no real footage enters CI.
- `docs/DATA_AND_ANNOTATION.md`, `docs/EVALUATION.md`, and `docs/benchmark_results_template.csv` describe the exact input, frozen split, available/unavailable metrics, denominator rules, and local-only output. `docs/PROGRESS.md` records only checks actually run.
- Acceptance for the tooling is a deterministic synthetic test run and refusal on mutated frozen inputs. Acceptance for an authentic benchmark result remains pending the user's permitted videos and labels; synthetic results cannot satisfy it.

## Left to implementation

Keep the CLI small, reuse the provider/measurement code and existing validation, preserve the current project layout, and do not add an annotation framework or a second tracker. Choose exact module/test paths after the implementation plan maps current package structure.
