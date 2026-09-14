# Project brief and scope freeze

## Why this company
The original September 2026 Odysse advert asks for Python/SQL, practical modelling
on trip and operational data, experiment evaluation and lightweight tools. It
also welcomes AI-assisted prototyping. Its fleet positioning problem is a useful
motivation for this forecast-first project, without pretending to reproduce its
proprietary reinforcement-learning system.

Primary role: https://uk.linkedin.com/jobs/view/data-scientist-at-odysse-ltd-4464356243
Company: https://www.ody.tech/
Checked: 13 September 2026. No employer data or private methods are assumed.

## Product sentence
“Forecast the next half-hour of observed pickups by zone, compare against simple
baselines, and show exactly where the model fails.”

## Scientific contract
The target is completed yellow-taxi pickup counts, not all latent ride demand.
Two public winter months; 20 Manhattan zones selected on January only. This is
intentionally smaller than the earlier proposal involving high-volume ride-hailing
files, simulation and vehicle repositioning. Yellow taxis are a proxy; keep that
qualification visible. Do not quietly swap data families if a download fails.

The fixed split, model recipe and output contract are in the source and README.
An honest negative result is acceptable. No 'at least 20% improvement' requirement.
No causal inference from forecasting scores. No revenue/wait-time claims.

## Acceptance before showing the project
Real ingestion completed with hashes and exclusions recorded; full dependency
integration tests run locally; chronological experiment produces reusable
predictions; recomputed metrics agree; the dashboard opens without fabricated
data; the owner can explain the target, baselines, timing and limitations.

## Demo, not a sales pitch
Show the historical period label, select one zone/day, compare observed pickups
with the three forecasts, inspect the full-period error table, then show one
failure case. The busiest-zone ranking is a forecast view, not a driver instruction.
Do not cherry-pick one good chart as evidence for general performance.

## Not in this version
No RL, GPU training, 3D city, API server, authentication, Docker, paid APIs,
streaming pipeline, database service, embeddings, multi-agent product or deployment.
No hyperparameter search after seeing the holdout. No extra notebooks duplicating
the implementation merely to inflate the deliverables.

## After the interview, only as possible future work
A genuinely operational evaluation would require vehicle availability, travel
times, repositioning costs, rejected requests, demand/supply feedback and safe
online validation. Additional seasons and a new held-out period come before
claiming generalisation. A time-blocked residual analysis and a latency stress
test are more useful next steps than a new UI framework.
