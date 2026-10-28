"""Local video inspection and CSRT traces using source presentation timestamps."""

from dataclasses import dataclass
from hashlib import file_digest
from math import isfinite
from pathlib import Path
from typing import Literal

import cv2
from pydantic import BaseModel, Field, StrictInt


class UnsupportedContainer(ValueError):
    pass


def validate_container(path: Path) -> None:
    """Require complete MP4/MOV top-level boxes, including movie and media data."""
    length = path.stat().st_size
    position = 0
    kinds = set()
    supported_brands = {
        b"isom", b"iso2", b"mp41", b"mp42", b"qt  ",
        b"avc1", b"av01", b"M4V ",
    }
    with path.open("rb") as source:
        while position < length:
            source.seek(position)
            header = source.read(8)
            if len(header) != 8:
                break
            size = int.from_bytes(header[:4], "big")
            kind = header[4:]
            header_size = 8
            if size == 1:
                extended = source.read(8)
                if len(extended) != 8:
                    break
                size = int.from_bytes(extended, "big")
                header_size = 16
            elif size == 0:
                size = length - position
            if size < header_size or size > length - position:
                break
            if kind == b"ftyp":
                payload_size = size - header_size
                if b"ftyp" in kinds or payload_size < 8 or payload_size % 4:
                    raise UnsupportedContainer("Invalid MP4/MOV file type brands")
                major_brand = source.read(4)
                source.read(4)  # Minor version is not a brand.
                # Parse compatible brands without letting them rescue an unsupported major.
                for _ in range((payload_size - 8) // 4):
                    compatible_brand = source.read(4)
                    if len(compatible_brand) != 4:
                        raise UnsupportedContainer("Invalid MP4/MOV compatible brand")
                if major_brand not in supported_brands:
                    raise UnsupportedContainer("Only MP4 and MOV brands are supported")
            kinds.add(kind)
            position += size
    if position != length or not {b"ftyp", b"moov", b"mdat"}.issubset(kinds):
        raise UnsupportedContainer("Only MP4 and MOV containers are supported")


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    frame_count: int
    fps: float


class InitialROI(BaseModel):
    x: StrictInt = Field(ge=0)
    y: StrictInt = Field(ge=0)
    width: StrictInt = Field(gt=0)
    height: StrictInt = Field(gt=0)


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class TrackFrame:
    frame_index: int
    timestamp_seconds: float
    bbox_px: BoundingBox | None
    center_x_px: float | None
    center_y_px: float | None
    quality_flags: list[str]


@dataclass(frozen=True)
class TrackingFailure:
    frame_index: int
    reason: str
    recovery_suggestion: str


@dataclass(frozen=True)
class Provenance:
    source_video_sha256: str
    preprocessing: str
    timebase_seconds_per_tick: float
    requested_frames: int
    opencv_version: str


@dataclass(frozen=True)
class TrackResult:
    schema_version: str
    experiment_id: str | None
    video_id: str
    provider_name: str
    model_name: str
    model_version: str
    run_config_id: str
    status: Literal["succeeded", "partial", "failed"]
    frames: list[TrackFrame]
    failures: list[TrackingFailure]
    provenance: Provenance


@dataclass(frozen=True)
class TrackingRun:
    trace: TrackResult
    overlay_path: Path


class OverlayError(RuntimeError):
    pass


def decoded_frames(capture, fps: float):
    """Yield source PTS in seconds; never synthesize missing timestamps."""
    if not isfinite(fps) or fps <= 0:
        raise ValueError("Video timestamp timebase unavailable")
    previous_timestamp = None
    dimensions = None
    frame_index = 0
    while True:
        decoded, frame = capture.read()
        if not decoded:
            break
        timestamp = capture.get(cv2.CAP_PROP_PTS) / fps
        if not isfinite(timestamp) or (
            previous_timestamp is not None and timestamp <= previous_timestamp
        ):
            raise ValueError("Video timestamps unavailable or nonmonotonic")
        if dimensions is None:
            dimensions = frame.shape[:2]
        if frame.shape[:2] != dimensions:
            raise ValueError("Video frame dimensions change during decoding")
        yield frame_index, timestamp, frame
        previous_timestamp = timestamp
        frame_index += 1


def inspect_video(path: Path) -> VideoMetadata:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        validate_container(path)
        fps = capture.get(cv2.CAP_PROP_FPS)
        expected_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        first_timestamp = previous_timestamp = None
        frame_count = 0
        width = height = 0
        for _, timestamp, frame in decoded_frames(capture, fps):
            if first_timestamp is None:
                first_timestamp = timestamp
                height, width = frame.shape[:2]
            previous_timestamp = timestamp
            frame_count += 1
        if not frame_count or (expected_count > 0 and frame_count != expected_count):
            raise ValueError("Video is empty or could not be fully decoded")
        if frame_count < 2:
            raise ValueError("At least two frames are required to validate video timestamps")
        return VideoMetadata(
            previous_timestamp - first_timestamp, width, height, frame_count, fps
        )
    except cv2.error as error:
        raise ValueError("Video cannot be decoded") from error
    finally:
        capture.release()


def draw_overlay_frame(writer, frame, timestamp: float, box: BoundingBox | None):
    try:
        if box is not None:
            cv2.rectangle(frame, (box.x, box.y),
                          (box.x + box.width, box.y + box.height), (0, 255, 0), 1)
        label = f"PTS {timestamp:.3f}s"
        if box is None:
            label += " tracking_failed"
        cv2.putText(frame, label, (2, 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.3, (0, 255, 255), 1)
        writer.write(frame)
    except (cv2.error, OSError) as error:
        raise OverlayError("Overlay frame could not be written") from error


def normalize_box(box_values, width: int, height: int) -> BoundingBox | None:
    try:
        if len(box_values) != 4 or not all(isfinite(value) for value in box_values):
            return None
        x, y, box_width, box_height = box_values
        if (x < 0 or y < 0 or box_width <= 0 or box_height <= 0
                or x + box_width > width or y + box_height > height):
            return None
        box = BoundingBox(*(round(value) for value in box_values))
    except (OverflowError, TypeError, ValueError):
        return None
    if (box.x < 0 or box.y < 0 or box.width <= 0 or box.height <= 0
            or box.x + box.width > width or box.y + box.height > height):
        return None
    return box


def track_video(source_path: Path, metadata: VideoMetadata, roi: InitialROI,
                observation_id: str, overlay_path: Path) -> TrackResult:
    """Run one local CSRT pass. Publish neither output until this returns."""
    if roi.x + roi.width > metadata.width or roi.y + roi.height > metadata.height:
        raise ValueError("Initial ROI must fit within the first frame")
    capture = cv2.VideoCapture(str(source_path), cv2.CAP_FFMPEG)
    writer = None
    completed = False
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        fps = capture.get(cv2.CAP_PROP_FPS)
        tracker = cv2.TrackerCSRT_create()
        frames = []
        failures = []
        for index, timestamp, frame in decoded_frames(capture, fps):
            if frame.shape[:2] != (metadata.height, metadata.width):
                raise ValueError("Video dimensions differ from uploaded metadata")
            if index == 0:
                box_values = (roi.x, roi.y, roi.width, roi.height)
                tracker.init(frame, box_values)
                found = True
                try:
                    # shortcut: CFR preview, use JSON PTS for timing until VFR export is needed.
                    writer = cv2.VideoWriter(str(overlay_path), cv2.CAP_FFMPEG,
                        cv2.VideoWriter_fourcc(*"VP90"), fps,
                        (metadata.width, metadata.height))
                    if not writer.isOpened():
                        raise OverlayError("Overlay encoder unavailable")
                except (cv2.error, OSError) as error:
                    raise OverlayError("Overlay encoder unavailable") from error
            else:
                found, box_values = tracker.update(frame)
            box = normalize_box(box_values, metadata.width, metadata.height) if found else None
            failure_reason = "CSRT update failed"
            if found and box is None:
                found = False
                failure_reason = "CSRT returned an invalid bounding box"
            flags = [] if found else ["tracking_failed"]
            frames.append(TrackFrame(index, timestamp, box,
                box.x + box.width / 2 if box else None,
                box.y + box.height / 2 if box else None, flags))
            if not found:
                failures.append(TrackingFailure(index, failure_reason,
                    "Record a clearer clip or select the target again on the first frame"))
            draw_overlay_frame(writer, frame, timestamp, box)
        if len(frames) != metadata.frame_count or len(frames) < 2:
            raise ValueError("Video is empty or could not be fully decoded")
        try:
            writer.release()
            writer = None
            overlay_metadata = inspect_video(overlay_path)
            if (overlay_metadata.frame_count != len(frames)
                or (overlay_metadata.width, overlay_metadata.height)
                != (metadata.width, metadata.height)):
                raise ValueError("Overlay does not match source frames")
        except (ValueError, cv2.error, OSError) as error:
            raise OverlayError("Overlay could not be fully encoded") from error
        with source_path.open("rb") as source:
            source_hash = file_digest(source, "sha256").hexdigest()
        result = TrackResult(
            schema_version="1.0.0", experiment_id=None, video_id=observation_id,
            provider_name="opencv", model_name="csrt", model_version=cv2.__version__,
            run_config_id="opencv-csrt-default-v1",
            status="partial" if failures else "succeeded", frames=frames,
            failures=failures, provenance=Provenance(
                source_video_sha256=source_hash, preprocessing="none",
                timebase_seconds_per_tick=1 / fps, requested_frames=metadata.frame_count,
                opencv_version=cv2.__version__),
        )
        completed = True
        return result
    except cv2.error as error:
        raise ValueError("Video or tracker could not be processed") from error
    finally:
        capture.release()
        try:
            if writer is not None:
                writer.release()
        finally:
            if not completed:
                overlay_path.unlink(missing_ok=True)
