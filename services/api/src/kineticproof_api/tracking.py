"""Local video inspection using source presentation timestamps."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import cv2


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    frame_count: int
    fps: float


def inspect_video(path: Path) -> VideoMetadata:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not isfinite(fps) or fps <= 0:
            raise ValueError("Video timestamp timebase unavailable")
        expected_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        first_timestamp = previous_timestamp = None
        frame_count = 0
        width = height = 0
        while True:
            decoded, frame = capture.read()
            if not decoded:
                break
            timestamp = capture.get(cv2.CAP_PROP_PTS) / fps
            if not isfinite(timestamp) or (
                previous_timestamp is not None and timestamp <= previous_timestamp
            ):
                raise ValueError("Video timestamps unavailable or nonmonotonic")
            if first_timestamp is None:
                first_timestamp = timestamp
                height, width = frame.shape[:2]
            if frame.shape[:2] != (height, width):
                raise ValueError("Video frame dimensions change during decoding")
            previous_timestamp = timestamp
            frame_count += 1
        if not frame_count or (expected_count > 0 and frame_count != expected_count):
            raise ValueError("Video is empty or could not be fully decoded")
        return VideoMetadata(
            previous_timestamp - first_timestamp, width, height, frame_count, fps
        )
    except cv2.error as error:
        raise ValueError("Video cannot be decoded") from error
    finally:
        capture.release()
