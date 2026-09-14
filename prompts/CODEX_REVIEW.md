# Codex independent review assignment

Read AGENTS.md, README.md, docs/BRIEF.md, HANDOFF.md and the actual source/results.
Start only after Claude has stopped writing. Do not trust narrative claims without
checking files and command output. Review, do not replace the architecture.

Run the tests. Inspect the real-data ingestion with special attention to:
- Official source filenames, hashes, month bounds, zone lookup and exclusions.
- Citywide gaps versus zero-count zone intervals, duplicate assumptions, local times.
- Top zones chosen from training only; fixed categorical zone codes.
- All features at forecast t use only observations before t. Per-zone lag/rolling
  calculations must not mix zones. Labels and future outcomes are not features.
- Chronological splits; same timestamp across zones in the same partition;
  disabled random early stopping. Recipe/selection decided on validation, not test.
- Earlier test bins are allowed at later forecast origins only under the declared
  one-step-ahead, zero-latency telemetry assumption. Do not label this a 14-day forecast.
- Identical evaluated rows for every method; WAPE zero denominator handled honestly.

Independently recompute MAE, RMSE, WAPE and bias from predictions.csv.gz. Join
history back to the prediction timestamps to check the baseline lag definitions.
Check all test rows belong to Feb 15–28 and that the output counts match the panel.
Preserve first-run artifacts. A reproduction must use a new output directory and
be labelled a repeat of an already-examined holdout, not a new experiment.

Inspect the dashboard's empty and populated states. Confirm it says historical
replay, not live operations, and that it makes no unmeasured revenue, waiting-time
or causal-benefit claims. Check labels and data source are not silently switched.

Write REVIEW.md with: blocking issues; important nonblocking weaknesses; exact
tests/commands; metric-recalculation results; minimal fixes; and what the owner
should be able to explain. Use line/file references. No speculative 'all good'.
For correctness bugs, add a failing test, make the smallest patch and rerun tests.
If a bug changes the science after the holdout was inspected, explicitly document
that exposure and the need for a new holdout rather than laundering the new score.
Do not add features, cloud infrastructure or a new model search.
