# Provider-neutral tracking contract

A tracking provider consumes an approved video asset, validated frame metadata, target-selection prompt/ROI where needed and bounded resource limits. It returns a **versioned TrackResult**, regardless of OpenCV, open-weight model, or Meta SAM.

## Logical fields
- `schema_version`; `experiment_id`; `video_id`; `provider_name`; `model_name`; `model_version`; `run_config_id`; `status` (`succeeded|partial|failed`)
- `frames[]`: `frame_index`, `timestamp_seconds`, `bbox_px?`, `mask_ref?`, `center_x_px?`, `center_y_px?`, `object_id?`, `quality_flags[]`, `confidence?` (optional and **not calibrated probability**)
- `failures[]`: frame index/range, reason, recovery suggestion
- `provenance`: source video hash, preprocessing, timebase, requested frames, measured/recorded usage metadata, provider request ID when available

`timestamp_seconds` must derive from the actual media timeline, not `frame_index / assumed_fps` when variable frame-rate data exists. Null center means missing; never fill invisibly. Include target identity continuity failures and per-frame masking semantics. No unverified model native response schema is claimed here.

## Adapters
`OpenCVTracker`: implemented local CSRT baseline with default parameters. If adding an open model, verify weights license, runtime requirements and reproducibility before adoption. `MetaSAMTracker`: future adapter; map real service responses into same contract after account/doc verification. Do not rebuild physics/UI to switch providers.

## Implemented local v1 mapping

- `schema_version="1.0.0"`, `experiment_id=null`, `video_id=observation_id`.
- `provider_name="opencv"`, `model_name="csrt"`, `model_version=cv2.__version__`, `run_config_id="opencv-csrt-default-v1"`.
- Initial ROI is `{x,y,width,height}` in integer pixels: nonnegative origin, positive dimensions, entirely inside the first frame. Floats, booleans and numeric strings are rejected.
- Frames use zero-based `frame_index`, source `timestamp_seconds`, `bbox_px={x,y,width,height}`, `center_x_px`, `center_y_px`, and `quality_flags`. The first frame uses the supplied ROI. Centers are bounding-box midpoints, not a segmented object's center of mass. Masks, object IDs and confidence are omitted.
- Tracker bbox components are normalized to the nearest integer pixel with Python `round` (ties-to-even). Centers derive from these normalized boxes and can contain half pixels.
- Timestamps come from FFmpeg-backed OpenCV `CAP_PROP_PTS / CAP_PROP_FPS`. Missing, nonfinite or nonincreasing PTS fails the run; frame indices never replace timestamps. See [OpenCV PTS documentation](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html).
- A failed CSRT update retains that frame with null bbox and centers, `quality_flags=["tracking_failed"]`, and a failure entry containing `frame_index`, `reason`, `recovery_suggestion`. Any failed update makes the run `partial`. No interpolation, relinking or confidence estimate is applied.
- Provenance keys: `source_video_sha256`, `preprocessing="none"`, `timebase_seconds_per_tick=1/fps`, `requested_frames` (uploaded decoded frame count), `opencv_version`.
- Overlay is an MP4 preview with a bounding box when available and source PTS drawn on every frame. It is encoded at constant FPS and does not preserve variable-rate playback timing or audio. JSON trace is authoritative for timing. Output is decoded and checked for matching frame count and dimensions before publication.

Synthetic tests verify this mapping and failure plumbing. They do not establish accuracy on authentic experimental footage. CSRT is an OpenCV tracker; no Meta model is used.

## Accept
One authentic clip produces a timestamped trace and visible overlay; schema-validation tests cover missing frames and out-of-order observations. Corrupt/bad clips fail transparently.
