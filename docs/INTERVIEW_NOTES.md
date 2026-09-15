# Explain the project, do not memorise invented results

## Before discussing it
The real-data run is done and independently verified (15 Sep 2026), so
“I built and evaluated this” is accurate. Be open that coding agents helped
implement and review it. Own the reasoning, validation and limitations, rather
than claiming every line was handwritten.

## Numbers you should know cold
Holdout 15-28 Feb 2025, 13,440 predictions, 20 Manhattan zones, 30-minute bins.

| | MAE | RMSE | WAPE | Bias |
|---|---:|---:|---:|---:|
| persistence | 14.29 | 22.19 | 19.4% | +0.01 |
| weekly-naive | 16.22 | 26.03 | 22.0% | +2.29 |
| **boosted trees** | **10.83** | **16.50** | **14.7%** | +1.96 |

24% better MAE than persistence, 33% than weekly-naive, same rows for all three.
Splits: train 8-31 Jan, validation 1-14 Feb, holdout 15-28 Feb, scored once.
Verified: 28 tests pass; metrics recomputed from the saved predictions with a
standalone stdlib script; a fresh end-to-end rerun is bit-identical.

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

**The failure pattern to lead with — weekly-lag staleness (diagnosed, not guessed):**
The model overpredicts in all 20 zones (+1.96 overall) while persistence is unbiased (+0.01).
I first assumed a level shift — that late-February demand simply ran below the January
training level. **The data refuted that:** the two holdout weeks have almost identical mean
demand, 73.40 and 74.24 pickups per zone-bin, yet bias tripled from +0.90 to +3.02.

The pattern is strongly associated with the weekly lag. Across the 14 holdout days the correlation
between “observed minus observed one week earlier” and the model's daily bias is
**r = -0.917** (r-squared approx 0.84). Say "strongly associated with", not "explains 84% of":
this is a correlation on 14 daily points, not a causal ablation. The pattern shows up on two days:

- **Mon 17 Feb (Presidents' Day):** observed 52.24 vs 65.69 the previous Monday. The model,
  anchored on `lag_336`, overpredicted by +5.16.
- **Mon 24 Feb (ordinary Monday):** now the *holiday itself* is the lag feature. Observed
  runs 5.16 above it and the model underpredicts, bias -1.29.

The error reverses sign — the signature of a stale seasonal feature, not a biased level.
That window is 36% of holdout rows and 61% of the total bias.

**Tie it to the baseline flip:** the most plausible link - again association, not proof - is
that the same weekly-lag exposure made weekly-naive the
better baseline on validation (13.93 vs 15.07) and the worse one on test (16.22 vs 14.29).
Validation contains no public holiday; the holdout does. One irregular day coincides with both the
baseline ranking flip and the bias. That is why I report against both baselines.

**Say the limits out loud:** this is an association, not causation. No holiday calendar or
weather data was joined, it rests on 14 daily points, and I ran no ablation — dropping or
gating `lag_336` and re-measuring is the test that would actually establish the mechanism,
and it needs a fresh period.

**Defensible next step:** an irregular-day indicator, or down-weighting `lag_336` when the
previous week's same slot diverges from the recent local level. I deliberately did **not**
implement it: the diagnosis used the holdout, so that holdout can no longer be a clean test
for the fix. The next honest step is a fresh month, selected on validation only.

---

## Live demo runbook (verified 15 Sep 2026)

Total time about 3 minutes. Every command below was executed end to end on this
machine on 15 Sep 2026. Raw data and `artifacts/first-run/` already exist locally,
so nothing depends on the network during the interview.

**Before the call**
```bash
cd /Users/leonardaarons-ditson/Code/fleetcast-odysse
uv sync                     # ~1 s warm
uv run pytest -q            # 28 passed, 1 skipped  (~4 s warm)
ls artifacts/first-run/     # 7 files must be present
```
If `artifacts/first-run/` is missing, stop and rebuild it before the call:
`uv run python -m fleetcast prepare && uv run python -m fleetcast run`.
Do not do this during the demo - `prepare` re-downloads about 120 MB.

**The demo**
```bash
uv run streamlit run app.py     # http://localhost:8501
```
1. **Headline card** - MAE 10.83 on the holdout. Say what the number is: mean
   absolute error in pickups, per zone, per 30 minutes.
2. **Baseline table** (expander) - show all three methods on the same 13,440 rows.
   Make the point that persistence and weekly-naive swap places between validation
   and test, so you quote the improvement against both.
3. **Zone selector** - entries read `Zone name . ID`; pick *Lenox Hill West* (MAE 7.4), then *Penn Station/Madison
   Sq West* (MAE 18.1). Add that Midtown Center has high MAE but the best WAPE, so
   you read the two together rather than ranking on MAE alone.
4. **Day selector** - the dropdown lists plain ISO dates, so pick **2025-02-17**.
   This is Presidents' Day and the clearest instance of the bias pattern: the model
   line sits above observed for most of the day (daily bias +5.16). Then pick
   **2025-02-24** and point out that the sign flips (daily bias -1.29) once the
   holiday itself has become the previous-week lag.
5. **Protocol expander** - splits, features and model config are recorded in JSON,
   alongside the data provenance hashes.

**If Streamlit will not start**, fall back to the numbers, which need no server:
```bash
uv run pytest -q
python3 -c "import json;d=json.load(open('artifacts/first-run/metrics.json'));print(json.dumps(d['test'],indent=1))"
```

**Two things to say unprompted**
- The holdout was scored once. The bias diagnosis came *after* that scoring, which is
  exactly why no holiday feature or bias correction has been added - the fix has to be
  evaluated on a fresh period, not on the window used to find the problem.
- Completed trips are not demand. This forecasts observed pickups, and lower forecast
  error is not evidence of shorter waits or higher earnings.
