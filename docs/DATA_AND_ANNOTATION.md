# Dataset, sourcing, rights, annotations

**Planned 12 clips**, not collected: initial working/control videos plus held-out evaluation across clean, static clutter and background-motion conditions; freeze a meaningful held-out subset before choosing thresholds. Do not imply 12 are already available or necessary before first code.

**Video manifest:** clip id, provenance/rights/consent, owner, date, scene condition, object material, effective length with method/uncertainty, release angle, resolution, actual timestamps/fps behavior, camera position, lighting, visibility, processing split, exclusions, hash, retention date.

**Reference event template:** clip id, rater id, timestamp seconds, event type (leftmost/rightmost or same-direction reference), evidence frame index, uncertainty, notes. Two independent annotators when feasible; resolve disagreement transparently; never label tracker output as independent reference.

**Data split:** demo/training/dev/held-out boundaries at clip/recording-session level to prevent leakage. Compare all trackers on identical media and reference labels; disclose dropped/failed clips.

**External videos:** only when license, attribution, compatibility, relevant footage and re-use rights are verified. User-owned recordings with consent are preferred. Private original media does not belong in public repo by default.
