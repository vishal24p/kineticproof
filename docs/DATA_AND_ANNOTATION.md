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

## Freeze and privacy rules

Keep the private dataset root, manifest, labels, lock, and reports outside the repository. Do not commit source video, consent records, pseudonymous-rater lookup data, locks, or generated reports. A lock is a local immutable snapshot: it records the canonical test records (including ROI, motion axis, condition, and split), test-video hashes, canonical test-label hash, complete recording-session split map, scoring configuration, and source commit. It stores manifest and label paths relative to the dataset root, not local absolute paths.

Freeze only from a clean Git checkout. A later run must also be clean and at the lock's exact source commit. `freeze` refuses an existing lock; changes to frozen test media, labels, manifest values, session split map, or source commit require a new local dataset revision and lock path. Dev-only content edits remain permitted only when they do not change the frozen test inputs or session split map.

Example private layout (all paths local and untracked):

```text
C:\KineticProof-private\pendulum-v1\
  manifest.json
  labels.csv
  clips\clip-001.mp4
  locks\test-v1.lock.json
  reports\test-v1\
```

## Sourcing and annotation practice

Two independent annotators when feasible; resolve disagreement transparently; never label tracker output as independent reference. Keep provenance and consent records outside public source media where needed.

**Data split:** demo/training/dev/held-out boundaries at clip/recording-session level to prevent leakage. Compare all trackers on identical media and reference labels; disclose dropped/failed clips.

**External videos:** only when license, attribution, compatibility, relevant footage and re-use rights are verified. User-owned recordings with consent are preferred. Private original media does not belong in public repo by default.
