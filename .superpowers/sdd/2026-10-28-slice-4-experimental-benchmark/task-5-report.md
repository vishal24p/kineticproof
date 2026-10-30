
## Follow-up: report hard-link safety

Pre-existing report targets are rejected before tracking or report writes. This prevents hard-link redirection and partial truncation; callers need a fresh report directory for each run. Existing symlink and dataset-input collision checks remain.

Command: `uv run --project services/api pytest -c services/api/pyproject.toml services/api/tests/test_benchmark.py -q -k "hard_linked_report or redirected_report_files or collision_with_dataset_input or existing_report_directory"`

Output:

```text
........                                                                 [100%]
8 passed, 59 deselected in 0.69s
```

Command: `uv run --project services/api pytest -c services/api/pyproject.toml services/api/tests -q`

Output:

```text
........................................................................ [ 45%]
........................................................................ [ 91%]
..............                                                           [100%]
158 passed in 13.51s
```

Command: `uv lock --check --project services/api`

Output: `Resolved 28 packages in 1ms`

Command: `git diff --check`

Output: no output; exit code 0.

The hard-link regression uses only a unique disposable file in the repository and removes it in `finally`; synthetic benchmark fixtures only. No authentic benchmark was run.
