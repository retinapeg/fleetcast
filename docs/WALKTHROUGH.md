# FleetCast — walkthrough and demo notes

## Start here

```bash
cd fleetcast
./demo.sh
```

`demo.sh` pre-flights the environment and the frozen artifacts, frees port 8599 and
opens http://127.0.0.1:8599 once the server is healthy. Stop with Ctrl-C. The
installed environment and saved artifacts are sufficient: no installation, download
or training during the demo. If the server cannot start, the script prints the
fallback: open `artifacts/first-run/REPORT.md` and these notes. If the artifacts are
missing, use the report/notes fallback; do not improvise scores.

`docs/DEMO_CARD.md` is the one-screen version of this file to keep open during the call.

## 60–90 second project story

“I built FleetCast as an independent mobility forecasting case study using public
NYC yellow-taxi records. The question is deliberately narrow: at the start of each
half-hour, predict observed pickups in the next half-hour across 20 Manhattan zones.

I used DuckDB SQL to build a complete zone/time panel, then compared persistence,
weekly seasonality and a small gradient-boosted tree model with Poisson loss. The
features use earlier observations, and evaluation is chronological: January for
training, early February for validation, and 15–28 February for the holdout. Model
weights are fixed during the holdout; earlier observed bins feed later forecasts.

On 13,440 predictions, model MAE is 10.83 pickups per zone per half-hour, versus
14.29 for persistence and 16.22 for weekly seasonality: reductions of 24% and 33%.
I independently checked the stored predictions against the reported metrics.

The interesting limitation is positive bias, about two pickups per bin. Its daily
pattern is strongly associated with the weekly lag being out of step with current
activity. That is a hypothesis, not causal proof. I have not changed the model:
this diagnosis used the holdout, so a proposed fix needs a fresh test period.
This forecasts observed trips; it does not establish lower waits or higher earnings.”

Be open that coding agents helped implement and review the project. Own the
problem definition, assumptions and validation; do not claim every line was handwritten.

## Verified results

Holdout: **15–28 February 2025**, 20 zones × 14 days × 48 bins = **13,440 predictions**.
MAE, RMSE and bias are pickups per zone per half-hour. WAPE below is a percentage.

| Method | MAE | RMSE | WAPE | Bias |
|---|---:|---:|---:|---:|
| Persistence | 14.29 | 22.19 | 19.4% | +0.01 |
| Weekly-naive | 16.22 | 26.03 | 22.0% | +2.29 |
| Boosted trees | **10.83** | **16.50** | **14.7%** | **+1.96** |

Exact relative MAE reductions: **24.2%** vs persistence, **33.2%** vs weekly-naive.
Weekly-naive was the better baseline on validation (13.93 vs 15.07); persistence
was better on test. The learned model was selected on validation MAE (10.87).
Report both baselines; do not imply persistence was selected on validation.

## Three-minute demo script

The first screen carries the whole argument before any tab is opened: the big
**Model MAE 10.83**, three like-for-like MAE bars, and four numbered takeaways —
**1 Result**, **2 Against baselines**, **3 Failure mode**, **4 Limitation**. Three
tabs sit underneath: **📈 Forecast**, **🔍 Where does the model fail?**, **📋 Method
& evidence**. RMSE, WAPE, bias and the full table are one expander down.

1. **0:00–0:30 — first screen, no clicks.** Show the historical-replay label, then
   the MAE bars: model 10.83, persistence 14.29, previous week 16.22. Say "lower is
   better", define the unit, mention the 13,440 identical rows. The four takeaways
   already state the result, the comparison, the failure mode and the limitation.
2. **0:30–1:00 — open the metric expander.** The three-method table on identical
   rows; WAPE as a percentage. Read the right-hand notes: the model loses on bias
   (+1.96 versus persistence +0.01), and previous-week — not persistence — was the
   better *validation* baseline.
3. **1:00–1:40 — 📈 Forecast tab.** It opens on Penn Station/Madison Sq West,
   2025-02-17 — the day whose previous-week reference is furthest out of step; the
   app says so on screen. Toggle "Show baselines" off and on. The three numbers
   under the chart are this zone and day only; do not quote full-period MAE as this
   day's score.
4. **1:40–2:20 — 🔍 Where does the model fail? tab.** The two-row comparison table
   puts 17 Feb (gap −13.45, bias +5.16) beside 24 Feb (gap +5.16, bias −1.29); the
   chart under it shows the two series mirroring each other. Naming 17 February
   Presidents' Day is a calendar label, not a mechanism. Explain association, no
   ablation, fresh test required. The day-by-day and per-zone tables are expanders.
5. **2:20–3:00 — 📋 Method & evidence tab.** Splits, target, model and baselines are
   visible; the standing caveats sit under them. Mention completed trips, the
   zero-latency assumption and the absence of a causal fleet outcome. Protocol,
   provenance, hashes, full metrics and downloads are in expanders. The volume
   ranking and time slider in the Forecast tab are optional; not dispatch advice.

## Error / failure story

The model has positive aggregate bias in all 20 zones. Across the two holdout
weeks, mean observed counts are similar (73.40 and 74.24), while model bias falls
from +3.02 to +0.90. A difference in weekly average activity alone does not account
for this pattern; it does not rule out every kind of distribution or level shift.

Across 14 days, correlate daily mean **observed minus previous-week observed**
with daily mean **model prediction minus observed**: **r = −0.91734**.
The saved weekly-naive prediction is exactly the previous-week count, checked
against the local panel for every forecast row.

| Date | Observed | Previous week | Gap | Model bias |
|---|---:|---:|---:|---:|
| 2025-02-17 | 52.24 | 65.69 | −13.45 | +5.16 |
| 2025-02-24 | 57.40 | 52.24 | +5.16 | −1.29 |

These are daily averages across **all 20 zones**, not Penn Station alone.
This sign reversal is consistent with stale weekly seasonality. It does not prove
that `lag_336` caused the model errors, or that a holiday caused the pattern.
Both correlated quantities contain the same observed value with opposite signs:
mathematical coupling is another reason correlation is insufficient. There are
only 14 daily points, temporal dependence, and no lag ablation or external event data.
Do not say “the lag explains 84% of the error.”

A defensible follow-up would compare a lag ablation or irregular-day feature on
new chronological development windows, freeze the choice, then evaluate on a
separate untouched period. No such experiment has been run. The existing holdout
is now diagnostic material and cannot be a clean test for a diagnosis-driven fix.

Secondary example: Penn Station has the highest model MAE (18.12) and WAPE (21.64%)
in this sample. Lenox Hill West has the lowest MAE (7.43); Midtown Center has the
lowest WAPE (11.47%) despite MAE 13.51. Scale changes the rankings. Transport-hub
surges are a plausible hypothesis, not an established explanation; the model still
beats both baselines at Penn Station.

## Likely technical questions — concise answers

| Question | Defensible answer |
|---|---|
| What exactly is predicted? | Count of observed pickups in [t, t+30 minutes), per selected zone. At 10:00, predict 10:00–10:30 using bins ending at or before 10:00. |
| Why 30 minutes? | A manageable, operationally motivated case-study resolution. I did not establish an optimal operational horizon or compare horizons. |
| Why these zones? | Top 20 Manhattan zones by January volume only, ties by zone ID. This limits generalisation to lower-volume zones. |
| How did you build the data? | Project pickup time and zone from official Parquet; validate month and zone; aggregate with DuckDB; complete the zone/time grid. Citywide coverage checks precede zero filling. |
| Why retain duplicate-looking records? | The reduced data has no unique trip ID; legitimate pickups can share a time and zone. |
| How much training data? | Jan 8–31: 24 days and 23,040 rows after seven-day lag warmup. Validation Feb 1–14: 13,440 rows. Refit on all 36,480 pre-test feature rows. |
| What prevents leakage? | Within-zone shifts, shifted rolling means, chronological partitions, January-only zone selection, and no random internal early-stopping split. |
| Can test observations become features? | Yes, only at later forecast origins, with fixed weights and the explicit immediate-availability assumption. This is rolling one-step evaluation, not a simultaneous fortnight forecast. |
| Why boosting and Poisson loss? | A compact nonlinear model for nonnegative counts. Ten features, 120 iterations, up to 15 leaves, learning rate 0.08, L2 1, seed 42. No tuning search; no claim neural networks or ARIMA were beaten. |
| Are counts proven Poisson? | No. Poisson is the fitting loss; it does not establish the full data distribution or give calibrated prediction intervals. |
| Why MAE rather than only RMSE? | MAE has direct count units and was the selection metric; RMSE highlights larger misses. Report both plus WAPE and signed bias. |
| How can MAE improve while bias worsens? | MAE measures absolute error; bias permits positive and negative errors to cancel. Nearly zero bias does not mean accurate predictions. Persistence errors also telescope over contiguous time intervals, so small aggregate bias is a weak accuracy claim. |
| Is the improvement significant? | It is measured on one two-week holdout. No confidence interval or significance test was run; 13,440 zone-bins are not independent samples. |
| How would you deploy? | First measure telemetry delay and establish as-of data availability; validate on new periods; forecast each half-hour with monitoring and a baseline fallback. Training cadence must be justified separately. |
| How does this connect to positioning? | Forecasts are one possible input. A positioning policy also needs supply, travel times, costs and a separate operational evaluation. |

## Limitations / anything not to claim

- Observed completed trips are not total or unmet demand; supply affects observations.
- No vehicle availability, rejected requests, revenue or travel-cost data.
- Immediate previous-bin availability is assumed, not demonstrated by retrospective TLC files.
- One city, two winter months, 20 high-volume Manhattan zones; no London transfer proof.
- Naive NYC local timestamps are used for Jan–Feb, with no DST transition in scope.
- Citywide coverage checks cannot prove complete reporting in each zone.
- No causal holiday/lag result, no ablation, no calibrated intervals, no operational A/B test.
- No current untouched test for a change motivated by this diagnosis.
- No RL, dispatch system, digital twin, live feed, proprietary model or commissioned work.

**Open question for fleet operators:** “How do you separate forecast quality from the effect of
vehicle supply and driver behaviour when evaluating positioning recommendations?”

See `docs/TEST_STATUS.md` and `REVIEW.md` for exact verification and remaining warnings.
