import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from kineticproof_api import benchmark
from kineticproof_api.benchmark import load_event_labels, load_manifest, validate_dataset


REPO = Path(__file__).resolve().parents[3]


def video(path, frames=6, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.CAP_FFMPEG, cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    assert writer.isOpened()
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 10, dtype=np.uint8))
    writer.release()


def dataset(tmp_path, records=None):
    root = tmp_path / "private"
    root.mkdir()
    video(root / "clip.mp4")
    records = records or [dict(clip_id="clip-a", recording_session_id="session-a", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted")]
    (root / "manifest.json").write_text(json.dumps(records), encoding="utf-8")
    return root


def test_manifest_accepts_permitted_relative_media(tmp_path):
    root = dataset(tmp_path)
    records = load_manifest(root / "manifest.json", root)
    assert records[0]["video_path"] == "clip.mp4"
    assert records[0]["initial_roi"].x == 1


@pytest.mark.parametrize("change", [
    {"video_path": "missing.mp4"}, {"video_path": "../outside.mp4"},
    {"clip_id": ""}, {"split": "validation"}, {"scene_condition": "busy"},
    {"rights_status": "pending"}, {"split": []}, {"scene_condition": {"bad": True}}, {"initial_roi": {"x": -1,"y": 1,"width": 5,"height": 5}},
    {"motion_axis": {"x": 0,"y": 0}},
])
def test_manifest_rejects_invalid_records(tmp_path, change):
    item = dict(clip_id="clip-a", recording_session_id="session-a", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted")
    item.update(change)
    root = dataset(tmp_path, [item])
    with pytest.raises(ValueError):
        load_manifest(root / "manifest.json", root)


def test_manifest_rejects_missing_required_fields_and_wrong_types(tmp_path):
    item = dict(clip_id="clip-a", recording_session_id="session-a", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted")
    item.pop("recording_session_id")
    root = dataset(tmp_path, [item])
    with pytest.raises(ValueError, match="must contain"):
        load_manifest(root / "manifest.json", root)


def test_manifest_rejects_duplicate_ids_and_unsupported_media(tmp_path):
    record = dict(clip_id="dup", recording_session_id="s", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted")
    root = dataset(tmp_path, [record, record])
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(root / "manifest.json", root)
    (root / "clip.mp4").write_bytes(b"not a video")
    (root / "manifest.json").write_text(json.dumps([record]))
    with pytest.raises(ValueError, match="unsupported or invalid"):
        load_manifest(root / "manifest.json", root)


def test_event_labels_sort_per_rater(tmp_path):
    root = dataset(tmp_path)
    path = root / "events.csv"
    path.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\nclip-a,r1,leftmost,0.4,4,0.01\nclip-a,r1,leftmost,0.1,1,0.02\n", encoding="utf-8")
    events = load_event_labels(path, root, {"clip-a"})["clip-a"]["r1"]
    assert [e.timestamp_seconds for e in events] == [0.1, 0.4]


@pytest.mark.parametrize("rows", [
    "unknown,r1,leftmost,0.1,1,0.01\n",
    "clip-a,r1,leftmost,nan,1,0.01\n",
    "clip-a,r1,leftmost,0.1,-1,0.01\n",
    "clip-a,r1,leftmost,0.1,1,-0.01\n",
    "clip-a,r1,leftmost,0.1,1,0.01\nclip-a,r1,rightmost,0.1,1,0.01\n",
])
def test_event_labels_reject_unknown_clips_and_duplicate_timestamps(tmp_path, rows):
    root = dataset(tmp_path)
    path = root / "events.csv"
    path.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError):
        load_event_labels(path, root, {"clip-a"})


def test_private_input_paths_must_be_outside_repository(tmp_path):
    inside = REPO / "services/api/tests/_private-test.json"
    with pytest.raises(ValueError):
        load_manifest(inside, REPO)


def test_private_event_labels_and_dataset_root_must_be_outside_repository():
    inside = REPO / "services/api/tests/_private-test.csv"
    with pytest.raises(ValueError):
        load_event_labels(inside, REPO, set())


def test_video_symlink_cannot_escape_dataset_root(tmp_path):
    root = dataset(tmp_path)
    outside = tmp_path / "outside.mp4"
    video(outside)
    try:
        (root / "escape.mp4").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    item = json.loads((root / "manifest.json").read_text())[0]
    item["video_path"] = "escape.mp4"
    (root / "manifest.json").write_text(json.dumps([item]))
    with pytest.raises(ValueError):
        load_manifest(root / "manifest.json", root)


def test_session_cannot_cross_splits(tmp_path):
    root = dataset(tmp_path, [
        dict(clip_id="a", recording_session_id="same", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted"),
        dict(clip_id="b", recording_session_id="same", video_path="clip.mp4", split="train", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted"),
    ])
    records = load_manifest(root / "manifest.json", root)
    with pytest.raises(ValueError):
        validate_dataset(records, {}, root)



def test_offset_source_timestamps_are_checked_against_final_pts(tmp_path, monkeypatch):
    root = dataset(tmp_path)
    records = load_manifest(root / "manifest.json", root)
    monkeypatch.setattr(benchmark, "_last_video_timestamp", lambda path: 10.5)
    labels = {"clip-a": {"r1": [benchmark.ReferenceEvent(event_type="leftmost", timestamp_seconds=10.4, evidence_frame_index=4, uncertainty_seconds=0.01)]}}
    validate_dataset(records, labels, root)


def _freeze_inputs(root, *, dev=False):
    records = [
        dict(clip_id="test-clip", recording_session_id="test-session", video_path="clip.mp4", split="test", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted"),
    ]
    if dev:
        records.append(dict(clip_id="dev-clip", recording_session_id="dev-session", video_path="clip.mp4", split="dev", scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted"))
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(records), encoding="utf-8")
    labels = root / "events.csv"
    labels.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds,notes\ntest-clip,r1,leftmost,0.1,1,0.01,first\ntest-clip,r1,leftmost,0.4,4,0.02,last\n", encoding="utf-8")
    return manifest, labels


def test_freeze_is_deterministic_and_never_overwrites(tmp_path):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    lock = tmp_path / "lock.json"
    first = benchmark.freeze_dataset(root, manifest, labels, lock, "a" * 40)
    lock.unlink()
    second = benchmark.freeze_dataset(root, manifest, labels, lock, "a" * 40)
    assert first == second
    assert json.loads(lock.read_text()) == first
    with pytest.raises(ValueError, match="already exists"):
        benchmark.freeze_dataset(root, manifest, labels, lock, "a" * 40)


def test_freeze_requires_test_clips(tmp_path):
    root = dataset(tmp_path)
    record = json.loads((root / "manifest.json").read_text())[0]
    record["split"] = "dev"
    (root / "manifest.json").write_text(json.dumps([record]))
    labels = root / "events.csv"
    labels.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\n", encoding="utf-8")
    with pytest.raises(ValueError, match="test clip"):
        benchmark.freeze_dataset(root, root / "manifest.json", labels, tmp_path / "lock.json", "a" * 40)


def test_lock_stores_relative_input_paths(tmp_path):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    lock = benchmark.freeze_dataset(root, manifest, labels, tmp_path / "lock.json", "a" * 40)
    assert lock["inputs"] == {"manifest_path": "manifest.json", "labels_path": "events.csv"}
    assert lock["session_splits"] == {"test-session": "test"}
    assert lock["test_clips"][0]["video_sha256"] == benchmark._sha256_file(root / "clip.mp4")
    assert lock["test_label_rows"][0]["timestamp_seconds"] == 0.1
    assert lock["test_label_rows_sha256"] == benchmark.hashlib.sha256(benchmark._canonical_json(lock["test_label_rows"])).hexdigest()
    assert "private" not in json.dumps(lock)


@pytest.mark.parametrize("mutation", ["media", "labels", "roi", "axis", "condition", "split"])
def test_frozen_test_inputs_must_match(tmp_path, mutation):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    lock_path = tmp_path / "lock.json"
    benchmark.freeze_dataset(root, manifest, labels, lock_path, "a" * 40)
    if mutation == "media":
        video(root / "clip.mp4", frames=7)
    elif mutation == "labels":
        labels.write_text(labels.read_text().replace(",0.01,first", ",0.03,first"))
    else:
        record = json.loads(manifest.read_text())[0]
        if mutation == "roi": record["initial_roi"]["x"] = 2
        if mutation == "axis": record["motion_axis"] = {"x": 0, "y": 1}
        if mutation == "condition": record["scene_condition"] = "static_clutter"
        if mutation == "split": record["split"] = "dev"
        manifest.write_text(json.dumps([record]))
    with pytest.raises(ValueError, match="frozen|lock|test"):
        benchmark.verify_frozen_inputs(root, lock_path)


def test_dev_only_changes_do_not_invalidate_lock(tmp_path):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root, dev=True)
    lock_path = tmp_path / "lock.json"
    benchmark.freeze_dataset(root, manifest, labels, lock_path, "a" * 40)
    labels.write_text(labels.read_text() + "dev-clip,r2,leftmost,0.2,2,0.01,dev only\n")
    assert benchmark.verify_frozen_inputs(root, lock_path)["source_commit"] == "a" * 40


@pytest.mark.parametrize("malformed", [False, True])
def test_lock_payload_digest_rejects_edits(tmp_path, malformed):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    lock_path = tmp_path / "lock.json"
    benchmark.freeze_dataset(root, manifest, labels, lock_path, "a" * 40)
    if malformed:
        lock_path.write_text("{")
    else:
        payload = json.loads(lock_path.read_text())
        payload["test_clips"][0]["clip_id"] = "edited"
        lock_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="digest|verify"):
        benchmark.verify_frozen_inputs(root, lock_path)


def test_lock_path_must_be_outside_repository(tmp_path):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    with pytest.raises(ValueError, match="outside the repository"):
        benchmark.freeze_dataset(root, manifest, labels, REPO / "benchmark-lock.json", "a" * 40)


@pytest.mark.parametrize("source_commit", [None, "", "not-a-commit", "a" * 39, "g" * 40])
def test_freeze_rejects_invalid_source_commit(tmp_path, source_commit):
    root = dataset(tmp_path)
    manifest, labels = _freeze_inputs(root)
    with pytest.raises(ValueError, match="source_commit"):
        benchmark.freeze_dataset(root, manifest, labels, tmp_path / "lock.json", source_commit)
