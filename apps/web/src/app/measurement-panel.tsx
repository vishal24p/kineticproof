"use client";

import { type PointerEvent, useRef, useState } from "react";
import { checkedResponse, type TrackResult } from "./observation-api";
import TrajectoryPlot from "./trajectory-plot";

type ReferenceEvent = {
  event_type: "leftmost" | "rightmost" | "same_direction";
  timestamp_seconds: number;
  evidence_frame_index: number;
  uncertainty_seconds: number;
};
type MeasurementRequest = {
  motion_axis: { x: number; y: number };
  reference_events: ReferenceEvent[];
  length_m?: number;
  gravity_m_s2?: number;
};
type MeasurementResult = {
  status: "succeeded" | "insufficient_data";
  motion_axis: { x: number; y: number };
  measured_period_seconds: number | null;
  cycle_mad_seconds: number | null;
  manual_reference_period_seconds: number | null;
  theoretical_period_seconds: number | null;
  source_timing_resolution_seconds: number | null;
  valid_frame_count: number;
  total_frame_count: number;
  turning_points: {
    frame_index: number;
    timestamp_seconds: number;
    position_px: number;
  }[];
  cycles: {
    start_frame_index: number;
    end_frame_index: number;
    period_seconds: number;
  }[];
  gap_ranges: { start_frame_index: number; end_frame_index: number }[];
  warnings: string[];
  measurement_config: Record<string, string | number>;
  manual_reference_intervals: Record<string, string | number>[];
  provenance: Record<string, string>;
};
export type MeasurementSummary = Pick<
  MeasurementResult,
  "status" | "gap_ranges"
>;

type Axis = { startX: number; startY: number; endX: number; endY: number };

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function MeasurementPanel({
  observationId,
  track,
  overlayUrl,
  disabled,
  onBusyChange,
  onResult,
}: {
  observationId: string;
  track: TrackResult;
  overlayUrl: string;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onResult: (result: MeasurementSummary) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const dragging = useRef(false);
  const [axis, setAxis] = useState<Axis>({
    startX: 20,
    startY: 50,
    endX: 80,
    endY: 50,
  });
  const [framePosition, setFramePosition] = useState(0);
  const [eventType, setEventType] =
    useState<ReferenceEvent["event_type"]>("leftmost");
  const [manualTime, setManualTime] = useState("");
  const [uncertainty, setUncertainty] = useState("");
  const [events, setEvents] = useState<ReferenceEvent[]>([]);
  const [length, setLength] = useState("");
  const [gravity, setGravity] = useState("");
  const [busy, setWorking] = useState(false);
  const blocked = busy || disabled;
  function setBusy(working: boolean) {
    setWorking(working);
    onBusyChange(working);
  }
  const [error, setError] = useState("");
  const [evidence, setEvidence] = useState<{
    result: MeasurementResult;
    request: MeasurementRequest;
  } | null>(null);
  const selected = track.frames[framePosition];

  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(100, (100 * (event.clientX - bounds.left)) / bounds.width),
      ),
      y: Math.max(
        0,
        Math.min(100, (100 * (event.clientY - bounds.top)) / bounds.height),
      ),
    };
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!dragging.current || blocked) return;
    const end = point(event);
    setAxis((current) => ({ ...current, endX: end.x, endY: end.y }));
  }
  function scrub(position: number) {
    setFramePosition(position);
    const preview = video.current;
    // Overlay is constant FPS; its frame order, never its PTS, selects evidence.
    if (preview && Number.isFinite(preview.duration))
      preview.currentTime = (position * preview.duration) / track.frames.length;
  }
  function addEvent() {
    setError("");
    const time = Number(manualTime),
      delta = Number(uncertainty);
    if (
      !manualTime.trim() ||
      !uncertainty.trim() ||
      !Number.isFinite(time) ||
      !Number.isFinite(delta) ||
      delta < 0 ||
      (events.length > 0 && time <= events[events.length - 1].timestamp_seconds)
    ) {
      setError(
        "Enter an independent finite timestamp, later than the previous event, and a finite nonnegative uncertainty.",
      );
      return;
    }
    setEvents([
      ...events,
      {
        event_type: eventType,
        timestamp_seconds: time,
        uncertainty_seconds: delta,
        evidence_frame_index: selected.frame_index,
      },
    ]);
    setManualTime("");
  }
  async function measure() {
    if (blocked) return;
    setError("");
    const x = (axis.endX - axis.startX) * (video.current?.videoWidth ?? 0);
    const y = (axis.endY - axis.startY) * (video.current?.videoHeight ?? 0);
    const norm = Math.hypot(x, y);
    if (
      !Object.values(axis).every(
        (value) => Number.isFinite(value) && value >= 0 && value <= 100,
      ) ||
      !Number.isFinite(norm) ||
      norm === 0
    ) {
      setError(
        "Draw a nonzero axis within the loaded video, or enter endpoints from 0 to 100 percent.",
      );
      return;
    }
    if (
      (length !== "" || gravity !== "") &&
      (!length.trim() ||
        !gravity.trim() ||
        ![Number(length), Number(gravity)].every(
          (value) => Number.isFinite(value) && value > 0,
        ))
    ) {
      setError(
        "Theory needs both a positive finite length and gravity, or leave both blank.",
      );
      return;
    }
    const request: MeasurementRequest = {
      motion_axis: { x: x / norm, y: y / norm },
      reference_events: events,
    };
    if (length !== "") {
      request.length_m = Number(length);
      request.gravity_m_s2 = Number(gravity);
    }
    setBusy(true);
    try {
      const result: MeasurementResult = await (
        await checkedResponse(
          await fetch(
            `/api/observations/${observationId}/measure?format=json`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(request),
            },
          ),
        )
      ).json();
      setEvidence({ result, request });
      onResult({ status: result.status, gap_ranges: result.gap_ranges });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Measurement failed.");
    } finally {
      setBusy(false);
    }
  }
  async function exportCsv() {
    if (!evidence || blocked) return;
    setBusy(true);
    setError("");
    try {
      const response = await checkedResponse(
        await fetch(`/api/observations/${observationId}/measure?format=csv`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(evidence.request),
        }),
      );
      download(await response.blob(), `kineticproof-${observationId}.csv`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV export failed.");
    } finally {
      setBusy(false);
    }
  }
  const result = evidence?.result;
  return (
    <div className="measurement-panel">
      <p id="axis-help">
        Drag a line along the swing direction. Keyboard: edit endpoint
        percentages below. Arrow keys adjust each number. The axis uses
        source-pixel geometry.
      </p>
      <div
        className="target-frame"
        role="img"
        aria-label="Motion axis selection"
        aria-describedby="axis-help"
        onPointerDown={(event) => {
          if (blocked || event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          dragging.current = true;
          const start = point(event);
          setAxis({
            startX: start.x,
            startY: start.y,
            endX: start.x,
            endY: start.y,
          });
        }}
        onPointerMove={move}
        onPointerUp={(event) => {
          move(event);
          dragging.current = false;
        }}
        onPointerCancel={() => {
          dragging.current = false;
        }}
      >
        <video
          ref={video}
          src={overlayUrl}
          muted
          playsInline
          preload="auto"
          aria-label="Axis and manual evidence frame"
          onError={() =>
            setError(
              "Overlay playback unavailable. Use a browser with MP4/VP9 support.",
            )
          }
        />
        <svg
          className="axis-line"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <line
            x1={axis.startX}
            y1={axis.startY}
            x2={axis.endX}
            y2={axis.endY}
            stroke="#facc15"
            strokeWidth="1"
          />
          <circle cx={axis.startX} cy={axis.startY} r="1.5" fill="#facc15" />
        </svg>
      </div>
      <fieldset className="roi-fields" disabled={blocked}>
        <legend>Motion axis endpoints (%) · dot marks start</legend>
        {(["startX", "startY", "endX", "endY"] as const).map((key) => (
          <label key={key}>
            {
              {
                startX: "Axis start x",
                startY: "Axis start y",
                endX: "Axis end x",
                endY: "Axis end y",
              }[key]
            }
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={Number.isNaN(axis[key]) ? "" : axis[key]}
              onChange={(event) =>
                setAxis({ ...axis, [key]: event.target.valueAsNumber })
              }
            />
          </label>
        ))}
      </fieldset>
      <details>
        <summary>Optional independent manual reference</summary>
        <p>
          Scrub to identify an annotated evidence frame only. Enter your
          independently timed event and uncertainty separately; video time never
          fills these fields.
        </p>
        <label className="field-label" htmlFor="evidence-frame">
          Evidence frame: {selected.frame_index}
        </label>
        <input
          id="evidence-frame"
          type="range"
          min="0"
          max={track.frames.length - 1}
          step="1"
          value={framePosition}
          disabled={blocked}
          onChange={(event) => scrub(Number(event.target.value))}
        />
        <fieldset className="roi-fields" disabled={blocked}>
          <legend>Manual event inputs</legend>
          <label>
            Event type
            <select
              value={eventType}
              onChange={(event) =>
                setEventType(event.target.value as ReferenceEvent["event_type"])
              }
            >
              <option value="leftmost">Leftmost</option>
              <option value="rightmost">Rightmost</option>
              <option value="same_direction">Same direction crossing</option>
            </select>
          </label>
          <label>
            Independent timestamp (s)
            <input
              type="number"
              step="any"
              value={manualTime}
              onChange={(event) => setManualTime(event.target.value)}
            />
          </label>
          <label>
            Timing uncertainty (s)
            <input
              type="number"
              min="0"
              step="any"
              value={uncertainty}
              onChange={(event) => setUncertainty(event.target.value)}
            />
          </label>
        </fieldset>
        <button
          type="button"
          className="action-button"
          disabled={blocked}
          onClick={addEvent}
        >
          Add manual event
        </button>
        <ol>
          {events.map((event, index) => (
            <li
              key={`${event.timestamp_seconds}-${event.evidence_frame_index}`}
            >
              {event.event_type} · {event.timestamp_seconds} ±{" "}
              {event.uncertainty_seconds} s · evidence frame{" "}
              {event.evidence_frame_index}{" "}
              <button
                type="button"
                disabled={blocked}
                onClick={() => setEvents(events.filter((_, i) => i !== index))}
              >
                Remove event {index + 1}
              </button>
            </li>
          ))}
        </ol>
      </details>
      <fieldset className="roi-fields" disabled={blocked}>
        <legend>Optional theory · supply both or leave both blank</legend>
        <label>
          Pivot to bob center of mass (m)
          <input
            type="number"
            min="0"
            step="any"
            value={length}
            onChange={(event) => setLength(event.target.value)}
          />
        </label>
        <label>
          Gravity (m/s²)
          <input
            type="number"
            min="0"
            step="any"
            value={gravity}
            onChange={(event) => setGravity(event.target.value)}
          />
        </label>
      </fieldset>
      <button
        type="button"
        className="action-button"
        disabled={blocked}
        onClick={() => void measure()}
      >
        {busy ? "Working…" : "Measure period"}
      </button>
      <p role="status" aria-live="polite">
        {busy
          ? "Request in progress…"
          : disabled
            ? "Measurement and exports are disabled while upload/tracking is active or current tracking output needs recovery."
            : result
              ? `Last completed measurement: ${result.status}. Results and exports use the inputs from that completed request; measure again after edits.`
              : "Choose the axis, then measure. Manual reference and theory are optional."}
      </p>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {result && (
        <div className="measurement-results">
          <TrajectoryPlot
            samples={track.frames.map((frame) => ({
              frame: frame.frame_index,
              time: frame.timestamp_seconds,
              position:
                frame.center_x_px === null || frame.center_y_px === null
                  ? null
                  : frame.center_x_px * result.motion_axis.x +
                    frame.center_y_px * result.motion_axis.y,
            }))}
            picks={result.turning_points}
          />
          <h3>Measured from tracked motion</h3>
          {result.status === "succeeded" &&
          result.measured_period_seconds !== null ? (
            <p>
              Measured period: {result.measured_period_seconds.toFixed(4)} s ·
              Cycle MAD: {result.cycle_mad_seconds?.toFixed(4) ?? "Unavailable"}{" "}
              s
            </p>
          ) : (
            <p>
              Insufficient data: at least two complete detected cycles are
              required. No measured period available.
            </p>
          )}
          <p>
            {result.valid_frame_count}/{result.total_frame_count} valid frames ·{" "}
            {result.cycles.length} detected cycles · Source timing resolution:{" "}
            {result.source_timing_resolution_seconds === null
              ? "Unavailable"
              : `${result.source_timing_resolution_seconds.toFixed(5)} s`}
            . MAD describes cycle spread, not total experimental uncertainty.
          </p>
          <h3>Independent manual reference</h3>
          <p>
            {result.manual_reference_period_seconds === null
              ? "No comparable manual intervals supplied."
              : `Manual reference period: ${result.manual_reference_period_seconds.toFixed(4)} s`}
          </p>
          <h3>Calculated theory</h3>
          <p>
            {result.theoretical_period_seconds === null
              ? "No theory inputs supplied."
              : `Theoretical period: ${result.theoretical_period_seconds.toFixed(4)} s (small-angle simple pendulum).`}
          </p>
          <h3>Warnings and gaps</h3>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          <p>
            {result.gap_ranges.length
              ? `Missing frames: ${result.gap_ranges.map((gap) => `${gap.start_frame_index}–${gap.end_frame_index}`).join(", ")}. No interpolation.`
              : "No tracking gaps reported."}
          </p>
          <details>
            <summary>Cycle picks, method and provenance</summary>
            <ol>
              {result.cycles.map((cycle) => (
                <li key={cycle.start_frame_index}>
                  Frames {cycle.start_frame_index}–{cycle.end_frame_index}:{" "}
                  {cycle.period_seconds.toFixed(4)} s
                </li>
              ))}
            </ol>
            <p>
              Method:{" "}
              {Object.entries(result.measurement_config)
                .map(([key, value]) => `${key}: ${value}`)
                .join(" · ")}
            </p>
            <dl>
              {Object.entries(result.provenance).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p>
              Entered manual events, intervals, full thresholds and provenance
              remain in JSON evidence.
            </p>
          </details>
          <div className="export-actions">
            <button
              type="button"
              className="action-button"
              disabled={blocked}
              onClick={() =>
                download(
                  new Blob(
                    [
                      JSON.stringify(
                        { request: evidence.request, result },
                        null,
                        2,
                      ),
                    ],
                    { type: "application/json" },
                  ),
                  `kineticproof-${observationId}.json`,
                )
              }
            >
              Download JSON evidence
            </button>
            <button
              type="button"
              className="action-button"
              disabled={blocked}
              onClick={() => void exportCsv()}
            >
              Download CSV
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
