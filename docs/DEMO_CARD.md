# FleetCast — demo card

One screen. Full detail in `WALKTHROUGH.md`.

## Launch

```bash
cd fleetcast
./demo.sh
```

Pre-flights the environment and the frozen artifacts, frees port 8599, opens the
browser when the server is healthy. Stop with Ctrl-C. No download, training or
preparation runs. If it refuses to start, it prints the fallback — open
`artifacts/first-run/REPORT.md` and this card. **Do not improvise scores.**

## The five numbers

| | |
|---|---|
| Model MAE (holdout) | **10.83** |
| Persistence MAE | 14.29 |
| Previous-week MAE | 16.22 |
| MAE reduction | **24.2%** vs persistence · 33.2% vs previous-week |
| Model bias | **+1.96** (persistence +0.01) |

Units: pickups per zone per 30 minutes. Holdout 15–28 Feb 2025, 13,440 predictions,
20 Manhattan zones. Weekly-gap / model-bias correlation across 14 days: **r = −0.917**.

## Click path (≈3 minutes)

The result, the baseline bars and four numbered takeaways (Result · Against
baselines · Failure mode · Limitation) are on the **first screen, before any tab**.
Three tabs sit underneath: **📈 Forecast**, **🔍 Where does the model fail?**,
**📋 Method & evidence**.

1. **First screen, no clicks.** Big MAE 10.83, then the three bars: model 10.83,
   persistence 14.29, previous week 16.22. Say "lower is better" and say the unit
   out loud. Read takeaway 3 aloud — the model overpredicts, bias +1.96.
2. **📈 Forecast tab.** Opens on Penn Station/Madison Sq West, 2025-02-17 (derived:
   stalest weekly reference). Toggle "Show baselines" off, then on. The three numbers
   under the chart are *this zone and day only*.
3. **🔍 Where does the model fail? tab.** The two-row table compares 17 Feb
   (gap −13.45, bias +5.16) with 24 Feb (gap +5.16, bias −1.29). The gap/bias chart
   shows the mirror. Day-by-day table and per-zone errors are in expanders.
4. **📋 Method & evidence tab.** Splits, target, model, baselines visible; protocol,
   provenance, hashes, full metrics and downloads in expanders.

## Say this

"At the start of each half-hour, predict observed pickups in the next half-hour
across 20 Manhattan zones. DuckDB panel, past-only lags, chronological splits:
January trains, early February selects, 15–28 February is the untouched holdout.
The model cuts MAE 24% against the stronger test baseline. The interesting part is
the failure: it overpredicts by about two pickups a bin, and that bias tracks how
stale the previous-week reference is — association, not proof, and diagnosed on the
holdout, so any fix needs a fresh test period."

## Do not claim

- That completed trips are total demand, or that lower MAE means shorter waits or more revenue.
- That the weekly lag *caused* the bias. No ablation was run. Never "explains 84% of the error."
- That the improvement is statistically significant. One holdout, no interval, no test.
- That persistence was selected on validation. Previous-week was the better *validation*
  baseline (13.93 vs 15.07); the **model** was selected on validation MAE (10.87).
- That NYC winter taxi data transfers to London ride-hailing.

## If asked how it was built

Coding agents helped implement and review it. Own the problem definition, the
assumptions, the split design and the validation. Do not claim every line was handwritten.

**Question for them:** "How do you separate forecast quality from the effect of vehicle
supply and driver behaviour when evaluating positioning recommendations?"
