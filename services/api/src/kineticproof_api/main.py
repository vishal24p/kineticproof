from contextlib import asynccontextmanager
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, UploadFile
from openai import AsyncOpenAI
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse, Response

from kineticproof_api.physics import (
    MeasurementRequest, MeasurementResult, measure_trace, measurement_csv,
)

from kineticproof_api.tracking import (
    InitialROI, OverlayError, TrackResult, TrackingRun, UnsupportedContainer,
    VideoMetadata, inspect_video, track_video,
)
from kineticproof_api.sam_tracker import SAMTrackingError, track_sam_video

MAX_UPLOAD_BYTES = 100_000_000
MULTIPART_ALLOWANCE_BYTES = 65_536
MAX_DURATION_SECONDS = 30


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/observations"
        ):
            await self.app(scope, receive, send)
            return
        limit = MAX_UPLOAD_BYTES + MULTIPART_ALLOWANCE_BYTES
        rejection = JSONResponse({"detail": "Upload request exceeds body limit"}, 413)
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    too_large = int(value) > limit
                except ValueError:
                    too_large = False
                if too_large:
                    await rejection(scope, receive, send)
                    return
        # Validate on bounded disk storage before multipart parsing can spool files.
        with TemporaryFile() as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limit:
                    await rejection(scope, receive, send)
                    return
                await run_in_threadpool(body.write, chunk)
                if not message.get("more_body", False):
                    break
            body.seek(0)

            async def replay():
                chunk = await run_in_threadpool(body.read, 1024 * 1024)
                return {"type": "http.request", "body": chunk, "more_body": bool(chunk)}

            await self.app(scope, replay, send)


@dataclass
class Observation:
    source_path: Path
    metadata: VideoMetadata
    tracking_run: TrackingRun | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    with TemporaryDirectory(prefix="kineticproof-") as directory:
        app.state.media_dir = Path(directory)
        app.state.observations = {}
        try:
            yield
        finally:
            app.state.observations.clear()


app = FastAPI(title="KineticProof API", lifespan=lifespan)
app.add_middleware(UploadBodyLimit)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/observations")
async def upload_observation(file: UploadFile) -> dict[str, str | float | int]:
    source_path = None
    accepted = False
    try:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".mp4", ".mov"}:
            raise HTTPException(415, "Only MP4 and MOV videos are supported")
        observation_id = str(uuid4())
        source_path = app.state.media_dir / f"{observation_id}{suffix}"
        size = 0
        with source_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Video exceeds 100 MB upload limit")
                await run_in_threadpool(output.write, chunk)
        try:
            metadata = await run_in_threadpool(inspect_video, source_path)
        except UnsupportedContainer as error:
            raise HTTPException(415, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if metadata.duration_seconds > MAX_DURATION_SECONDS:
            raise HTTPException(413, "Video exceeds 30 second duration limit")
        app.state.observations[observation_id] = Observation(source_path, metadata)
        accepted = True
        return {
            "observation_id": observation_id,
            "duration_seconds": metadata.duration_seconds,
            "width": metadata.width,
            "height": metadata.height,
            "frame_count": metadata.frame_count,
        }
    finally:
        if source_path is not None and not accepted:
            source_path.unlink(missing_ok=True)
        await file.close()


def get_observation(observation_id: str) -> Observation:
    observation = app.state.observations.get(observation_id)
    if observation is None:
        raise HTTPException(404, "Observation not found")
    return observation


def get_tracking_run(observation_id: str) -> TrackingRun:
    run = get_observation(observation_id).tracking_run
    if run is None:
        raise HTTPException(409, "No completed tracking result")
    return run


@app.post("/api/observations/{observation_id}/tracking")
async def track_observation(
    observation_id: str,
    roi: InitialROI,
    provider: Literal["opencv", "meta_sam"] = Query("opencv"),
) -> dict[str, str | int]:
    observation = get_observation(observation_id)
    if roi.x + roi.width > observation.metadata.width or roi.y + roi.height > observation.metadata.height:
        raise HTTPException(422, "Initial ROI must fit within the first frame")
    overlay_path = app.state.media_dir / f"{uuid4()}-overlay.mp4"
    if provider == "opencv":
        try:
            trace = await run_in_threadpool(
                track_video, observation.source_path, observation.metadata,
                roi, observation_id, overlay_path,
            )
        except OverlayError as error:
            raise HTTPException(500, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    else:
        api_key = getenv("MODEL_API_KEY")
        if not api_key:
            raise HTTPException(503, "Meta SAM is unavailable: MODEL_API_KEY is not configured")
        client = AsyncOpenAI(
            base_url="https://api.meta.ai/v1",
            api_key=api_key,
            max_retries=0,
        )
        try:
            trace = await track_sam_video(
                observation.source_path, observation.metadata, roi,
                observation_id, overlay_path, client,
            )
        except OverlayError as error:
            raise HTTPException(500, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except SAMTrackingError as error:
            raise HTTPException(502, str(error)) from error
        finally:
            await client.close()
    # One assignment publishes the matching pair; failed reruns leave prior output intact.
    observation.tracking_run = TrackingRun(trace, overlay_path)
    return {"status": trace.status, "frame_count": len(trace.frames)}


@app.get("/api/observations/{observation_id}/tracks", response_model=TrackResult)
def get_tracks(observation_id: str) -> TrackResult:
    return get_tracking_run(observation_id).trace


@app.post("/api/observations/{observation_id}/measure", response_model=None)
def measure_observation(
    observation_id: str,
    request: MeasurementRequest,
    response_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
) -> MeasurementResult | Response:
    try:
        result = measure_trace(get_tracking_run(observation_id).trace, request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if response_format == "csv":
        return Response(measurement_csv(result), media_type="text/csv",
                        headers={"X-Measurement-Status": result.status})
    return result


@app.get("/api/observations/{observation_id}/overlay")
def get_overlay(observation_id: str) -> FileResponse:
    return FileResponse(get_tracking_run(observation_id).overlay_path, media_type="video/mp4")
