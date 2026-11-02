# Slice 6 README Architecture and Benchmark Status Plan

> **For agentic workers:** Use the repository docs as the source of truth. This is a docs-only task; do not invent benchmark evidence.

**Goal:** Give public README readers a concise architecture view and an honest benchmark-status snapshot.

**Architecture:** Add a short text flow for the implemented local path and a small table of current evidence counts. Link to the architecture, evaluation, and dataset docs for detail.

**Source documents:** `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`, `docs/DATA_AND_ANNOTATION.md`, and Slice 6 in `docs/IMPLEMENTATION.md`.

## Decisions

- Report zero verified dataset clips, zero independent labels, and zero benchmark runs/results; metric values remain unavailable.
- Describe local process memory and app-owned temporary media accurately; do not imply public deployment or hosted Meta behavior is verified.
- Keep release version `0.6.1.0`; this is documentation added to the same Slice 6 PR, not a separate release.

## Task 1: Add README architecture and benchmark evidence

**Files:**
- Modify: `README.md`

- [ ] Add a compact architecture flow and one table of observed evidence counts.
- [ ] Link the detailed architecture, evaluation protocol, and dataset/annotation docs.
- [ ] Verify values against source docs and run `git diff --check`.

**Acceptance:** README distinguishes implemented local components from unverified hosted/deployment behavior and reports no benchmark measurements as available.
