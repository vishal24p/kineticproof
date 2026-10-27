# Provider-neutral tracking contract (design, not tested API)

A tracking provider consumes an approved video asset, validated frame metadata, target-selection prompt/ROI where needed and bounded resource limits. It returns a **versioned TrackResult**, regardless of OpenCV, open-weight model, or Meta SAM.

## Logical fields
- `schema_version`; `experiment_id`; `video_id`; `provider_name`; `model_name`; `model_version`; `run_config_id`; `status` (`succeeded|partial|failed`)
- `frames[]`: `frame_index`, `timestamp_seconds`, `bbox_px?`, `mask_ref?`, `center_x_px?`, `center_y_px?`, `object_id?`, `quality_flags[]`, `confidence?` (optional and **not calibrated probability**)
- `failures[]`: frame index/range, reason, recovery suggestion
- `provenance`: source video hash, preprocessing, timebase, requested frames, measured/recorded usage metadata, provider request ID when available

`timestamp_seconds` must derive from the actual media timeline, not `frame_index / assumed_fps` when variable frame-rate data exists. Null center means missing; never fill invisibly. Include target identity continuity failures and per-frame masking semantics. No unverified model native response schema is claimed here.

## Adapters
`OpenCVTracker`: contour/threshold or optical tracking with explicit parameterization, good enough for a clean baseline and possibly MVP. If adding a genuinely open model, verify weights license, runtime requirements and reproducibility before adoption. `MetaSAMTracker`: map real service responses into same contract after account/doc verification. Do not rebuild physics/UI to switch providers.

## Accept
One authentic clip produces a timestamped trace and visible overlay; schema-validation tests cover missing frames and out-of-order observations. Corrupt/bad clips fail transparently.
