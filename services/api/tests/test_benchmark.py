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
