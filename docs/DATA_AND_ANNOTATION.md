# Dataset, sourcing, rights, annotations

## Private benchmark inputs

No benchmark clips have been collected. The planned twelve clips are a working target, not a prerequisite for the tooling or a claim about available data.

Keep the dataset root, manifest, event labels, and source videos in a local directory outside the repository checkout. Manifest and event-label file paths must resolve inside that root; each `video_path` is relative to it and must resolve inside it, including after symlink resolution. The validator rejects videos above the API media limits (100,000,000 bytes or 30 seconds), unsupported or undecodable media, and initial ROIs outside the first frame.

The manifest is a JSON array with one object per clip and these required fields:

- `clip_id`: stable pseudonymous clip identifier.
- `recording_session_id`: pseudonymous recording-session identifier; every clip in a session must use the same split.
- `video_path`: relative path to the private source video.
- `split`: `demo`, `train`, `dev`, or `test`.
- `scene_condition`: `clean`, `static_clutter`, or `moving_background`.
- `initial_roi`: `{ "x", "y", "width", "height" }` integer pixel box.
- `motion_axis`: `{ "x", "y" }` nonzero direction vector.
- `rights_status`: must be exactly `permitted` before freezing or scoring.

The separate event-label CSV requires `clip_id`, `rater_id`, `event_type`, `timestamp_seconds`, `evidence_frame_index`, and `uncertainty_seconds`; optional `notes` may be included. `rater_id` must be pseudonymous. Event types are `leftmost`, `rightmost`, or `same_direction`. Rows are grouped by clip and rater, sorted by timestamp for measurement, and duplicate timestamps for a clip/rater are rejected. Raters remain independent; the benchmark does not merge labels into a consensus.

## Sourcing and annotation practice

Two independent annotators when feasible; resolve disagreement transparently; never label tracker output as independent reference. Keep provenance and consent records outside public source media where needed.

**Data split:** demo/training/dev/held-out boundaries at clip/recording-session level to prevent leakage. Compare all trackers on identical media and reference labels; disclose dropped/failed clips.

**External videos:** only when license, attribution, compatibility, relevant footage and re-use rights are verified. User-owned recordings with consent are preferred. Private original media does not belong in public repo by default.
