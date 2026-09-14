# Starter verification status

Prepared on 13 September 2026 in a Linux artifact-authoring environment, not on
Leo's Mac. No claim is made that anything is already installed in his project.

Executed command: `python -m pytest -q`
Result: **26 passed, 2 skipped**.
Python 3.13.5; NumPy 2.3.5; pandas 2.2.3; scikit-learn 1.8.0; pytest 9.0.2.

Passed: feature timing and future-mutation invariance, within-zone isolation,
training-only zone selection, panel validity/zero filling, split boundaries,
metric edge cases, fixed model settings and a synthetic correctness benchmark.
Synthetic fixture results are not saved as portfolio benchmarks or shown in the app.

Skipped: DuckDB aggregation integration (dependency absent) and Streamlit empty-state
smoke test (dependency absent). Both checks are included for the Mac environment.
The real data download failed in this environment because the source hostname
could not be resolved. No actual TLC data or real-data model scores are included.
The dashboard source has been created but a populated browser session has not
been run here. A uv lockfile has not been generated here.

Next required checks on the Mac: `uv sync`; rerun all tests with dependencies;
verify official download/schema/aggregation; run the real benchmark; independently
recompute metrics; test the populated UI. Update this file with actual output.
A test pass alone does not prove that the experiment assumptions match reality.
