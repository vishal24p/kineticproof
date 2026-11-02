# Meta API integration and validation

## Implemented locally

The tracking endpoint has an opt-in `provider=meta_sam` path using the OpenAI async Python SDK against Meta Model API, SAM 3.1 (`sam-3.1`), and Meta's official `meta-sam-parser`. It accepts the existing first-frame ROI, requests forward propagation, maps output frame records to local source PTS, derives centers from output-box midpoints, and returns the shared TrackResult and overlay. OpenCV remains the default. A SAM failure never switches providers or replaces a previous successful result.

The SAM path reads `MODEL_API_KEY` at request time. It uploads only when explicitly selected, requests remote file expiry after 3600 seconds, then attempts deletion after parsing. Deletion failure is surfaced; the expiry is the cleanup backstop. Offline tests use fake clients and synthetic video only.

## Not verified

- Account entitlement, credits, billing controls, and access to `sam-3.1` for this account.
- Any live upload or SAM response, including real response shape, frame coverage, accuracy, quality, latency, or actual cost.
- Comparative value against OpenCV on identical authorized footage and independent labels.

No paid or hosted call was made for this implementation. Do not report SAM as validated or claim improved tracking until a consented clip has been run after account access and spending authorization are confirmed.

## Next validation steps

1. Check first-party Meta documentation for current limits, supported media, billing, and request behavior before a live run.
2. Confirm account entitlement, spend controls, user authorization, and consent for the specific source clip.
3. Make a bounded live evaluation only after explicit authorization. Record sanitized request/response details, frames returned, cleanup outcome, elapsed time, and actual cost.
4. Compare SAM and OpenCV on the same clip and independent references. Keep gaps and failures visible; make no claim from synthetic fixtures.

Official references: [SAM prompts and tracking](https://dev.meta.ai/docs/sam/segmenting), [Meta Python parser](https://dev.meta.ai/docs/sam/client-libraries), [file expiry and deletion](https://dev.meta.ai/docs/file-handling), [pricing and limits](https://dev.meta.ai/docs/pricing-rate-limits).
