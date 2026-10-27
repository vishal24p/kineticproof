"""Synthetic media tests: plumbing evidence, not measured experimental footage."""

import asyncio
from tempfile import TemporaryFile
from uuid import UUID

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from kineticproof_api import main


@pytest.fixture
def request_spools(monkeypatch, tmp_path):
    opened = []

    def create():
        spool = TemporaryFile(dir=tmp_path)
        opened.append(spool)
        return spool

    monkeypatch.setattr(main, "TemporaryFile", create)
    yield opened
    assert all(spool.closed for spool in opened)


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


def test_renamed_avi_container_is_rejected(tmp_path):
    data = synthetic_video(tmp_path / "synthetic.avi")
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", data)})
        assert response.status_code == 415
        assert list(main.app.state.media_dir.iterdir()) == []
        assert main.app.state.observations == {}


@pytest.mark.parametrize("brand", [b"3gp4", b"3gp5", b"3gp6", b"avif"])
def test_renamed_unsupported_major_brand_is_rejected(tmp_path, brand):
    data = bytearray(synthetic_video(tmp_path / "synthetic.mp4"))
    assert data[4:8] == b"ftyp"
    data[8:12] = brand
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", bytes(data))})
        assert response.status_code == 415
        assert list(main.app.state.media_dir.iterdir()) == []
        assert main.app.state.observations == {}


def test_single_frame_zero_pts_is_rejected(tmp_path):
    data = synthetic_video(tmp_path / "synthetic-single.mp4", frame_count=1)
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", data)})
        assert response.status_code == 422
        assert "timestamp" in response.json()["detail"]
        assert list(main.app.state.media_dir.iterdir()) == []


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_body_limit_rejects_chunked_input_before_parser(monkeypatch, headers, request_spools):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)
    monkeypatch.setattr(main, "MULTIPART_ALLOWANCE_BYTES", 4, raising=False)
    parser_called = False
    sent = []
    chunks = iter([b"1234", b"5678", b"90123"])

    async def parser(scope, receive, send):
        nonlocal parser_called
        parser_called = True

    async def receive():
        return {"type": "http.request", "body": next(chunks), "more_body": True}

    async def send(message):
        sent.append(message)

    middleware = main.UploadBodyLimit(parser)
    asyncio.run(middleware({"type": "http", "path": "/api/observations",
                           "method": "POST", "headers": headers}, receive, send))
    assert not parser_called
    assert sent[0]["status"] == 413
    assert len(request_spools) == 1


def test_body_limit_replays_within_limit_input_and_allows_overhead(monkeypatch, request_spools):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)
    monkeypatch.setattr(main, "MULTIPART_ALLOWANCE_BYTES", 4, raising=False)
    received = bytearray()
    chunks = iter([b"12345678", b"abcd"])

    async def parser(scope, receive, send):
        while True:
            message = await receive()
            received.extend(message["body"])
            if not message.get("more_body", False):
                break

    async def receive():
        chunk = next(chunks)
        return {"type": "http.request", "body": chunk, "more_body": chunk != b"abcd"}

    async def send(message):
        raise AssertionError("Valid body should reach parser")

    asyncio.run(main.UploadBodyLimit(parser)(
        {"type": "http", "path": "/api/observations", "method": "POST",
         "headers": []}, receive, send))
    assert received == b"12345678abcd"
    assert len(request_spools) == 1


def test_body_limit_rejects_large_content_length_before_reading(monkeypatch, request_spools):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)
    monkeypatch.setattr(main, "MULTIPART_ALLOWANCE_BYTES", 4)
    sent = []

    async def unexpected(*args):
        raise AssertionError("Oversized Content-Length must reject before body/parser")

    async def send(message):
        sent.append(message)

    asyncio.run(main.UploadBodyLimit(unexpected)(
        {"type": "http", "path": "/api/observations", "method": "POST",
         "headers": [(b"content-length", b"13")]}, unexpected, send))
    assert sent[0]["status"] == 413
    assert request_spools == []


def test_disconnected_request_cleans_partial_spool(request_spools):
    messages = iter([
        {"type": "http.request", "body": b"partial", "more_body": True},
        {"type": "http.disconnect"},
    ])

    async def unexpected(*args):
        raise AssertionError("Disconnected request must not reach parser")

    async def receive():
        return next(messages)

    asyncio.run(main.UploadBodyLimit(unexpected)(
        {"type": "http", "path": "/api/observations", "method": "POST",
         "headers": []}, receive, unexpected))
    assert len(request_spools) == 1


def test_api_body_limit_is_installed(monkeypatch, request_spools):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)
    monkeypatch.setattr(main, "MULTIPART_ALLOWANCE_BYTES", 4)
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", b"x" * 13)})
        assert response.status_code == 413
        assert list(main.app.state.media_dir.iterdir()) == []


@pytest.mark.parametrize("suffix", [".mp4", ".mov"])
def test_upload_accepts_synthetic_video(tmp_path, suffix):
    data = synthetic_video(tmp_path / f"synthetic{suffix}")
    if suffix == ".mov":
        assert data[4:12] == b"ftypqt  ", "Fixture must use a real MOV container"
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
def test_inspection_rejects_missing_or_nonmonotonic_pts(monkeypatch, tmp_path, timestamps):
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
    source = tmp_path / "synthetic.mp4"
    synthetic_video(source)
    monkeypatch.setattr(tracking.cv2, "VideoCapture", lambda *_: capture)
    with pytest.raises(ValueError, match="timestamp"):
        tracking.inspect_video(source)
    assert capture.released
