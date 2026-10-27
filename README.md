# KineticProof 2.0 — product and implementation documentation (v2)

**Mission:** Make real, low-cost physics experiments investigable with everyday materials and a phone: plan a question, gather genuine observations, derive measurements with transparent algorithms, judge quality and uncertainty, compare evidence against a reference/theory, and propose the next experiment. The pendulum is the **first demonstration**, not the product's identity or permanent limitation.

**Implementation strategy:** Build a complete provider-agnostic pipeline using a genuinely runnable open-source tracking method/model first. Integrate hosted Meta SAM 3.1 and Muse Spark as a **later provider migration/extension**, not a blocker to implementation. Never misrepresent open-model outputs as Meta outputs; the submitted project must genuinely use Meta products, and its value must be demonstrated with real evidence.

**Where to start:** `AGENTS.md` -> `docs/00_INDEX.md` -> `docs/PRODUCT.md` -> `docs/WORKFLOWS.md` -> `docs/ARCHITECTURE.md` -> `docs/IMPLEMENTATION.md`. Read workstream-specific documents before changing that area. No single document is intended to contain everything.

**Project status:** Documentation and design only. No code, measured footage, tests, models, benchmarks, deployment, or Meta integration verified in this package.

**Hackathon:** Meta Global AI Developer Hackathon, Indie Developer track; public GitHub repository and 3-minute demo-video URLs required by the user-inspected submission form. Deadline: Nov 4, 2026, 9:00 PM US Eastern per event; re-confirm time and local conversion at submission. See `docs/HACKATHON_RULES.md` and `docs/SUBMISSION.md`.

**Non-goals for the MVP:** native mobile app, live-streaming capture, user accounts, generalized arbitrary physics interpretation, invented measurements, complex infra. Future experiments are extensibility targets; do not silently claim they work.
