# FleetCast — interview demo card

One screen. Full detail in `INTERVIEW_NOTES.md`.

## Launch

```bash
cd /Users/leonardaarons-ditson/Code/fleetcast-odysse
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

1. **Results tab.** Headline cards, then the three-method table on identical rows.
   Say the unit out loud. Note the model loses on bias — read the right-hand column.
2. **Forecast replay tab.** Opens on 2025-02-17 (derived: stalest weekly reference).
   Change zone → Penn Station/Madison Sq West. Toggle "Show baselines" off, then on.
   The three numbers under the chart are *this zone and day only*.
3. **Where it fails tab.** All-zone daily bias +5.16 on 17 Feb. Switch the day
   selector to 2025-02-24 → flips to −1.29. The gap/bias chart shows the mirror.
4. **Evidence & limits tab.** Protocol, per-day errors, prediction download.

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
