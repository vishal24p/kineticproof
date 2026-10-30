import csv
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from kineticproof_api import benchmark
from kineticproof_api.benchmark import load_event_labels, load_manifest, validate_dataset


REPO = Path(__file__).resolve().parents[3]


def _benchmark_cli(*args, cwd=REPO, source_root=REPO):
    environment = os.environ | {"PYTHONPATH": str(source_root / "services" / "api" / "src")}
    return subprocess.run(
        ["uv", "run", "--project", str(REPO / "services" / "api"), "python", "-m", "kineticproof_api.benchmark", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_cli_help_and_subcommands():
    help_result = _benchmark_cli("--help")
    assert help_result.returncode == 0
    assert "freeze" in help_result.stdout
    assert "run" in help_result.stdout

    for command in ("freeze", "run"):
        result = _benchmark_cli(command, "--help")
        assert result.returncode == 0
        assert f"benchmark {command}" in result.stdout

    assert _benchmark_cli().returncode == 2


def _clean_source_repository(tmp_path):
    source = tmp_path / "benchmark-source"
    shutil.copytree(REPO / "services" / "api" / "src", source / "services" / "api" / "src")
    (source / "docs").mkdir()
    shutil.copy2(REPO / "docs" / "benchmark_results_template.csv", source / "docs")
    for arguments in (("init",), ("config", "user.email", "test@example.invalid"),
                      ("config", "user.name", "Benchmark test"), ("add", "."),
                      ("commit", "-m", "benchmark source")):
        subprocess.run(["git", "-C", str(source), *arguments], check=True, capture_output=True, text=True)
    return source


def _synthetic_cli_dataset(tmp_path):
    root = tmp_path / "synthetic-private-dataset"
    clips = root / "clips"
    clips.mkdir(parents=True)
    writer = cv2.VideoWriter(str(clips / "synthetic.mp4"), cv2.CAP_FFMPEG,
                             cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for index in range(6):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        cv2.rectangle(frame, (8 + index, 18), (17 + index, 27), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    manifest = [{"clip_id": "synthetic-clip", "recording_session_id": "synthetic-session",
                 "video_path": "clips/synthetic.mp4", "split": "test", "scene_condition": "clean",
                 "initial_roi": {"x": 8, "y": 18, "width": 10, "height": 10},
                 "motion_axis": {"x": 1, "y": 0}, "rights_status": "permitted"}]
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "labels.csv").write_text(
        "clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\n"
        "synthetic-clip,rater-1,leftmost,0.1,1,0.01\n"
        "synthetic-clip,rater-1,leftmost,0.3,3,0.01\n",
        encoding="utf-8",
    )
    return root


def test_freeze_and_run_require_locked_clean_commit(tmp_path):
    source = _clean_source_repository(tmp_path)
    root = _synthetic_cli_dataset(tmp_path)
    lock = root / "lock.json"
    (source / "dirty.txt").write_text("dirty", encoding="utf-8")
    dirty_freeze = _benchmark_cli("freeze", "--dataset-root", str(root), "--manifest", str(root / "manifest.json"),
                                  "--labels", str(root / "labels.csv"), "--lock", str(lock),
                                  cwd=source, source_root=source)
    assert dirty_freeze.returncode == 1
    assert "clean" in dirty_freeze.stderr
    (source / "dirty.txt").unlink()

    frozen = _benchmark_cli("freeze", "--dataset-root", str(root), "--manifest", str(root / "manifest.json"),
                            "--labels", str(root / "labels.csv"), "--lock", str(lock),
                            cwd=source, source_root=source)
    assert frozen.returncode == 0

    (source / "dirty.txt").write_text("dirty", encoding="utf-8")
    dirty_run = _benchmark_cli("run", "--dataset-root", str(root), "--lock", str(lock),
                               "--output-dir", str(root / "dirty-report"), cwd=source, source_root=source)
    assert dirty_run.returncode == 1
    assert "clean" in dirty_run.stderr
    subprocess.run(["git", "-C", str(source), "add", "dirty.txt"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "change source"], check=True, capture_output=True, text=True)
    changed_head = _benchmark_cli("run", "--dataset-root", str(root), "--lock", str(lock),
                                  "--output-dir", str(root / "changed-head-report"), cwd=source, source_root=source)
    assert changed_head.returncode == 1
    assert "does not match" in changed_head.stderr


def test_synthetic_cli_freeze_run_and_mutation_rejection(tmp_path):
    """Synthetic fixture only; generated reports are not authentic benchmark evidence."""
    source = _clean_source_repository(tmp_path)
    root = _synthetic_cli_dataset(tmp_path)
    lock = root / "locks" / "synthetic.lock.json"
    lock.parent.mkdir()
    freeze = _benchmark_cli("freeze", "--dataset-root", str(root), "--manifest", str(root / "manifest.json"),
                            "--labels", str(root / "labels.csv"), "--lock", str(lock),
                            cwd=source, source_root=source)
    assert freeze.returncode == 0, freeze.stderr

    report = root / "reports" / "synthetic"
    run = _benchmark_cli("run", "--dataset-root", str(root), "--lock", str(lock), "--output-dir", str(report),
                         cwd=source, source_root=source)
    assert run.returncode == 0, run.stderr
    assert {path.name for path in report.iterdir()} == {"results.csv", "details.jsonl", "summary.json"}

    labels = root / "labels.csv"
    labels.write_text(labels.read_text(encoding="utf-8").replace(",0.3,3,", ",0.4,3,"), encoding="utf-8")
    rejected = _benchmark_cli("run", "--dataset-root", str(root), "--lock", str(lock),
                              "--output-dir", str(root / "reports" / "synthetic-mutated"),
                              cwd=source, source_root=source)
    assert rejected.returncode == 1
    assert "Frozen test inputs" in rejected.stderr


def video(path, frames=6, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.CAP_FFMPEG, cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    assert writer.isOpened()
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 10 % 256, dtype=np.uint8))
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



def test_source_timestamp_labels_must_fall_within_decoded_pts_bounds(tmp_path, monkeypatch):
    root = dataset(tmp_path)
    records = load_manifest(root / "manifest.json", root)
    monkeypatch.setattr(benchmark, "_video_timestamp_bounds", lambda path: (10.0, 10.5))
    labels = {"clip-a": {"r1": [benchmark.ReferenceEvent(event_type="leftmost", timestamp_seconds=10.4, evidence_frame_index=4, uncertainty_seconds=0.01)]}}
    validate_dataset(records, labels, root)
    labels["clip-a"]["r1"][0] = benchmark.ReferenceEvent(
        event_type="leftmost", timestamp_seconds=3.0, evidence_frame_index=4, uncertainty_seconds=0.01)
    with pytest.raises(ValueError, match="before clip start"):
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


def _runner_dataset(tmp_path, records=None, rows=()):
    root = tmp_path / "runner-private"
    root.mkdir()
    records = records or [
        dict(clip_id=f"clip-{i}", recording_session_id=f"session-{i}", video_path=f"{i}.mp4",
             split="test", scene_condition=condition, initial_roi=dict(x=1, y=1, width=10, height=10),
             motion_axis=dict(x=1, y=0), rights_status="permitted")
        for i, condition in enumerate(("clean", "static_clutter"))
    ]
    for record in records:
        video(root / record["video_path"], frames=41)
    manifest = root / "inputs" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps(records), encoding="utf-8")
    labels = root / "inputs" / "labels.csv"
    labels.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\n" +
                      "".join(",".join(map(str, row)) + "\n" for row in rows), encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    lock = benchmark.freeze_dataset(root, manifest, labels, lock_path, "a" * 40)
    return root, lock_path, lock


def _fake_trace(source_hash, status="succeeded"):
    return SimpleNamespace(
        status=status,
        frames=[SimpleNamespace(frame_index=0, timestamp_seconds=0, center_x_px=1, center_y_px=1,
                                quality_flags=[])],
        failures=[],
        provenance=SimpleNamespace(source_video_sha256=source_hash),
        model_dump=lambda **kwargs: {"status": status, "provenance": {"source_video_sha256": source_hash}},
    )


def _fake_measurement(measured=2.0, periods=(2.0,), status="succeeded", valid_fraction=1.0):
    intervals = [SimpleNamespace(event_type="leftmost", period_seconds=period) for period in periods]
    return SimpleNamespace(status=status, measured_period_seconds=measured, valid_frame_fraction=valid_fraction,
                           manual_reference_intervals=intervals,
                           manual_reference_period_seconds=statistics.median(periods) if periods else None,
                           warnings=[], model_dump=lambda **kwargs: {"status": status, "periods": list(periods)})


def test_run_reloads_locked_source_files_and_rejects_missing_or_changed_inputs(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path)
    # Decoys at the root prove the locked relative paths are authoritative.
    (root / "manifest.json").write_text("[]", encoding="utf-8")
    (root / "labels.csv").write_text("bad", encoding="utf-8")
    seen = []
    monkeypatch.setattr(benchmark, "track_video", lambda *args: (seen.append(args[0]) or _fake_trace(benchmark._sha256_file(args[0]))))
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: _fake_measurement())
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert len(seen) == 2

    seen.clear()
    (root / "inputs" / "labels.csv").unlink()
    with pytest.raises(ValueError):
        benchmark.run_benchmark(root, lock_path, tmp_path / "missing-report", "a" * 40)
    assert not seen


def test_run_rejects_changed_test_labels_before_scoring(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path, rows=[("clip-0", "r1", "leftmost", .1, 1, .01),
                                                           ("clip-0", "r1", "leftmost", .3, 3, .01)])
    (root / "inputs" / "labels.csv").write_text((root / "inputs" / "labels.csv").read_text().replace(",0.01\n", ",0.02\n"))
    monkeypatch.setattr(benchmark, "track_video", lambda *args: pytest.fail("must verify before tracking"))
    with pytest.raises(ValueError, match="frozen|changed"):
        benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)


def test_run_scores_the_verified_input_snapshot(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path, rows=[("clip-0", "r1", "leftmost", .1, 1, .01),
                                                           ("clip-0", "r1", "leftmost", .3, 3, .01)])
    original_manifest = benchmark.load_manifest
    original_labels = benchmark.load_event_labels

    def mutate_manifest_after_verified_load(*args):
        records = original_manifest(*args)
        payload = json.loads((root / "inputs" / "manifest.json").read_text())
        payload[0]["initial_roi"]["x"] = 2
        payload[0]["motion_axis"] = {"x": 0, "y": 1}
        payload[0]["scene_condition"] = "moving_background"
        (root / "inputs" / "manifest.json").write_text(json.dumps(payload))
        return records

    def mutate_labels_after_verified_load(*args):
        labels = original_labels(*args)
        path = root / "inputs" / "labels.csv"
        path.write_text(path.read_text().replace(",0.3,3,", ",0.4,3,"), encoding="utf-8")
        return labels

    monkeypatch.setattr(benchmark, "load_manifest", mutate_manifest_after_verified_load)
    monkeypatch.setattr(benchmark, "load_event_labels", mutate_labels_after_verified_load)
    monkeypatch.setattr(benchmark, "track_video", lambda path, metadata, roi, *args: (
        roi.x == 1 or pytest.fail("run used a manifest reloaded after verification"),
        _fake_trace(benchmark._sha256_file(path)),
    )[1])
    monkeypatch.setattr(benchmark, "measure_trace", lambda trace, request: (
        [event.timestamp_seconds for event in request.reference_events] == [.1, .3]
        or pytest.fail("run used labels reloaded after verification"),
        _fake_measurement(),
    )[1])

    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert summary["conditions"]["clean"]["test_clip_count"] == 1
    assert summary["conditions"]["moving_background"]["test_clip_count"] == 0


def test_run_requires_locked_source_commit_and_output_outside_repository(tmp_path):
    root, lock_path, _ = _runner_dataset(tmp_path)
    with pytest.raises(ValueError, match="source_commit"):
        benchmark.run_benchmark(root, lock_path, tmp_path / "report", "b" * 40)
    with pytest.raises(ValueError, match="outside the repository"):
        benchmark.run_benchmark(root, lock_path, REPO / "benchmark-output", "a" * 40)


@pytest.mark.parametrize("report_name", ["results.csv", "details.jsonl", "summary.json"])
def test_run_rejects_redirected_report_files(tmp_path, monkeypatch, report_name):
    root, lock_path, _ = _runner_dataset(tmp_path)
    output = tmp_path / "report"
    output.mkdir()
    redirected = tmp_path / f"redirected-{report_name}"
    redirected.write_text("private data", encoding="utf-8")
    try:
        (output / report_name).symlink_to(redirected)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    monkeypatch.setattr(benchmark, "track_video", lambda *args: pytest.fail("must reject report path before tracking"))
    with pytest.raises(ValueError, match="symlink"):
        benchmark.run_benchmark(root, lock_path, output, "a" * 40)
    assert redirected.read_text(encoding="utf-8") == "private data"


@pytest.mark.parametrize("report_name", ["results.csv", "details.jsonl", "summary.json"])
def test_run_rejects_hard_linked_report_files_without_modifying_target(tmp_path, monkeypatch, report_name):
    root, lock_path, _ = _runner_dataset(tmp_path)
    output = tmp_path / "report"
    output.mkdir()
    descriptor, temporary_name = tempfile.mkstemp(prefix=".benchmark-hardlink-", dir=REPO)
    os.close(descriptor)
    disposable = Path(temporary_name)
    report = output / report_name
    try:
        disposable.write_text("private data", encoding="utf-8")
        try:
            os.link(disposable, report)
        except (OSError, NotImplementedError):
            pytest.skip("hard-link creation is unavailable")
        monkeypatch.setattr(benchmark, "track_video", lambda *args: pytest.fail("must reject report path before tracking"))
        with pytest.raises(ValueError, match="already exists"):
            benchmark.run_benchmark(root, lock_path, output, "a" * 40)
        assert disposable.read_text(encoding="utf-8") == "private data"
        assert list(output.iterdir()) == [report]
    finally:
        report.unlink(missing_ok=True)
        disposable.unlink(missing_ok=True)


def test_run_rejects_report_file_collision_with_dataset_input(tmp_path, monkeypatch):
    root = tmp_path / "runner-private"
    root.mkdir()
    records = [dict(clip_id="clip-0", recording_session_id="session-0", video_path="0.mp4", split="test",
                    scene_condition="clean", initial_roi=dict(x=1, y=1, width=10, height=10),
                    motion_axis=dict(x=1, y=0), rights_status="permitted")]
    video(root / "0.mp4", frames=41)
    inputs = root / "inputs"
    inputs.mkdir()
    manifest = inputs / "manifest.json"
    labels = inputs / "results.csv"
    manifest.write_text(json.dumps(records), encoding="utf-8")
    labels.write_text("clip_id,rater_id,event_type,timestamp_seconds,evidence_frame_index,uncertainty_seconds\n", encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    benchmark.freeze_dataset(root, manifest, labels, lock_path, "a" * 40)
    monkeypatch.setattr(benchmark, "track_video", lambda *args: pytest.fail("must reject input collision before tracking"))
    with pytest.raises(ValueError, match="collides"):
        benchmark.run_benchmark(root, lock_path, inputs, "a" * 40)
    assert "clip_id,rater_id" in labels.read_text(encoding="utf-8")


def test_clip_is_tracked_once_and_each_rater_is_scored_separately(tmp_path, monkeypatch):
    rows = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "rightmost", .2, 2, .01),
            ("clip-0", "r1", "leftmost", .4, 4, .01), ("clip-0", "r1", "leftmost", .8, 8, .01),
            ("clip-0", "r2", "same_direction", .1, 1, .01), ("clip-0", "r2", "same_direction", .5, 5, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, rows=rows)
    tracked, measured = [], []
    trace = _fake_trace(benchmark._sha256_file(root / "0.mp4"))
    monkeypatch.setattr(benchmark, "track_video", lambda *args: (tracked.append(args) or trace))
    monkeypatch.setattr(benchmark, "measure_trace", lambda actual, request: (measured.append((actual, request)) or _fake_measurement()))
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert len(tracked) == 2
    assert len(measured) == 2
    r1 = next(request for _, request in measured if request.reference_events[0].event_type == "leftmost")
    assert [event.event_type for event in r1.reference_events] == ["leftmost", "rightmost", "leftmost", "leftmost"]
    assert all(actual is trace for actual, _ in measured)


def test_reference_eligibility_requires_same_type_pair(tmp_path, monkeypatch):
    rows = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "rightmost", .2, 2, .01),
            ("clip-0", "r2", "leftmost", .1, 1, .01), ("clip-0", "r2", "leftmost", .3, 3, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, rows=rows)
    monkeypatch.setattr(benchmark, "track_video", lambda *args: _fake_trace(benchmark._sha256_file(args[0])))
    monkeypatch.setattr(benchmark, "measure_trace", lambda trace, request: _fake_measurement(periods=(.2,) if len(request.reference_events) == 2 and request.reference_events[0].event_type == "leftmost" else ()))
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    r1 = next(row for row in rows if row["rater_id"] == "r1")
    r2 = next(row for row in rows if row["rater_id"] == "r2")
    assert r1["rater_eligible"] == "false"
    assert r1["rater_ineligibility_reason"]
    assert r2["rater_eligible"] == "true"


def test_scores_weight_clips_equally_and_keep_rater_spread(tmp_path, monkeypatch):
    rows = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "leftmost", .3, 3, .01),
            ("clip-0", "r2", "leftmost", .1, 2, .01), ("clip-0", "r2", "leftmost", .5, 5, .01),
            ("clip-1", "r3", "leftmost", .1, 1, .01), ("clip-1", "r3", "leftmost", .4, 4, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, rows=rows)
    monkeypatch.setattr(benchmark, "track_video", lambda *args: _fake_trace(benchmark._sha256_file(args[0])))
    def measure(trace, request):
        return _fake_measurement(measured=1.0 if request.reference_events[0].evidence_frame_index == 1 else 2.0,
                                 periods=(1.0, 3.0) if request.reference_events[0].evidence_frame_index == 1 else (3.0,))
    monkeypatch.setattr(benchmark, "measure_trace", measure)
    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    clip0 = [row for row in rows if row["clip_id"] == "clip-0"]
    clip1 = next(row for row in rows if row["clip_id"] == "clip-1")
    assert [float(row["rater_absolute_error_s"]) for row in clip0] == [.8, 1.6]
    assert all(float(row["reference_period_range_s"]) == pytest.approx(.2) for row in clip0)
    assert clip1["reference_period_range_s"] == ""
    assert summary["scored_clip_count"] == 2
    assert summary["median_absolute_error_s"] == pytest.approx(.95)
    assert summary["median_absolute_deviation_s"] == pytest.approx(.25)


def test_report_keeps_missing_failed_partial_and_insufficient_clips(tmp_path, monkeypatch):
    records = [dict(clip_id=f"clip-{i}", recording_session_id=f"s{i}", video_path=f"{i}.mp4", split="test",
                    scene_condition=condition, initial_roi=dict(x=1,y=1,width=10,height=10), motion_axis=dict(x=1,y=0), rights_status="permitted")
               for i, condition in enumerate(("clean", "static_clutter", "moving_background"))]
    rows = [("clip-1", "r1", "leftmost", .1, 1, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, records, rows)
    def track(path, *args):
        if path.name == "0.mp4": raise RuntimeError("decoder broke")
        return _fake_trace(benchmark._sha256_file(path), "partial" if path.name == "1.mp4" else "succeeded")
    monkeypatch.setattr(benchmark, "track_video", track)
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: _fake_measurement(measured=None, periods=(), status="insufficient_data", valid_fraction=.5))
    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    report = json.loads((tmp_path / "report" / "summary.json").read_text())
    assert summary == report
    assert summary["test_clip_count"] == 3
    assert summary["tracking_failed_count"] == 1
    assert summary["tracking_partial_count"] == 1
    assert summary["insufficient_measurement_count"] == 1
    assert summary["missing_reference_clip_count"] == 2
    assert summary["ineligible_reference_clip_count"] == 1
    assert summary["scored_clip_count"] == 0
    assert sum(item["test_clip_count"] for item in summary["conditions"].values()) == 3
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        csv_rows = list(csv.DictReader(source))
    assert len(csv_rows) == 3
    assert csv_rows[0]["rater_id"] == ""
    assert "no_reference_annotations" in (csv_rows[0]["rater_ineligibility_reason"], csv_rows[0]["abstention_reason"])
    details = [json.loads(line) for line in (tmp_path / "report" / "details.jsonl").read_text().splitlines()]
    assert len(details) == 3 and details[0]["tracking_error"]


def test_reports_schema_and_unavailable_metrics(tmp_path, monkeypatch):
    root, lock_path, lock = _runner_dataset(tmp_path)
    monkeypatch.setattr(benchmark, "track_video", lambda *args: _fake_trace(benchmark._sha256_file(args[0])))
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: _fake_measurement())
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
    template = next(csv.reader((REPO / "docs" / "benchmark_results_template.csv").open(encoding="utf-8")))
    assert reader.fieldnames == template
    assert len(rows) == 2
    assert rows[0]["bob_center_error_px"] == rows[0]["id_switches"] == rows[0]["matched_visible_frame_coverage"] == ""
    assert rows[0]["unavailable_metrics_reason"]
    summary = json.loads((tmp_path / "report" / "summary.json").read_text())
    assert summary["source_commit"] == "a" * 40
    assert summary["lock_payload_sha256"] == lock["payload_sha256"]
    assert summary["latency_description"]
    assert {item.name for item in (tmp_path / "report").iterdir()} == {"results.csv", "details.jsonl", "summary.json"}


def test_latency_covers_tracking_and_all_rater_measurements(tmp_path, monkeypatch):
    rows = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "leftmost", .3, 3, .01),
            ("clip-0", "r2", "leftmost", .1, 1, .01), ("clip-0", "r2", "leftmost", .4, 4, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, rows=rows)
    ticks = iter((10, 17, 17, 21))
    monkeypatch.setattr(benchmark.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(benchmark, "track_video", lambda *args: _fake_trace(benchmark._sha256_file(args[0])))
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: _fake_measurement())
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert {row["latency_s"] for row in rows if row["clip_id"] == "clip-0"} == {"7"}


def test_tracking_exception_is_reported_as_failed_clip(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path)
    monkeypatch.setattr(benchmark, "track_video", lambda *args: (_ for _ in ()).throw(ValueError("decoder failure")))
    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert summary["tracking_failed_count"] == 2
    details = [json.loads(line) for line in (tmp_path / "report" / "details.jsonl").read_text().splitlines()]
    assert all(item["tracking_error"] == "decoder failure" for item in details)


def test_temporary_overlay_is_removed_after_each_clip(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path)
    overlays = []
    def track(path, metadata, roi, clip_id, overlay):
        overlays.append(overlay)
        if path.name == "0.mp4": raise RuntimeError("tracking failed")
        return _fake_trace(benchmark._sha256_file(path))
    monkeypatch.setattr(benchmark, "track_video", track)
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: _fake_measurement())
    benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert len(overlays) == 2 and all(not path.exists() for path in overlays)


def test_source_change_during_tracking_is_not_scored(tmp_path, monkeypatch):
    rows = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "leftmost", .3, 3, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, rows=rows)
    def track(path, *args):
        old_hash = benchmark._sha256_file(path)
        if path.name == "0.mp4":
            path.write_bytes(path.read_bytes() + b"changed")
        return _fake_trace(old_hash)
    monkeypatch.setattr(benchmark, "track_video", track)
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: pytest.fail("changed source must not be scored"))
    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    assert summary["tracking_failed_count"] == 1
    with (tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8") as source:
        row = next(row for row in csv.DictReader(source) if row["clip_id"] == "clip-0")
    assert row["rater_absolute_error_s"] == ""


def test_source_change_then_tracking_exception_is_reported_and_not_scored(tmp_path, monkeypatch):
    records = [dict(clip_id="clip-0", recording_session_id="session-0", video_path="0.mp4", split="test",
                    scene_condition="clean", initial_roi=dict(x=1,y=1,width=10,height=10),
                    motion_axis=dict(x=1,y=0), rights_status="permitted")]
    labels = [("clip-0", "r1", "leftmost", .1, 1, .01), ("clip-0", "r1", "leftmost", .3, 3, .01)]
    root, lock_path, _ = _runner_dataset(tmp_path, records, labels)

    def mutate_then_fail(path, *args):
        path.write_bytes(path.read_bytes() + b"changed")
        raise RuntimeError("decoder failed after mutation")

    monkeypatch.setattr(benchmark, "track_video", mutate_then_fail)
    monkeypatch.setattr(benchmark, "measure_trace", lambda *args: pytest.fail("changed source must not be scored"))
    summary = benchmark.run_benchmark(root, lock_path, tmp_path / "report", "a" * 40)
    row = next(csv.DictReader((tmp_path / "report" / "results.csv").open(newline="", encoding="utf-8")))
    detail = json.loads((tmp_path / "report" / "details.jsonl").read_text(encoding="utf-8"))
    assert summary["tracking_failed_count"] == 1
    assert summary["scored_clip_count"] == 0
    assert row["tracking_status"] == "failed"
    assert row["rater_absolute_error_s"] == ""
    assert detail["source_changed_during_tracking"] is True
    assert detail["tracking_error"] == "decoder failed after mutation"
    assert benchmark._sha256_file(root / "0.mp4") != json.loads(lock_path.read_text())["test_clips"][0]["video_sha256"]


def test_existing_report_directory_fails_without_success_summary(tmp_path, monkeypatch):
    root, lock_path, _ = _runner_dataset(tmp_path)
    output = tmp_path / "report"
    output.mkdir()
    (output / "results.csv").mkdir()
    monkeypatch.setattr(benchmark, "track_video", lambda *args: _fake_trace(benchmark._sha256_file(args[0])))
    with pytest.raises(ValueError, match="already exists"):
        benchmark.run_benchmark(root, lock_path, output, "a" * 40)
    assert not (output / "summary.json").exists()
