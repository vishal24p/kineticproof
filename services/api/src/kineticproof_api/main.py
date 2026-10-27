from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from kineticproof_api.tracking import VideoMetadata, inspect_video

MAX_UPLOAD_BYTES = 100_000_000
MAX_DURATION_SECONDS = 30


@dataclass
class Observation:
    source_path: Path
    metadata: VideoMetadata


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
                output.write(chunk)
        try:
            metadata = await run_in_threadpool(inspect_video, source_path)
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
