# FleetCast — first real-data benchmark

Independent case study. NYC yellow taxis are a proxy, not Odysse's London fleet.

## Protocol

Train: Jan 8–31 2025 after seven-day lag warmup. Validate: Feb 1–14. Test: Feb 15–28.
Rolling 30-minute-ahead predictions with fixed evaluation-period weights and observed prior bins.
Previous pickup totals are assumed immediately available. This is not a live system.

Model selected on validation: **boosted_trees**.
Baseline selected on validation: **weekly_naive**.

## Held-out results

| Method | MAE | RMSE | WAPE | Bias |
|---|---:|---:|---:|---:|
| persistence | 14.291 | 22.190 | 19.36% | 0.010 |
| weekly_naive | 16.221 | 26.027 | 21.97% | 2.294 |
| boosted_trees | 10.830 | 16.501 | 14.67% | 1.960 |

## Interpretation limits

These are forecast errors, not a measured reduction in waits or an increase in revenue.
The observations cover completed trips, not rejected requests or unmet demand.
No supply/driver-availability data, causal experiment, dispatch policy or RL result is claimed.
Top-zone selection uses only January; this omits low-volume zones and limits generalisation.
Inspect by_zone.csv and by_day.csv for systematic failure, not only the aggregate score.
Two winter months in one city do not establish seasonal robustness or UK transferability.
The public files are retrospective. Real telemetry latency must be measured before deployment.
Do not tune the model after inspecting this holdout and continue calling it untouched.
