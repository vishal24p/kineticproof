"""Offline SAM adapter tests; fake responses are plumbing, not model evidence."""

import asyncio
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from meta_sam_parser import FrameReference, SegmentationBoxRecord

from kineticproof_api import sam_tracker
from kineticproof_api.tracking import InitialROI, inspect_video


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


def box_record(index, x=4, y=5, width=10, height=8):
    return SegmentationBoxRecord(
        order=index,
        object_id="1",
        left=x,
        top=y,
        right=x + width,
        bottom=y + height,
        frame=FrameReference(index),
    )


class FakeFiles:
    def __init__(self, delete_error=None):
        self.upload = None
        self.deletions = []
        self.delete_error = delete_error

    async def create(self, *, file, purpose, expires_after):
        self.upload = (file.read(), purpose, expires_after)
        return SimpleNamespace(id="file-test")

    async def delete(self, *, file_id):
        self.deletions.append(file_id)
        if self.delete_error:
            raise self.delete_error


class FakeResponses:
    def __init__(self, error=None, output_text=None):
        self.request = None
        self.error = error
        self.output_text = output_text

    async def create(self, **request):
        self.request = request
        if self.error:
            raise self.error

        async def events():
            yield SimpleNamespace(
                type="response.created", response=SimpleNamespace(id="resp-test")
            )
            if self.output_text is not None:
                yield {
                    "type": "response.output_text.done",
                    "item_id": "msg-test",
                    "output_index": 0,
                    "content_index": 0,
                    "text": self.output_text,
                }
            yield SimpleNamespace(type="response.completed")

        return events()


class FakeClient:
    def __init__(self, *, response_error=None, delete_error=None, output_text=None):
        self.files = FakeFiles(delete_error)
        self.responses = FakeResponses(response_error, output_text)


def install_fake_parser(monkeypatch, records, outcome="completed", error=None):
    def parse(events, format):
        async def final_result():
            async for _ in events:
                pass
            if error:
                raise error
            return SimpleNamespace(
                outcome=SimpleNamespace(status=outcome),
                diagnostics=(),
                records=records,
            )

        return SimpleNamespace(final_result=final_result)

    monkeypatch.setattr(sam_tracker, "parse_responses_stream", parse)


def run_tracking(tmp_path, monkeypatch, client, records, *, parser_error=None,
                 roi=(4, 5, 10, 8)):
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, records, error=parser_error)
    output_path = tmp_path / "overlay.mp4"
    result = asyncio.run(sam_tracker.track_sam_video(
        source_path,
        metadata,
        InitialROI(x=roi[0], y=roi[1], width=roi[2], height=roi[3]),
        "observation-test",
        output_path,
        client,
    ))
    return result, output_path, source_path, metadata


def test_sam_request_uses_box_prompt_forward_mode_and_expires_upload(
    tmp_path, monkeypatch,
):
    client = FakeClient()
    records = [box_record(index) for index in reversed(range(6))]
    result, overlay, source, metadata = run_tracking(tmp_path, monkeypatch, client, records)

    assert client.files.upload == (
        source.read_bytes(), "user_data",
        {"anchor": "created_at", "seconds": 3600},
    )
    request = client.responses.request
    assert request["model"] == "sam-3.1"
    assert request["stream"] is True
    assert request["metadata"] == {"propagation_direction": "forward"}
    assert request["input"] == [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text":
            "<0f>1<|box;x1=4;y1=5;x2=13;y2=12;w=64;h=48|>"},
        {"type": "input_video", "file_id": "file-test"},
    ]}]
    assert client.files.deletions == ["file-test"]
    assert result.provider_name == "meta_sam"
    assert result.model_name == "sam-3.1"
    assert result.provenance.provider_request_id == "resp-test"
    assert result.provenance.opencv_version is None
    assert [frame.frame_index for frame in result.frames] == list(range(6))
    assert [frame.timestamp_seconds for frame in result.frames] == pytest.approx(
        [0, .1, .2, .3, .4, .5]
    )
    assert all(frame.bbox_px.x == 4 for frame in result.frames)
    assert result.frames[0].center_x_px == 9
    assert result.frames[0].center_y_px == 9
    assert result.status == "succeeded"
    assert overlay.exists()
    overlay_metadata = inspect_video(overlay)
    assert overlay_metadata.frame_count == metadata.frame_count
    assert (overlay_metadata.width, overlay_metadata.height) == (64, 48)


def test_official_parser_maps_box_record_and_deletes_upload(tmp_path):
    client = FakeClient(output_text=(
        "<0f>1<|box;x1=4;y1=5;x2=13;y2=12;w=64;h=48|>"
        "<|mask;x=0;y=0;data=1,1,!!!!!&!!!!!|>"
    ))
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)

    result = asyncio.run(sam_tracker.track_sam_video(
        source_path,
        metadata,
        InitialROI(x=4, y=5, width=10, height=8),
        "observation-test",
        tmp_path / "overlay.mp4",
        client,
    ))

    assert result.frames[0].bbox_px.x == 4
    assert result.frames[0].bbox_px.y == 5
    assert result.frames[0].bbox_px.width == 10
    assert result.frames[0].bbox_px.height == 8
    assert client.files.deletions == ["file-test"]


def test_missing_sam_boxes_remain_explicit_gaps(tmp_path, monkeypatch):
    client = FakeClient()
    result, _, _, _ = run_tracking(
        tmp_path, monkeypatch, client, [box_record(index) for index in (5, 3, 0, 2)]
    )

    assert result.status == "partial"
    assert [failure.frame_index for failure in result.failures] == [1, 4]
    assert result.frames[1].bbox_px is None
    assert result.frames[1].center_x_px is None
    assert result.frames[1].quality_flags == ["tracking_failed"]


@pytest.mark.parametrize("records", [
    [box_record(0), box_record(0)],
    [box_record(6)],
    [box_record(0, x=63)],
])
def test_invalid_sam_box_records_fail_and_delete_remote_file(tmp_path, monkeypatch, records):
    client = FakeClient()
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, records)
    output_path = tmp_path / "overlay.mp4"

    with pytest.raises(sam_tracker.SAMTrackingError):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", output_path, client,
        ))

    assert client.files.deletions == ["file-test"]
    assert not output_path.exists()


def test_provider_failure_still_deletes_uploaded_file(tmp_path):
    client = FakeClient(response_error=RuntimeError("offline fixture error"))
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)

    with pytest.raises(sam_tracker.SAMTrackingError, match="request failed"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", tmp_path / "overlay.mp4", client,
        ))

    assert client.files.deletions == ["file-test"]


@pytest.mark.parametrize("records", [None, {"unexpected": "mapping"}])
def test_malformed_parser_records_fail_with_adapter_error(tmp_path, monkeypatch, records):
    client = FakeClient()
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, records)

    with pytest.raises(sam_tracker.SAMTrackingError, match="request failed"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", tmp_path / "overlay.mp4", client,
        ))

    assert client.files.deletions == ["file-test"]


def test_parser_failure_still_deletes_uploaded_file(tmp_path, monkeypatch):
    client = FakeClient()
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, [], error=ValueError("bad fixture stream"))

    with pytest.raises(sam_tracker.SAMTrackingError, match="request failed"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", tmp_path / "overlay.mp4", client,
        ))

    assert client.files.deletions == ["file-test"]


def test_cleanup_failure_is_reported_with_expiry_backstop(tmp_path, monkeypatch):
    client = FakeClient(delete_error=OSError("fixture delete failure"))
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, [box_record(index) for index in range(6)])

    with pytest.raises(sam_tracker.SAMTrackingError, match="one-hour expiry"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", tmp_path / "overlay.mp4", client,
        ))

    assert client.files.deletions == ["file-test"]


def test_overlay_failure_removes_incomplete_output(tmp_path, monkeypatch):
    client = FakeClient()
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, [box_record(index) for index in range(6)])
    output_path = tmp_path / "overlay.mp4"

    class FailedWriter:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(sam_tracker.cv2, "VideoWriter", lambda *args: FailedWriter())
    with pytest.raises(sam_tracker.OverlayError, match="encoder unavailable"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
            "observation-test", output_path, client,
        ))

    assert client.files.deletions == ["file-test"]
    assert not output_path.exists()


def test_source_decode_and_overlay_run_in_threadpool(tmp_path, monkeypatch):
    client = FakeClient()
    worker_threads = []
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)
    install_fake_parser(monkeypatch, [box_record(index) for index in range(6)])
    output_path = tmp_path / "overlay.mp4"
    build = sam_tracker._build_trace_overlay

    def record_worker(*args):
        worker_threads.append(get_ident())
        return build(*args)

    monkeypatch.setattr(sam_tracker, "_build_trace_overlay", record_worker)
    caller_thread = get_ident()
    result = asyncio.run(sam_tracker.track_sam_video(
        source_path, metadata, InitialROI(x=4, y=5, width=10, height=8),
        "observation-test", output_path, client,
    ))

    assert result.status == "succeeded"
    assert worker_threads and worker_threads[0] != caller_thread


def test_invalid_roi_fails_before_remote_upload(tmp_path):
    client = FakeClient()
    source_path = tmp_path / "source.mp4"
    synthetic_video(source_path)
    metadata = inspect_video(source_path)

    with pytest.raises(ValueError, match="fit within"):
        asyncio.run(sam_tracker.track_sam_video(
            source_path, metadata, InitialROI(x=63, y=5, width=2, height=8),
            "observation-test", tmp_path / "overlay.mp4", client,
        ))

    assert client.files.upload is None
