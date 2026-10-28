"use client";

import { type PointerEvent, useEffect, useRef, useState } from "react";

type Observation = {
  observation_id: string;
  width: number;
  height: number;
  duration_seconds: number;
  frame_count: number;
};
type Roi = { x: number; y: number; width: number; height: number };
type TrackResult = {
  status: "succeeded" | "partial" | "failed";
  provider_name: string;
  model_name: string;
  model_version: string;
  frames: {
    frame_index: number;
    timestamp_seconds: number;
    center_x_px: number | null;
    center_y_px: number | null;
    quality_flags: string[];
  }[];
  failures: {
    frame_index: number;
    reason: string;
    recovery_suggestion: string;
  }[];
  provenance: { source_video_sha256: string; [key: string]: unknown };
};

async function checkedResponse(response: Response) {
  if (response.ok) return response;
  const body = await response.json().catch(() => null);
  const detail =
    typeof body?.detail === "string"
      ? body.detail
      : body?.detail
        ? JSON.stringify(body.detail)
        : response.statusText;
  throw new Error(
    `API ${response.status}: ${detail || "Request failed"}.${response.status === 404 ? " Local observation unavailable; upload again after an API restart." : ""}`,
  );
}

export default function Workspace() {
  const [observation, setObservation] = useState<Observation | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [roi, setRoi] = useState<Roi>({ x: 0, y: 0, width: 0, height: 0 });
  const [track, setTrack] = useState<TrackResult | null>(null);
  const [overlayUrl, setOverlayUrl] = useState("");
  const [busy, setBusy] = useState<"upload" | "tracking" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("No video uploaded.");
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  useEffect(
    () => () => {
      if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    },
    [sourceUrl],
  );
  useEffect(
    () => () => {
      if (overlayUrl) URL.revokeObjectURL(overlayUrl);
    },
    [overlayUrl],
  );

  async function upload(file: File | undefined) {
    if (!file) return;
    setError("");
    if (!/\.(mp4|mov)$/i.test(file.name)) {
      setError("Choose an MP4 or MOV file.");
      return;
    }
    if (file.size > 100_000_000) {
      setError("File exceeds 100,000,000 bytes. Choose a smaller clip.");
      return;
    }
    setBusy("upload");
    setNotice("Uploading and validating video…");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await checkedResponse(
        await fetch("/api/observations", { method: "POST", body: form }),
      );
      const next: Observation = await response.json();
      setObservation(next);
      setSourceUrl(URL.createObjectURL(file));
      setRoi({ x: 0, y: 0, width: 0, height: 0 });
      setTrack(null);
      setOverlayUrl("");
      setNotice(
        "Video ready. Drag around the bob on the first frame, or enter target pixels below.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
      setNotice(
        "Upload failed. Choose another clip or check that the local API is running.",
      );
    } finally {
      setBusy(null);
    }
  }

  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.round(
        Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) *
          (observation?.width ?? 0),
      ),
      y: Math.round(
        Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) *
          (observation?.height ?? 0),
      ),
    };
  }
  function selectTarget(event: PointerEvent<HTMLDivElement>) {
    if (!dragStart.current || busy) return;
    const end = point(event);
    const start = dragStart.current;
    setRoi({
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      width: Math.abs(end.x - start.x),
      height: Math.abs(end.y - start.y),
    });
  }

  async function runTracking() {
    if (!observation) return;
    setError("");
    if (
      !Object.values(roi).every(Number.isInteger) ||
      roi.x < 0 ||
      roi.y < 0 ||
      roi.width <= 0 ||
      roi.height <= 0 ||
      roi.x + roi.width > observation.width ||
      roi.y + roi.height > observation.height
    ) {
      setError(
        "Target must use integer pixels, positive width and height, and fit entirely inside the first frame.",
      );
      return;
    }
    setBusy("tracking");
    setNotice(
      "Tracking with OpenCV CSRT… Previous completed output stays available.",
    );
    try {
      const path = `/api/observations/${observation.observation_id}`;
      await checkedResponse(
        await fetch(`${path}/tracking`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(roi),
        }),
      );
      const next: TrackResult = await (
        await checkedResponse(
          await fetch(`${path}/tracks`, { cache: "no-store" }),
        )
      ).json();
      const overlay = await (
        await checkedResponse(
          await fetch(`${path}/overlay`, { cache: "no-store" }),
        )
      ).blob();
      setTrack(next);
      setOverlayUrl(URL.createObjectURL(overlay));
      setNotice(
        next.status === "partial"
          ? "Partial track: some frames are missing. Inspect the overlay and reselect the bob if needed."
          : "Tracking completed. Inspect the overlay; reselect the bob and rerun if the target is wrong.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Tracking failed.");
      setNotice(
        track
          ? "Rerun failed. Previous completed trace and overlay remain visible. Correct the target or check the local API, then retry."
          : "Tracking failed. Correct the target or check the local API, then retry.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-16">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-800">
          KineticProof · Local workspace
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-5xl">
          Investigate motion. Inspect the evidence.
        </h1>
        <p className="mt-5 text-lg leading-8 text-slate-700">
          Start with a pendulum, record a real observation, and trace each
          measurement back to its source.
        </p>
      </header>

      <aside
        aria-label="Local session"
        className="my-8 rounded-xl border border-teal-200 bg-teal-50 p-5 text-sm leading-6 text-teal-950"
      >
        <strong>Local session only.</strong> Video stays on this machine.
        Browser refresh clears the active workspace; stopping the local API
        deletes its uploads and observations. Export evidence before ending your
        session.
      </aside>

      <nav aria-label="Investigation stages" className="mb-8">
        <ol className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <li>
            <a className="stage-link" href="#investigate">
              1. Investigate
            </a>
          </li>
          <li>
            <a className="stage-link" href="#observe">
              2. Observe
            </a>
          </li>
          <li>
            <a className="stage-link" href="#evidence">
              3. Evidence
            </a>
          </li>
          <li>
            <a className="stage-link" href="#next-trial">
              4. Next trial
            </a>
          </li>
        </ol>
      </nav>

      <div className="grid gap-6 lg:grid-cols-2">
        <section
          id="investigate"
          aria-labelledby="investigate-title"
          className="stage-panel"
        >
          <p className="stage-number">01 · Prepare</p>
          <h2 id="investigate-title">Investigate</h2>
          <p>
            First investigation: a simple pendulum. How repeatable is its
            period?
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Use string, a secure support, and a small, soft bob. Clear its
              swing path.
            </li>
            <li>
              Keep the camera fixed, face the swing plane, and keep the whole
              motion in frame.
            </li>
            <li>
              Use good lighting and a plain background; record several complete
              cycles.
            </li>
            <li>
              Record string length if comparing with theory. Include a visible
              scale reference where needed.
            </li>
          </ul>
        </section>

        <section
          id="observe"
          aria-labelledby="observe-title"
          className="stage-panel"
        >
          <p className="stage-number">02 · Record</p>
          <h2 id="observe-title">Observe</h2>
          <p>
            Upload a real MP4 or MOV clip, choose the bob, and inspect its
            annotated track.
          </p>
          <p>
            Limits: 100,000,000 bytes and 30 seconds. Tracking provider: OpenCV
            CSRT.
          </p>
          <label className="field-label" htmlFor="video-upload">
            Upload observation (MP4 or MOV)
          </label>
          <input
            id="video-upload"
            type="file"
            accept=".mp4,.mov,video/mp4,video/quicktime"
            disabled={busy !== null}
            onChange={(event) => {
              void upload(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <p role="status" aria-live="polite">
            {notice}
          </p>
          {error && (
            <p role="alert" className="error-message">
              {error}
            </p>
          )}
          {observation && (
            <>
              <p>
                {observation.width} × {observation.height} pixels ·{" "}
                {observation.duration_seconds.toFixed(3)} seconds ·{" "}
                {observation.frame_count} frames
              </p>
              <p id="target-help">
                Drag a rectangle around the bob. Keyboard: use the four labelled
                pixel fields below, then Run tracking. Origin is the top-left
                corner.
              </p>
              <div
                className="target-frame"
                role="img"
                aria-label="First-frame target selection"
                aria-describedby="target-help"
                onPointerDown={(event) => {
                  if (busy || event.button !== 0) return;
                  event.currentTarget.setPointerCapture(event.pointerId);
                  dragStart.current = point(event);
                  setRoi({ ...dragStart.current, width: 0, height: 0 });
                }}
                onPointerMove={selectTarget}
                onPointerUp={(event) => {
                  selectTarget(event);
                  dragStart.current = null;
                }}
                onPointerCancel={() => {
                  dragStart.current = null;
                }}
              >
                <video
                  src={sourceUrl}
                  muted
                  playsInline
                  preload="auto"
                  aria-label="Uploaded video first frame"
                  onError={() =>
                    setError(
                      "This browser cannot preview the source codec. Convert the clip to a browser-playable MP4, then upload again.",
                    )
                  }
                  onLoadedData={(event) => {
                    event.currentTarget.pause();
                    event.currentTarget.currentTime = 0;
                  }}
                />
                <div
                  className="target-box"
                  style={{
                    left: `${(roi.x / observation.width) * 100}%`,
                    top: `${(roi.y / observation.height) * 100}%`,
                    width: `${(roi.width / observation.width) * 100}%`,
                    height: `${(roi.height / observation.height) * 100}%`,
                  }}
                />
              </div>
              <fieldset disabled={busy !== null} className="roi-fields">
                <legend>Target rectangle in source pixels</legend>
                {(["x", "y", "width", "height"] as const).map((key) => (
                  <label key={key}>
                    {key === "x"
                      ? "Left (x)"
                      : key === "y"
                        ? "Top (y)"
                        : key === "width"
                          ? "Width"
                          : "Height"}
                    <input
                      type="number"
                      step="1"
                      min={key === "x" || key === "y" ? 0 : 1}
                      max={
                        key === "x" || key === "width"
                          ? observation.width
                          : observation.height
                      }
                      value={Number.isNaN(roi[key]) ? "" : roi[key]}
                      onChange={(event) =>
                        setRoi({ ...roi, [key]: event.target.valueAsNumber })
                      }
                    />
                  </label>
                ))}
              </fieldset>
              <button
                type="button"
                className="action-button"
                disabled={busy !== null}
                onClick={() => void runTracking()}
              >
                {busy === "tracking"
                  ? "Tracking…"
                  : track
                    ? "Rerun tracking"
                    : "Run tracking"}
              </button>
            </>
          )}
          {track && (
            <div className="tracking-output">
              <h3>Completed track · {track.status}</h3>
              <p>
                Provider: {track.provider_name} ·{" "}
                {track.model_name.toUpperCase()} · {track.model_version}
              </p>
              <p>
                {track.frames.length} source-timed frames ·{" "}
                {track.failures.length} tracking failures. Missing positions are
                not filled.
              </p>
              {track.status === "partial" && (
                <p>
                  Partial result: inspect missing frames before measuring;
                  correct the target and rerun if needed.
                </p>
              )}
              <video
                src={overlayUrl}
                muted
                controls
                preload="metadata"
                aria-label="Annotated tracking overlay"
                onError={() =>
                  setError(
                    "This browser cannot play the annotated overlay codec. Try a browser with MP4/VP9 playback support.",
                  )
                }
              />
              <p>
                Overlay is a constant-rate preview without audio. Trace
                timestamps remain authoritative.
              </p>
              <details>
                <summary>Inspect source-timed trace</summary>
                <div className="trace-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Frame</th>
                        <th>Time (s)</th>
                        <th>Center x (px)</th>
                        <th>Center y (px)</th>
                        <th>Quality</th>
                      </tr>
                    </thead>
                    <tbody>
                      {track.frames.map((frame) => (
                        <tr key={frame.frame_index}>
                          <td>{frame.frame_index}</td>
                          <td>{frame.timestamp_seconds.toFixed(4)}</td>
                          <td>{frame.center_x_px ?? "Missing"}</td>
                          <td>{frame.center_y_px ?? "Missing"}</td>
                          <td>{frame.quality_flags.join(", ") || "Tracked"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )}
        </section>

        <section
          id="evidence"
          aria-labelledby="evidence-title"
          className="stage-panel"
        >
          <p className="stage-number">03 · Inspect</p>
          <h2 id="evidence-title">Evidence</h2>
          <p>
            Inspect motion, cycle picks, measured period, uncertainty, and
            tracking gaps. Reference values and theory appear separately.
          </p>
          <p className="stage-empty">
            No measurement yet. Evidence requires a real observation and an
            inspected track.
          </p>
        </section>

        <section
          id="next-trial"
          aria-labelledby="next-trial-title"
          className="stage-panel"
        >
          <p className="stage-number">04 · Continue</p>
          <h2 id="next-trial-title">Next trial</h2>
          <p>
            Use the evidence and its limitations to plan a controlled follow-up
            investigation.
          </p>
          <p className="stage-empty">
            Complete an observation before choosing the next trial. A suggested
            plan is separate from a measured result.
          </p>
        </section>
      </div>
    </main>
  );
}
