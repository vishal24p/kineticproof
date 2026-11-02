"""Meta SAM 3.1 tracking adapter; callers provide the authenticated async client."""

from hashlib import file_digest
from pathlib import Path

import cv2
from meta_sam_parser import (
    FramePrompt,
    PromptBox,
    PromptObject,
    SegmentationBoxRecord,
    build_object_prompt,
    parse_responses_stream,
    video_segmentation_format,
)
from starlette.concurrency import run_in_threadpool

from kineticproof_api.tracking import (
    InitialROI,
    OverlayError,
    Provenance,
    TrackFrame,
    TrackResult,
    TrackingFailure,
    VideoMetadata,
    decoded_frames,
    draw_overlay_frame,
    inspect_video,
    normalize_box,
)

SAM_FILE_EXPIRY_SECONDS = 3600


class SAMTrackingError(RuntimeError):
    """SAM request, response, or remote-file cleanup failed."""


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


async def _capture_response_id(events, request_ids):
    async for event in events:
        if _field(event, "type") == "response.created":
            response_id = _field(_field(event, "response"), "id")
            if isinstance(response_id, str):
                request_ids.append(response_id)
        yield event


async def _request_boxes(client, source_path: Path, metadata: VideoMetadata,
                         roi: InitialROI):
    if (roi.x + roi.width > metadata.width
            or roi.y + roi.height > metadata.height):
        raise ValueError("Initial ROI must fit within the first frame")

    prompt = build_object_prompt(
        size=(metadata.width, metadata.height),
        objects=[PromptObject(id=1, prompts=[FramePrompt(
            frame=0,
            box=PromptBox(roi.x, roi.y, roi.x + roi.width, roi.y + roi.height),
        )])],
    )

    remote_file_id = None
    request_error = None
    cleanup_error = None
    records = None
    request_ids = []
    try:
        with source_path.open("rb") as video_file:
            remote_file = await client.files.create(
                file=video_file,
                purpose="user_data",
                expires_after={"anchor": "created_at", "seconds": SAM_FILE_EXPIRY_SECONDS},
            )
        remote_file_id = _field(remote_file, "id")
        if not isinstance(remote_file_id, str) or not remote_file_id:
            raise RuntimeError("Meta file upload returned no file ID")

        events = await client.responses.create(
            model="sam-3.1",
            input=[{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_video", "file_id": remote_file_id},
            ]}],
            stream=True,
            metadata={"propagation_direction": "forward"},
        )
        parsed = parse_responses_stream(
            _capture_response_id(events, request_ids), video_segmentation_format()
        )
        result = await parsed.final_result()
        if result.outcome.status != "completed":
            raise RuntimeError("SAM response stream did not complete")
        if any(diagnostic.severity == "error" for diagnostic in result.diagnostics):
            raise RuntimeError("SAM response contained invalid segmentation records")
        try:
            raw_records = result.records
        except (AttributeError, TypeError) as error:
            raise RuntimeError("SAM parser returned invalid records") from error
        if not isinstance(raw_records, (tuple, list)):
            raise RuntimeError("SAM parser returned invalid records")
        records = tuple(raw_records)
    except Exception as error:
        request_error = error
    finally:
        if remote_file_id:
            try:
                await client.files.delete(file_id=remote_file_id)
            except Exception as error:
                cleanup_error = error

    if cleanup_error:
        detail = "SAM video file deletion failed; its one-hour expiry remains as a backstop"
        if request_error:
            detail += " after the tracking request also failed"
        raise SAMTrackingError(detail) from cleanup_error
    if request_error:
        raise SAMTrackingError("SAM tracking request failed") from request_error

    boxes = {}
    for record in records:
        if not isinstance(record, SegmentationBoxRecord) or record.object_id != "1":
            continue
        frame = record.frame
        if frame is None or type(frame.frame_index) is not int:
            raise SAMTrackingError("SAM box is missing a valid source frame index")
        index = frame.frame_index
        if index < 0 or index >= metadata.frame_count:
            raise SAMTrackingError("SAM box frame index is outside the source video")
        if index in boxes:
            raise SAMTrackingError("SAM returned duplicate boxes for one source frame")
        values = (record.left, record.top,
                  record.right - record.left, record.bottom - record.top)
        box = normalize_box(values, metadata.width, metadata.height)
        if box is None:
            raise SAMTrackingError("SAM returned a box outside the source frame")
        boxes[index] = box

    return boxes, (request_ids[0] if request_ids else None)


def _build_trace_overlay(source_path: Path, metadata: VideoMetadata,
                         observation_id: str, overlay_path: Path, boxes, request_id):
    capture = cv2.VideoCapture(str(source_path), cv2.CAP_FFMPEG)
    writer = None
    completed = False
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        frames = []
        failures = []
        for index, timestamp, frame in decoded_frames(capture, metadata.fps):
            if frame.shape[:2] != (metadata.height, metadata.width):
                raise ValueError("Video dimensions differ from uploaded metadata")
            if index == 0:
                try:
                    # shortcut: CFR preview; JSON PTS remains authoritative until VFR export is needed.
                    writer = cv2.VideoWriter(str(overlay_path), cv2.CAP_FFMPEG,
                        cv2.VideoWriter_fourcc(*"mp4v"), metadata.fps,
                        (metadata.width, metadata.height))
                    if not writer.isOpened():
                        raise OverlayError("Overlay encoder unavailable")
                except (cv2.error, OSError) as error:
                    raise OverlayError("Overlay encoder unavailable") from error

            box = boxes.get(index)
            if box is None:
                failures.append(TrackingFailure(
                    index, "SAM returned no box for this frame",
                    "Record a clearer clip or select the target again on the first frame",
                ))
            frames.append(TrackFrame(
                index,
                timestamp,
                box,
                box.x + box.width / 2 if box else None,
                box.y + box.height / 2 if box else None,
                [] if box else ["tracking_failed"],
            ))
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
            schema_version="1.0.0",
            experiment_id=None,
            video_id=observation_id,
            provider_name="meta_sam",
            model_name="sam-3.1",
            model_version="3.1",
            run_config_id="meta-sam-3.1-forward-box-v1",
            status="partial" if failures else "succeeded",
            frames=frames,
            failures=failures,
            provenance=Provenance(
                source_video_sha256=source_hash,
                preprocessing="none",
                timebase_seconds_per_tick=1 / metadata.fps,
                requested_frames=metadata.frame_count,
                provider_request_id=request_id,
            ),
        )
        completed = True
        return result
    except cv2.error as error:
        raise ValueError("Video could not be processed for SAM overlay") from error
    finally:
        capture.release()
        try:
            if writer is not None:
                writer.release()
        finally:
            if not completed:
                overlay_path.unlink(missing_ok=True)


async def track_sam_video(source_path: Path, metadata: VideoMetadata, roi: InitialROI,
                          observation_id: str, overlay_path: Path, client) -> TrackResult:
    """Run SAM asynchronously and keep local video work off the event loop."""
    boxes, request_id = await _request_boxes(client, source_path, metadata, roi)
    return await run_in_threadpool(
        _build_trace_overlay, source_path, metadata, observation_id, overlay_path,
        boxes, request_id,
    )
