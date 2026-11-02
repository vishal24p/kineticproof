type Sample = { frame: number; time: number; position: number | null };
type Pick = {
  frame_index: number;
  timestamp_seconds: number;
  position_px: number;
};

export default function TrajectoryPlot({
  samples,
  picks,
}: {
  samples: Sample[];
  picks: Pick[];
}) {
  const values = samples.flatMap((sample) =>
    sample.position === null ? [] : [sample.position],
  );
  if (!values.length) return <p>No valid positions to plot.</p>;
  const low = Math.min(...values, ...picks.map((pick) => pick.position_px));
  const high = Math.max(...values, ...picks.map((pick) => pick.position_px));
  const start = samples[0].time;
  const end = samples[samples.length - 1].time;
  const x = (time: number) => 45 + (500 * (time - start)) / (end - start || 1);
  const y = (position: number) =>
    175 - (150 * (position - low)) / (high - low || 1);
  let drawing = false;
  const path = samples
    .map((sample) => {
      if (sample.position === null) {
        drawing = false;
        return "";
      }
      const command = `${drawing ? "L" : "M"}${x(sample.time)},${y(sample.position)}`;
      drawing = true;
      return command;
    })
    .join(" ");
  return (
    <figure>
      <svg
        viewBox="0 0 570 220"
        role="img"
        aria-label="Projected source-timed trajectory with detected turning points. Gaps are not joined."
      >
        <title>Projected trajectory and detected turning points</title>
        <path d="M45 20V175H550" fill="none" stroke="#64748b" />
        <path d={path} fill="none" stroke="#0f766e" strokeWidth="2" />
        {picks.map((pick) => (
          <circle
            key={pick.frame_index}
            cx={x(pick.timestamp_seconds)}
            cy={y(pick.position_px)}
            r="4"
            fill="#9a3412"
          >
            <title>
              Detected pick: frame {pick.frame_index},{" "}
              {pick.timestamp_seconds.toFixed(4)} s
            </title>
          </circle>
        ))}
        <text x="45" y="195" fontSize="12">
          {start.toFixed(2)} s
        </text>
        <text x="505" y="195" fontSize="12">
          {end.toFixed(2)} s
        </text>
        <text x="4" y="22" fontSize="11">
          {high.toFixed(1)}
        </text>
        <text x="4" y="175" fontSize="11">
          {low.toFixed(1)}
        </text>
        <text x="180" y="215" fontSize="12">
          Source time (s) · projection (px)
        </text>
      </svg>
      <figcaption>
        Teal: raw projected centers. Orange circles: detected filtered turning
        points. Missing positions break the line.
      </figcaption>
    </figure>
  );
}
