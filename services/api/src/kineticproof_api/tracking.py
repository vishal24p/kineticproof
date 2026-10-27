"""Local video inspection using source presentation timestamps."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import cv2


class UnsupportedContainer(ValueError):
    pass


def validate_container(path: Path) -> None:
    """Require complete MP4/MOV top-level boxes, including movie and media data."""
    length = path.stat().st_size
    position = 0
    kinds = set()
    supported_brands = {b"isom", b"iso2", b"mp41", b"mp42", b"qt  "}
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


def inspect_video(path: Path) -> VideoMetadata:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        validate_container(path)
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
        if frame_count < 2:
            raise ValueError("At least two frames are required to validate video timestamps")
        return VideoMetadata(
            previous_timestamp - first_timestamp, width, height, frame_count, fps
        )
    except cv2.error as error:
        raise ValueError("Video cannot be decoded") from error
    finally:
        capture.release()
