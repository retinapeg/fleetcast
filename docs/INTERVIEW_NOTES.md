# Explain the project, do not memorise invented results

## Before discussing it
Read the generated REPORT.md and verify the implementation locally. At the starter
stage say “I am building”; only say “I built and evaluated” after the actual run.
Be open that coding agents helped implement and review it. Own the reasoning,
validation and limitations, rather than claiming every line was handwritten.

## Opening after a successful run
“I wanted a small example related to operational mobility data, so I built a
half-hourly pickup forecasting pipeline using public NYC taxi records. I used
SQL to build a zone/time panel, compared a learned model against persistence and
weekly seasonality, and evaluated it chronologically rather than randomly splitting
trips. The interesting part is whether the improvement survives on later dates
and in which zones it breaks down. It is a proxy study, not a claim about your
fleet or an increase in driver earnings.”

Add only the measured score and a real failure example from the generated outputs.
A baseline winning is a legitimate finding, not a reason to hide the baseline.

## Eight things to be able to explain
1. **Target:** observed pickups per zone in [t,t+30m), not unmet or total demand.
2. **SQL:** Parquet projection, date/zone validation, half-hour aggregation and
   joining a complete time grid; why zero is an assumption, not missing at random.
3. **Timing:** predict at t with past pickup bins; no same-bin counts or future fares.
   Example: at 10:00 predict 10:00–10:30 using history ending at 10:00.
4. **Baselines:** last half-hour and same half-hour last week. They are cheap,
   interpretable and can be hard to beat; comparison uses identical rows.
5. **Model:** gradient boosting adds small decision trees to correct residual
   structure. Poisson loss is suitable for nonnegative count targets; it does not
   establish that all residuals are truly Poisson, nor supply calibrated intervals.
6. **Evaluation:** model/recipe selected on Feb 1–14; refit on pre-test data;
   fixed weights on Feb 15–28. Earlier test observations may feed later forecasts.
7. **Metrics:** MAE is mean absolute pickup-count error. RMSE weights large misses
   more heavily. WAPE = sum(abs(pred-actual))/sum(actual), not a causal business KPI.
   Bias = mean(pred-actual); positive means overprediction.
8. **Limits:** completed-trip censoring, uncertain telemetry latency, unknown
   vehicle supply and relocation costs, limited winter/city coverage and no
   counterfactual outcomes. Lower error is not proof of a better dispatch policy.

## How this relates to your background
The bridge is numerical modelling plus rigorous testing: make assumptions
explicit, define the observable quantity, compare to a baseline, and investigate
where a model is wrong. Tie this to your own work only in ways you can substantiate.
Do not recite claims about experience, customers or operational impact you do not have.

## A good question for the interviewer
“When you evaluate a positioning recommendation, how do you separate forecasting
quality from changes in vehicle supply and driver behaviour?”

## Real findings — measured after chronological holdout (Feb 15–28)

**Model selected on validation:** boosted_trees (HistGradientBoostingRegressor, Poisson loss)

**Test period scores (14 days, 13,440 predictions):**
| Method | MAE | RMSE | WAPE | Bias |
|---|---:|---:|---:|---:|
| persistence | 14.29 | 22.19 | 19.4% | +0.01 |
| weekly_naive | 16.22 | 26.03 | 22.0% | +2.29 |
| boosted_trees | **10.83** | **16.50** | **14.7%** | +1.96 |

**Improvement:** 24% MAE reduction vs persistence; 33% vs weekly_naive.

**Failure case — high error zone:**
Penn Station/Madison Sq West is the worst zone on both absolute and relative error: MAE 18.1 and WAPE 21.6%, against 7.4 / 13.2% for the best zone (Lenox Hill West). Because WAPE is also worst there, this is not simply a volume artefact — the zone is genuinely harder to forecast. A plausible cause is surge behaviour around a transport hub (train arrivals, events, weather) that lagged pickup counts alone cannot anticipate. Note the contrast with Midtown Center: high MAE (13.5) but the *best* WAPE (11.5%), which is a volume effect rather than a modelling failure. Comparing MAE alone would have mixed these two cases up.

**Domain limitation:**
The lagged-pickup features assume previous 30-minute bins are available immediately. Real deployment requires measuring ingestion/telemetry delay. If delay is >30 minutes, the most recent feature is already stale.

**Defensible next step:**
The model overpredicts in every one of the 20 zones (bias range +0.72 to +4.09, overall +1.96 against persistence's +0.01). That one-sided bias is the clearest open lead: it suggests the Poisson fit is systematically high across the holdout rather than failing in specific zones, so the first thing to check is whether late-February demand simply ran below the January training level. Worth separating that period effect from zone effects before adding any features — a bias correction estimated on validation would be a cheaper next step than a more complex model.
