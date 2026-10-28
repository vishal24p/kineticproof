# Slice 1 — Open Tracking Design

## Goal

Let a local user upload a short video, select the object with a first-frame bounding box, and inspect an OpenCV track trace and annotated overlay.

## User decisions

- Expose tracking through FastAPI upload and tracking endpoints.
- Accept MP4/MOV uploads up to 100,000,000 bytes and 30 seconds.
- Pass the initial target as pixel coordinates `(x, y, width, height)` on the first frame.
- Require integer pixel coordinates and return bounding boxes as `{x, y, width, height}` objects.
- Return exact timestamps in JSON and provide an annotated MP4 overlay.
- Keep the previous successful trace and overlay if a later tracking attempt fails.

## Design

- `POST /api/observations` streams the upload into app-owned temporary storage, validates its extension, size, duration and decodability, and returns an observation id plus basic video metadata.
- `POST /api/observations/{id}/tracking` accepts the initial bounding box and runs OpenCV CSRT synchronously. Keep observation files and result state in an app-lifetime temporary directory and in memory; add no database or job queue.
- `GET /api/observations/{id}/tracks` returns the provider-neutral `TrackResult`; `GET /api/observations/{id}/overlay` serves the annotated MP4. App shutdown removes temporary files.
- Use OpenCV's FFmpeg backend and `CAP_PROP_PTS` for frame presentation timestamps. Convert PTS using the stream FPS time base. If PTS is missing or the backend cannot provide it, fail explicitly; never substitute `frame_index / fps`.
- Use the OpenCV CSRT tracker from `opencv-contrib-python-headless`. Record provider and OpenCV version. A failed update produces an explicit missing-frame flag and null center; do not interpolate or silently relink.
- Add the source timestamp as a visible label in each overlay frame. The JSON trace remains authoritative for timing; overlay playback may normalize variable frame timing to the source average FPS.
- Generate synthetic video in tests and label it synthetic. Do not commit video files or present synthetic output as measured footage.

## Acceptance

- API rejects unsupported extension, over-limit upload, over-limit duration, corrupt media and invalid/out-of-bounds bounding boxes with clear errors.
- A synthetic clip produces monotonically timestamped frames, explicit CSRT failures, and an inspectable overlay endpoint.
- Tests show missing detections remain null and no frame-index/FPS fallback is used.
- Source and overlay files are removed when the API process shuts down.

## Limits

- Tracking is synchronous and single-process. Long-running jobs and multiple workers are outside Slice 1.
- Synthetic tests prove pipeline behavior only; a consented real clip is still needed to validate real-world tracking.

## References

- [OpenCV video timestamps](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html)
- [OpenCV CSRT tracker](https://docs.opencv.org/4.13.0/d2/da2/classcv_1_1TrackerCSRT.html)
- [OpenCV contrib Python wheel](https://pypi.org/project/opencv-contrib-python-headless/4.13.0.92/)
