# Task 2 report — Freeze immutable test inputs

Implemented `freeze_dataset` and `verify_frozen_inputs` in `services/api/src/kineticproof_api/benchmark.py`. Locks contain dataset-relative manifest/label paths, canonical test clip records and label rows, each test video SHA-256, the canonical label-row SHA-256, the complete session split map, benchmark configuration, and source commit. The canonical payload digest is checked before live inputs are compared. Dev-only label edits remain allowed when the split map is unchanged. Existing lock files and lock paths inside the repository are rejected; missing or malformed source commit metadata is rejected.

## Verification

Command: `uv run --project services/api pytest services/api/tests/test_benchmark.py -q`

Output: `42 passed in 0.88s`

Command: `git -c core.whitespace=cr-at-eol diff --check`

Output: no output; exit code 0.

No authentic benchmark was run; tests use generated synthetic media only.
