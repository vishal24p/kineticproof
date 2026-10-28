"use client";

export default function Workspace() {
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
          <p className="stage-empty">No video uploaded.</p>
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
