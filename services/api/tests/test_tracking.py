"""Synthetic media tests: plumbing evidence, not measured experimental footage."""

from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from kineticproof_api import main


def synthetic_video(path: Path, frame_count=6, fps=10.0) -> bytes:
    writer = cv2.VideoWriter(str(path), cv2.CAP_FFMPEG,
                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    assert writer.isOpened(), "Synthetic test encoder unavailable"
    try:
        for index in range(frame_count):
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            cv2.rectangle(frame, (index % 40, 12), (index % 40 + 12, 24),
                          (255, 255, 255), -1)
            writer.write(frame)
    finally:
        writer.release()
    return path.read_bytes()


@pytest.mark.parametrize("suffix", [".mp4", ".mov"])
def test_upload_accepts_synthetic_video(tmp_path, suffix):
    data = synthetic_video(tmp_path / f"synthetic{suffix}")
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={
            "file": (f"private-person-name{suffix}", data, "video/mp4")})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"observation_id", "duration_seconds", "width",
                             "height", "frame_count"}
        UUID(body["observation_id"])
        assert body["duration_seconds"] == pytest.approx(0.5)
        assert (body["width"], body["height"], body["frame_count"]) == (64, 48, 6)
        assert "private-person-name" not in response.text


@pytest.mark.parametrize("filename,data,status", [
    ("clip.avi", b"unsupported", 415),
    ("clip.mp4", b"corrupt", 422),
    ("clip.mov", b"", 422),
])
def test_rejection_leaves_no_files(filename, data, status):
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": (filename, data)})
        assert response.status_code == status
        assert list(main.app.state.media_dir.iterdir()) == []
        assert main.app.state.observations == {}


def test_upload_byte_counter_rejects_and_cleans_partial_file(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024 * 1024)
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={
            "file": ("clip.mp4", b"x" * (1024 * 1024 + 1))})
        assert response.status_code == 413
        assert list(main.app.state.media_dir.iterdir()) == []


def test_long_synthetic_video_rejected_and_removed(tmp_path):
    data = synthetic_video(tmp_path / "synthetic-long.mp4", frame_count=312)
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", data)})
        assert response.status_code == 413
        assert list(main.app.state.media_dir.iterdir()) == []


def test_shutdown_removes_only_app_owned_media(tmp_path):
    source = tmp_path / "synthetic.mp4"
    data = synthetic_video(source)
    with TestClient(main.app) as client:
        assert client.post("/api/observations", files={"file": ("clip.mp4", data)}).status_code == 200
        media_dir = main.app.state.media_dir
        assert list(media_dir.iterdir())
    assert not media_dir.exists()
    assert source.read_bytes() == data


def test_truncated_synthetic_upload_rejected_and_removed(tmp_path):
    data = synthetic_video(tmp_path / "synthetic.mp4")
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={
            "file": ("clip.mp4", data[:len(data) // 2])})
        assert response.status_code == 422
        assert list(main.app.state.media_dir.iterdir()) == []


def test_upload_read_failure_removes_partial_file(monkeypatch):
    from starlette.datastructures import UploadFile

    reads = 0

    async def interrupted_read(self, size=-1):
        nonlocal reads
        reads += 1
        if reads == 1:
            return b"partial video"
        raise OSError("Synthetic interrupted upload")

    monkeypatch.setattr(UploadFile, "read", interrupted_read)
    with TestClient(main.app) as client:
        with pytest.raises(OSError, match="interrupted"):
            client.post("/api/observations", files={"file": ("clip.mp4", b"video")})
        assert list(main.app.state.media_dir.iterdir()) == []
        assert main.app.state.observations == {}


def test_inspection_accepts_zero_pts(tmp_path):
    from kineticproof_api.tracking import inspect_video

    source = tmp_path / "synthetic.mp4"
    synthetic_video(source)
    metadata = inspect_video(source)
    assert metadata.duration_seconds == pytest.approx(0.5)
    assert metadata.fps == 10.0
    assert metadata.frame_count == 6


@pytest.mark.parametrize("timestamps", [[0, 0, 0], [0, float("nan"), 2],
                                         [0, 2, 1]])
def test_inspection_rejects_missing_or_nonmonotonic_pts(monkeypatch, timestamps):
    from kineticproof_api import tracking

    class Capture:
        index = -1
        released = False

        def isOpened(self):
            return True

        def get(self, prop):
            return {cv2.CAP_PROP_FPS: 10.0, cv2.CAP_PROP_FRAME_COUNT: 3,
                    cv2.CAP_PROP_PTS: timestamps[self.index]}.get(prop, 0)

        def read(self):
            self.index += 1
            return (True, np.zeros((48, 64, 3), dtype=np.uint8)) if self.index < 3 else (False, None)

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(tracking.cv2, "VideoCapture", lambda *_: capture)
    with pytest.raises(ValueError, match="timestamp"):
        tracking.inspect_video(Path("synthetic.mp4"))
    assert capture.released
