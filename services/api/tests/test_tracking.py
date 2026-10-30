"""Synthetic media tests: plumbing evidence, not measured experimental footage."""

import asyncio
from pathlib import Path
from tempfile import TemporaryFile
from uuid import UUID

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from kineticproof_api import main
from kineticproof_api import tracking


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


def test_unbranded_container_is_rejected(tmp_path):
    data = bytearray(synthetic_video(tmp_path / "synthetic.mp4"))
    assert data[4:8] == b"ftyp"
    data[4:8] = b"free"
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mov", bytes(data))})
        assert response.status_code == 415
        assert list(main.app.state.media_dir.iterdir()) == []


@pytest.mark.parametrize("brand", [
    b"isom", b"iso2", b"mp41", b"mp42", b"qt  ", b"avc1", b"av01", b"M4V ",
])
def test_supported_major_brands_are_accepted(tmp_path, brand):
    data = bytearray(synthetic_video(tmp_path / "synthetic.mp4"))
    data[8:12] = brand
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", bytes(data))})
        assert response.status_code == 200


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


@pytest.fixture
def uploaded_synthetic(tmp_path):
    data = synthetic_video(tmp_path / "synthetic-tracking.mp4")
    with TestClient(main.app) as client:
        response = client.post("/api/observations", files={"file": ("clip.mp4", data)})
        assert response.status_code == 200
        yield client, response.json()["observation_id"], data


@pytest.mark.parametrize("route,method", [("tracking", "post"), ("tracks", "get"),
                                         ("overlay", "get")])
def test_unknown_tracking_observation(route, method):
    with TestClient(main.app) as client:
        response = getattr(client, method)(f"/api/observations/unknown/{route}",
            **({"json": {"x": 0, "y": 12, "width": 13, "height": 13}} if method == "post" else {}))
        assert response.status_code == 404


@pytest.mark.parametrize("route", ["tracks", "overlay"])
def test_missing_tracking_result_returns_conflict(uploaded_synthetic, route):
    client, observation_id, _ = uploaded_synthetic
    assert client.get(f"/api/observations/{observation_id}/{route}").status_code == 409


def test_csrt_trace_and_overlay(uploaded_synthetic, tmp_path):
    from hashlib import sha256

    client, observation_id, source = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    response = client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13})
    assert response.status_code == 200
    assert response.json() == {"status": "succeeded", "frame_count": 6}
    trace = client.get(f"{base}/tracks").json()
    assert set(trace) == {"schema_version", "experiment_id", "video_id", "provider_name",
                          "model_name", "model_version", "run_config_id", "status",
                          "frames", "failures", "provenance"}
    assert trace["schema_version"] == "1.0.0"
    assert trace["experiment_id"] is None
    assert trace["video_id"] == observation_id
    assert trace["provider_name"] == "opencv"
    assert trace["model_name"] == "csrt"
    assert trace["model_version"] == cv2.__version__
    assert trace["run_config_id"] == "opencv-csrt-default-v1"
    assert trace["status"] == "succeeded"
    assert trace["failures"] == []
    assert trace["provenance"] == {"source_video_sha256": sha256(source).hexdigest(),
        "preprocessing": "none", "timebase_seconds_per_tick": 0.1,
        "requested_frames": 6, "opencv_version": cv2.__version__,
        "provider_request_id": None}
    assert [frame["frame_index"] for frame in trace["frames"]] == list(range(6))
    assert [frame["timestamp_seconds"] for frame in trace["frames"]] == pytest.approx([0, .1, .2, .3, .4, .5])
    assert all(frame["quality_flags"] == [] for frame in trace["frames"])
    assert all(frame["center_x_px"] is not None for frame in trace["frames"])
    assert trace["frames"][0]["bbox_px"] == {"x": 0, "y": 12, "width": 13, "height": 13}
    assert trace["frames"][0]["center_x_px"] == 6.5
    assert trace["frames"][0]["center_y_px"] == 18.5
    assert all(type(value) is int for frame in trace["frames"]
               for value in frame["bbox_px"].values())
    assert all("confidence" not in frame for frame in trace["frames"])
    overlay = client.get(f"{base}/overlay")
    assert overlay.status_code == 200
    assert overlay.headers["content-type"] == "video/mp4"
    overlay_path = tmp_path / "synthetic-overlay.mp4"
    overlay_path.write_bytes(overlay.content)
    metadata = tracking.inspect_video(overlay_path)
    assert metadata.frame_count == 6
    assert (metadata.width, metadata.height) == (64, 48)


def _synthetic_sam_trace(observation_id):
    frames = [tracking.TrackFrame(
        index, index / 10, tracking.BoundingBox(0, 12, 13, 13), 6.5, 18.5, [],
    ) for index in range(6)]
    return tracking.TrackResult(
        "1.0.0", None, observation_id, "meta_sam", "sam-3.1", "3.1",
        "meta-sam-3.1-forward-box-v1", "succeeded", frames, [],
        tracking.Provenance("synthetic-test-hash", "none", 0.1, 6,
                            provider_request_id="synthetic-test-request"),
    )


def test_explicit_opencv_provider_uses_existing_trace(uploaded_synthetic):
    client, observation_id, _ = uploaded_synthetic
    response = client.post(
        f"/api/observations/{observation_id}/tracking?provider=opencv",
        json={"x": 0, "y": 12, "width": 13, "height": 13},
    )
    assert response.status_code == 200
    assert client.get(f"/api/observations/{observation_id}/tracks").json()["provider_name"] == "opencv"


def test_invalid_tracking_provider_is_rejected(uploaded_synthetic):
    client, observation_id, _ = uploaded_synthetic
    response = client.post(
        f"/api/observations/{observation_id}/tracking?provider=unknown",
        json={"x": 0, "y": 12, "width": 13, "height": 13},
    )
    assert response.status_code == 422
    assert client.get(f"/api/observations/{observation_id}/tracks").status_code == 409


def test_sam_provider_without_key_never_constructs_client(uploaded_synthetic, monkeypatch):
    client, observation_id, _ = uploaded_synthetic
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(main, "AsyncOpenAI", lambda **kwargs: pytest.fail("client must not be constructed"))

    response = client.post(
        f"/api/observations/{observation_id}/tracking?provider=meta_sam",
        json={"x": 0, "y": 12, "width": 13, "height": 13},
    )
    assert response.status_code == 503
    assert client.get(f"/api/observations/{observation_id}/tracks").status_code == 409


def test_sam_provider_is_explicit_and_closes_client(uploaded_synthetic, monkeypatch):
    client, observation_id, _ = uploaded_synthetic
    monkeypatch.setenv("MODEL_API_KEY", "test-only-key")
    client_options = {}

    class FakeMetaClient:
        closed = False

        async def close(self):
            self.closed = True

    fake_client = FakeMetaClient()

    def build_client(**kwargs):
        client_options.update(kwargs)
        return fake_client

    async def fake_sam_tracker(source_path, metadata, roi, requested_id, overlay_path, used_client):
        assert source_path.exists()
        assert requested_id == observation_id
        assert (roi.x, roi.y, roi.width, roi.height) == (0, 12, 13, 13)
        assert used_client is fake_client
        overlay_path.write_bytes(b"synthetic test overlay")
        return _synthetic_sam_trace(requested_id)

    monkeypatch.setattr(main, "AsyncOpenAI", build_client)
    monkeypatch.setattr(main, "track_sam_video", fake_sam_tracker)
    response = client.post(
        f"/api/observations/{observation_id}/tracking?provider=meta_sam",
        json={"x": 0, "y": 12, "width": 13, "height": 13},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "succeeded", "frame_count": 6}
    assert client.get(f"/api/observations/{observation_id}/tracks").json()["provider_name"] == "meta_sam"
    assert client_options == {
        "base_url": "https://api.meta.ai/v1",
        "api_key": "test-only-key",
        "max_retries": 0,
    }
    assert fake_client.closed


def test_failed_sam_rerun_does_not_fallback_or_replace_success(
    uploaded_synthetic, monkeypatch,
):
    from kineticproof_api.sam_tracker import SAMTrackingError

    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    roi = {"x": 0, "y": 12, "width": 13, "height": 13}
    assert client.post(f"{base}/tracking", json=roi).status_code == 200
    trace = client.get(f"{base}/tracks").json()
    overlay = client.get(f"{base}/overlay").content
    monkeypatch.setenv("MODEL_API_KEY", "test-only-key")

    class FakeMetaClient:
        async def close(self):
            pass

    monkeypatch.setattr(main, "AsyncOpenAI", lambda **kwargs: FakeMetaClient())
    async def failed_sam_tracker(*args):
        raise SAMTrackingError("synthetic provider failure")

    monkeypatch.setattr(main, "track_sam_video", failed_sam_tracker)
    monkeypatch.setattr(main, "track_video", lambda *args: pytest.fail("must not fall back to OpenCV"))
    response = client.post(f"{base}/tracking?provider=meta_sam", json=roi)

    assert response.status_code == 502
    assert client.get(f"{base}/tracks").json() == trace
    assert client.get(f"{base}/overlay").content == overlay


def test_failed_csrt_update_has_null_geometry(uploaded_synthetic, monkeypatch):
    class FailedTracker:
        def init(self, frame, box):
            pass

        def update(self, frame):
            return False, (0, 0, 0, 0)

    monkeypatch.setattr(tracking.cv2, "TrackerCSRT_create", FailedTracker)
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    response = client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13})
    assert response.status_code == 200
    assert response.json() == {"status": "partial", "frame_count": 6}
    trace = client.get(f"{base}/tracks").json()
    assert trace["status"] == "partial"
    assert len(trace["failures"]) == 5
    for frame, failure in zip(trace["frames"][1:], trace["failures"]):
        assert frame["bbox_px"] is None
        assert frame["center_x_px"] is None and frame["center_y_px"] is None
        assert frame["quality_flags"] == ["tracking_failed"]
        assert failure["frame_index"] == frame["frame_index"]
        assert failure["reason"] and failure["recovery_suggestion"]


def test_trace_and_overlay_use_irregular_source_pts(uploaded_synthetic, monkeypatch):
    client, observation_id, _ = uploaded_synthetic
    real_capture = cv2.VideoCapture
    real_put_text = cv2.putText
    source_ticks = [4, 6, 9, 13, 18, 24]
    labels = []

    class IrregularCapture:
        def __init__(self, *args):
            self.capture = real_capture(*args)
            self.index = -1

        def isOpened(self):
            return self.capture.isOpened()

        def read(self):
            result = self.capture.read()
            self.index += 1
            return result

        def get(self, prop):
            if prop == cv2.CAP_PROP_PTS:
                return source_ticks[self.index]
            return self.capture.get(prop)

        def release(self):
            self.capture.release()

    def record_label(frame, label, *args):
        labels.append(label)
        return real_put_text(frame, label, *args)

    monkeypatch.setattr(tracking.cv2, "VideoCapture", IrregularCapture)
    monkeypatch.setattr(tracking.cv2, "putText", record_label)
    base = f"/api/observations/{observation_id}"
    response = client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13})
    assert response.status_code == 200
    frames = client.get(f"{base}/tracks").json()["frames"]
    assert [frame["timestamp_seconds"] for frame in frames] == pytest.approx([.4, .6, .9, 1.3, 1.8, 2.4])
    assert len(labels) == 6
    assert all(f"{timestamp:.3f}" in label for timestamp, label in
               zip([.4, .6, .9, 1.3, 1.8, 2.4], labels))


@pytest.mark.parametrize("change", [{"x": -1}, {"y": -1}, {"width": 0},
    {"height": -1}, {"x": 60}, {"y": 40}, {"width": 65}, {"height": 49},
    {"x": 0.5}, {"x": 0.0}, {"width": "13"}, {"x": True}, {"height": None}])
def test_invalid_tracking_roi(uploaded_synthetic, change):
    client, observation_id, _ = uploaded_synthetic
    roi = {"x": 0, "y": 12, "width": 13, "height": 13} | change
    response = client.post(f"/api/observations/{observation_id}/tracking", json=roi)
    assert response.status_code == 422
    assert client.get(f"/api/observations/{observation_id}/tracks").status_code == 409
    assert len(list(main.app.state.media_dir.iterdir())) == 1


@pytest.mark.parametrize("failure", ["pts", "decode", "writer"])
def test_failed_rerun_preserves_previous_trace_and_overlay(uploaded_synthetic, monkeypatch, failure):
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    roi = {"x": 0, "y": 12, "width": 13, "height": 13}
    assert client.post(f"{base}/tracking", json=roi).status_code == 200
    trace = client.get(f"{base}/tracks").json()
    overlay = client.get(f"{base}/overlay").content
    files_before = set(main.app.state.media_dir.iterdir())
    if failure == "writer":
        class UnavailableWriter:
            def __init__(self, path, *args):
                Path(path).write_bytes(b"synthetic partial overlay")

            def isOpened(self):
                return False

            def release(self):
                pass

        monkeypatch.setattr(tracking.cv2, "VideoWriter", UnavailableWriter)
    else:
        real_decoded_frames = tracking.decoded_frames

        def broken_frames(capture, fps):
            for index, timestamp, frame in real_decoded_frames(capture, fps):
                if index == 2:
                    if failure == "pts":
                        raise ValueError("Video timestamps unavailable or nonmonotonic")
                    return
                yield index, timestamp, frame

        monkeypatch.setattr(tracking, "decoded_frames", broken_frames)
    response = client.post(f"{base}/tracking", json=roi)
    assert response.status_code == (500 if failure == "writer" else 422)
    assert client.get(f"{base}/tracks").json() == trace
    assert client.get(f"{base}/overlay").content == overlay
    assert set(main.app.state.media_dir.iterdir()) == files_before


def test_first_writer_failure_does_not_publish_result(uploaded_synthetic, monkeypatch):
    class BrokenWriter:
        def isOpened(self):
            return True

        def write(self, frame):
            raise cv2.error("Synthetic encoder failure")

        def release(self):
            pass

    monkeypatch.setattr(tracking.cv2, "VideoWriter", lambda *args: BrokenWriter())
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    response = client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13})
    assert response.status_code == 500
    assert client.get(f"{base}/tracks").status_code == 409
    assert client.get(f"{base}/overlay").status_code == 409
    assert len(list(main.app.state.media_dir.iterdir())) == 1


def test_successful_rerun_publishes_matching_pair(uploaded_synthetic):
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    assert client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13}).status_code == 200
    old_run = main.app.state.observations[observation_id].tracking_run
    old_overlay = client.get(f"{base}/overlay").content
    assert client.post(f"{base}/tracking", json={"x": 1, "y": 12, "width": 12, "height": 13}).status_code == 200
    new_run = main.app.state.observations[observation_id].tracking_run
    assert new_run.overlay_path != old_run.overlay_path
    assert client.get(f"{base}/tracks").json()["frames"][0]["bbox_px"]["x"] == 1
    assert client.get(f"{base}/overlay").content == new_run.overlay_path.read_bytes()
    assert client.get(f"{base}/overlay").content != old_overlay


def test_silent_encoder_failure_does_not_publish(uploaded_synthetic, monkeypatch):
    class SilentWriter:
        def isOpened(self):
            return True

        def write(self, frame):
            pass

        def release(self):
            pass

    monkeypatch.setattr(tracking.cv2, "VideoWriter", lambda *args: SilentWriter())
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    response = client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13})
    assert response.status_code == 500
    assert client.get(f"{base}/tracks").status_code == 409
    assert client.get(f"{base}/overlay").status_code == 409
    assert len(list(main.app.state.media_dir.iterdir())) == 1


def test_trace_boxes_have_integer_pixels(uploaded_synthetic, monkeypatch):
    class FractionalTracker:
        def init(self, frame, box):
            pass

        def update(self, frame):
            return True, (1.5, 12.5, 13.5, 13.9)

    monkeypatch.setattr(tracking.cv2, "TrackerCSRT_create", FractionalTracker)
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    assert client.post(f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13}).status_code == 200
    frames = client.get(f"{base}/tracks").json()["frames"]
    assert all(type(value) is int for frame in frames for value in frame["bbox_px"].values())
    assert frames[1]["bbox_px"] == {"x": 2, "y": 12, "width": 14, "height": 14}
    assert frames[1]["center_x_px"] == 9
    assert frames[1]["center_y_px"] == 19


@pytest.mark.parametrize("box_values", [
    pytest.param((float("nan"), 12, 13, 13), id="non-finite"),
    pytest.param((63, 12, 2, 13), id="outside-frame"),
    pytest.param((1, 12, 0.4, 13), id="rounded-zero-size"),
])
def test_invalid_csrt_boxes_are_partial_with_null_geometry(
    uploaded_synthetic, monkeypatch, box_values
):
    class InvalidBoxTracker:
        def init(self, frame, box):
            pass

        def update(self, frame):
            return True, box_values

    monkeypatch.setattr(tracking.cv2, "TrackerCSRT_create", InvalidBoxTracker)
    client, observation_id, _ = uploaded_synthetic
    base = f"/api/observations/{observation_id}"
    response = client.post(
        f"{base}/tracking", json={"x": 0, "y": 12, "width": 13, "height": 13}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    trace = client.get(f"{base}/tracks").json()
    assert len(trace["failures"]) == 5
    for frame, failure in zip(trace["frames"][1:], trace["failures"]):
        assert frame["bbox_px"] is None
        assert frame["center_x_px"] is None
        assert frame["center_y_px"] is None
        assert frame["quality_flags"] == ["tracking_failed"]
        assert failure["reason"] == "CSRT returned an invalid bounding box"
        assert failure["recovery_suggestion"]
