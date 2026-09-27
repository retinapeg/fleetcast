# FleetCast

Can a small model forecast NYC taxi pickups 30 minutes ahead better than assuming the next half-hour looks like the last one?

**Result:** Yes: on a held-out fortnight (13,440 predictions), Poisson boosted trees reached MAE 10.83 against 14.29 for persistence, a 24% reduction.

**Status:** Completed experiment on public TLC data, verified end to end on 15 September 2026.

- Counts pickups per half-hour in 20 Manhattan zones, trains on past-only features and scores once on a chronological holdout.
- The pipeline reproduces bit for bit from the public source, and tests cover leakage.
- Completed trips are not total demand, and the model overpredicts (bias +1.96). Lower error does not show shorter waits.

[Technical details →](docs/GUIDE.md)
