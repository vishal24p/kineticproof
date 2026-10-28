"""Private, local benchmark input validation."""

import csv
import hashlib
import json
from pathlib import Path
import re

import cv2
from pydantic import ValidationError

from kineticproof_api.main import MAX_DURATION_SECONDS, MAX_UPLOAD_BYTES
from kineticproof_api.physics import MotionAxis, ReferenceEvent
from kineticproof_api.tracking import InitialROI, inspect_video

SPLITS = {"demo", "train", "dev", "test"}
CONDITIONS = {"clean", "static_clutter", "moving_background"}
MANIFEST_FIELDS = {"clip_id", "recording_session_id", "video_path", "split", "scene_condition", "initial_roi", "motion_axis", "rights_status"}
EVENT_FIELDS = {"clip_id", "rater_id", "event_type", "timestamp_seconds", "evidence_frame_index", "uncertainty_seconds"}
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LOCK_VERSION = 1
BENCHMARK_CONFIGURATION = {"tracker": "opencv_csrt", "measurement": "pendulum_period_from_reference_events"}


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _private_path(path, dataset_root, label):
    root = Path(dataset_root).resolve()
    resolved = Path(path).resolve()
    if _inside(root, REPOSITORY_ROOT):
        raise ValueError("dataset_root must be outside the repository checkout")
    if not _inside(resolved, root):
        raise ValueError(f"{label} must resolve within dataset_root")
    if _inside(resolved, REPOSITORY_ROOT):
        raise ValueError(f"{label} must be outside the repository checkout")
    return root, resolved


def _last_video_timestamp(path: Path) -> float:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        fps = capture.get(cv2.CAP_PROP_FPS)
        timestamp = None
        while capture.read()[0]:
            timestamp = capture.get(cv2.CAP_PROP_PTS) / fps
        if timestamp is None:
            raise ValueError("Video has no source timestamps")
        return timestamp
    finally:
        capture.release()


def load_manifest(path, dataset_root) -> list[dict]:
    root, manifest_path = _private_path(path, dataset_root, "manifest path")
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read benchmark manifest: {error}") from error
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest must contain a non-empty JSON array")
    seen, result = set(), []
    for index, record in enumerate(records):
        where = f"manifest record {index + 1}"
        if not isinstance(record, dict) or not MANIFEST_FIELDS <= record.keys():
            raise ValueError(f"{where} must contain {', '.join(sorted(MANIFEST_FIELDS))}")
        clip_id, session = record["clip_id"], record["recording_session_id"]
        if not isinstance(clip_id, str) or not clip_id.strip() or not isinstance(session, str) or not session.strip():
            raise ValueError(f"{where} requires non-empty clip_id and recording_session_id")
        if clip_id in seen:
            raise ValueError(f"Duplicate clip_id: {clip_id}")
        seen.add(clip_id)
        if not isinstance(record["split"], str) or record["split"] not in SPLITS:
            raise ValueError(f"{where} has unsupported split")
        if not isinstance(record["scene_condition"], str) or record["scene_condition"] not in CONDITIONS:
            raise ValueError(f"{where} has unsupported scene_condition")
        if record["rights_status"] != "permitted":
            raise ValueError(f"{where} requires rights_status='permitted'")
        try:
            roi = InitialROI.model_validate(record["initial_roi"])
            axis = MotionAxis.model_validate(record["motion_axis"])
        except (ValidationError, TypeError) as error:
            raise ValueError(f"{where} has invalid initial_roi or motion_axis: {error}") from error
        video_rel = Path(record["video_path"]) if isinstance(record["video_path"], str) else Path(".")
        if video_rel.is_absolute():
            raise ValueError(f"{where} video_path must be relative")
        video_path = (root / video_rel).resolve()
        if not _inside(video_path, root) or _inside(video_path, REPOSITORY_ROOT):
            raise ValueError(f"{where} video_path escapes the private dataset_root")
        if not video_path.is_file():
            raise ValueError(f"{where} video file does not exist: {record['video_path']}")
        if video_path.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError(f"{where} video exceeds the {MAX_UPLOAD_BYTES}-byte media limit")
        try:
            metadata = inspect_video(video_path)
        except (ValueError, OSError) as error:
            raise ValueError(f"{where} video is unsupported or invalid: {error}") from error
        if metadata.duration_seconds > MAX_DURATION_SECONDS:
            raise ValueError(f"{where} video exceeds the {MAX_DURATION_SECONDS}-second media limit")
        if roi.x + roi.width > metadata.width or roi.y + roi.height > metadata.height:
            raise ValueError(f"{where} initial_roi must fit within the first video frame")
        result.append({**record, "video_path": video_rel.as_posix(), "initial_roi": roi, "motion_axis": axis, "_resolved_video_path": video_path, "_video_metadata": metadata})
    return result


def load_event_labels(path, dataset_root, clip_ids) -> dict[str, dict[str, list[ReferenceEvent]]]:
    _, labels_path = _private_path(path, dataset_root, "event-label path")
    try:
        with labels_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or not EVENT_FIELDS <= set(reader.fieldnames):
                raise ValueError(f"Event CSV must contain {', '.join(sorted(EVENT_FIELDS))}")
            grouped = {}
            seen = set()
            for line, row in enumerate(reader, 2):
                clip_id, rater_id = row["clip_id"], row["rater_id"]
                if clip_id not in clip_ids:
                    raise ValueError(f"Event row {line} references unknown clip_id {clip_id!r}")
                if not rater_id or not rater_id.strip():
                    raise ValueError(f"Event row {line} requires a pseudonymous rater_id")
                try:
                    event = ReferenceEvent(event_type=row["event_type"], timestamp_seconds=float(row["timestamp_seconds"]), evidence_frame_index=int(row["evidence_frame_index"]), uncertainty_seconds=float(row["uncertainty_seconds"]), notes=row.get("notes") or None)
                    if event.timestamp_seconds < 0:
                        raise ValueError("timestamp_seconds must be non-negative")
                except (ValidationError, TypeError, ValueError) as error:
                    raise ValueError(f"Invalid event row {line}: {error}") from error
                key = (clip_id, rater_id, event.timestamp_seconds)
                if key in seen:
                    raise ValueError(f"Duplicate timestamp for clip {clip_id}, rater {rater_id}: {event.timestamp_seconds}")
                seen.add(key)
                grouped.setdefault(clip_id, {}).setdefault(rater_id, []).append(event)
    except OSError as error:
        raise ValueError(f"Cannot read event-label CSV: {error}") from error
    for raters in grouped.values():
        for events in raters.values():
            events.sort(key=lambda event: event.timestamp_seconds)
    return grouped


def validate_dataset(manifest, labels, dataset_root) -> None:
    root = Path(dataset_root).resolve()
    if _inside(root, REPOSITORY_ROOT):
        raise ValueError("dataset_root must be outside the repository checkout")
    sessions, records = {}, {}
    for record in manifest:
        if record.get("rights_status") != "permitted":
            raise ValueError(f"Clip {record.get('clip_id')!r} requires rights_status='permitted'")
        if (not isinstance(record.get("split"), str) or record["split"] not in SPLITS
                or not isinstance(record.get("scene_condition"), str)
                or record["scene_condition"] not in CONDITIONS):
            raise ValueError(f"Clip {record.get('clip_id')!r} has an unsupported split or scene_condition")
        session, split = record["recording_session_id"], record["split"]
        if session in sessions and sessions[session] != split:
            raise ValueError(f"Recording session {session!r} crosses splits")
        sessions[session] = split
        if record["clip_id"] in records:
            raise ValueError(f"Duplicate clip_id: {record['clip_id']}")
        video_path = (root / record["video_path"]).resolve()
        if not _inside(video_path, root) or _inside(video_path, REPOSITORY_ROOT):
            raise ValueError(f"Clip {record['clip_id']!r} video_path escapes the private dataset_root")
        records[record["clip_id"]] = record
    unknown = set(labels) - records.keys()
    if unknown:
        raise ValueError(f"Labels contain unknown clips: {', '.join(sorted(unknown))}")
    for clip_id, raters in labels.items():
        metadata = records[clip_id].get("_video_metadata")
        if metadata is None:
            metadata = inspect_video(Path(dataset_root) / records[clip_id]["video_path"])
        last_timestamp = _last_video_timestamp(
            records[clip_id].get("_resolved_video_path", root / records[clip_id]["video_path"])
        )
        for rater_id, events in raters.items():
            for event in events:
                if event.evidence_frame_index >= metadata.frame_count:
                    raise ValueError(f"Evidence frame index out of range for clip {clip_id}, rater {rater_id}")
                if event.timestamp_seconds > last_timestamp:
                    raise ValueError(f"Event timestamp exceeds clip duration for clip {clip_id}, rater {rater_id}")


def _canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_test_inputs(manifest, labels, dataset_root):
    root = Path(dataset_root).resolve()
    test_records = []
    for record in sorted((item for item in manifest if item["split"] == "test"), key=lambda item: item["clip_id"]):
        test_records.append({
            "clip_id": record["clip_id"],
            "recording_session_id": record["recording_session_id"],
            "video_path": record["video_path"],
            "split": record["split"],
            "scene_condition": record["scene_condition"],
            "initial_roi": record["initial_roi"].model_dump(mode="json"),
            "motion_axis": record["motion_axis"].model_dump(mode="json"),
            "rights_status": record["rights_status"],
            "video_sha256": _sha256_file(record["_resolved_video_path"]),
        })
    test_ids = {record["clip_id"] for record in test_records}
    label_rows = []
    for clip_id in sorted(test_ids):
        for rater_id in sorted(labels.get(clip_id, {})):
            for event in labels[clip_id][rater_id]:
                label_rows.append({
                    "clip_id": clip_id,
                    "rater_id": rater_id,
                    "event_type": event.event_type,
                    "timestamp_seconds": event.timestamp_seconds,
                    "evidence_frame_index": event.evidence_frame_index,
                    "uncertainty_seconds": event.uncertainty_seconds,
                    "notes": event.notes,
                })
    return test_records, label_rows


def _lock_payload(dataset_root, manifest_path, labels_path, source_commit):
    root, manifest_file = _private_path(manifest_path, dataset_root, "manifest path")
    _, labels_file = _private_path(labels_path, root, "event-label path")
    manifest = load_manifest(manifest_file, root)
    labels = load_event_labels(labels_file, root, {record["clip_id"] for record in manifest})
    validate_dataset(manifest, labels, root)
    test_records, label_rows = _canonical_test_inputs(manifest, labels, root)
    if not test_records:
        raise ValueError("Dataset must contain at least one test clip")
    sessions = {record["recording_session_id"]: record["split"] for record in manifest}
    return {
        "version": LOCK_VERSION,
        "inputs": {
            "manifest_path": manifest_file.relative_to(root).as_posix(),
            "labels_path": labels_file.relative_to(root).as_posix(),
        },
        "source_commit": source_commit,
        "configuration": BENCHMARK_CONFIGURATION,
        "session_splits": dict(sorted(sessions.items())),
        "test_clips": test_records,
        "test_label_rows": label_rows,
        "test_label_rows_sha256": hashlib.sha256(_canonical_json(label_rows)).hexdigest(),
    }


def freeze_dataset(dataset_root, manifest_path, labels_path, lock_path, source_commit):
    if not isinstance(source_commit, str) or re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", source_commit) is None:
        raise ValueError("source_commit must be a full 40- or 64-character hexadecimal Git commit")
    lock_file = Path(lock_path).resolve()
    if _inside(lock_file, REPOSITORY_ROOT):
        raise ValueError("lock_path must be outside the repository checkout")
    payload = _lock_payload(dataset_root, manifest_path, labels_path, source_commit.lower())
    lock = {**payload, "payload_sha256": hashlib.sha256(_canonical_json(payload)).hexdigest()}
    try:
        with lock_file.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(lock, target, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            target.write("\n")
    except FileExistsError as error:
        raise ValueError(f"Lock file already exists: {lock_file}") from error
    return lock


def verify_frozen_inputs(dataset_root, lock_path):
    lock_file = Path(lock_path).resolve()
    if _inside(lock_file, REPOSITORY_ROOT):
        raise ValueError("lock_path must be outside the repository checkout")
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
        if not isinstance(lock, dict):
            raise ValueError("Lock must be a JSON object")
        payload = {key: value for key, value in lock.items() if key != "payload_sha256"}
        expected_digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
        if lock.get("payload_sha256") != expected_digest:
            raise ValueError("Lock payload digest does not match")
        if lock.get("version") != LOCK_VERSION:
            raise ValueError("Unsupported benchmark lock version")
        if not isinstance(lock.get("source_commit"), str) or re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", lock["source_commit"]) is None:
            raise ValueError("Lock source_commit metadata is invalid")
        inputs = lock["inputs"]
        manifest_path, labels_path = inputs["manifest_path"], inputs["labels_path"]
        if not isinstance(manifest_path, str) or not isinstance(labels_path, str):
            raise ValueError("Lock input paths must be relative strings")
        root = Path(dataset_root).resolve()
        current = _lock_payload(root, root / manifest_path, root / labels_path, lock["source_commit"])
        if current != payload:
            raise ValueError("Frozen test inputs or session split map changed; create a new lock")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"Cannot verify benchmark lock: {error}") from error
    return lock
