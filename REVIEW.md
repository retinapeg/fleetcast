# FleetCast interview-readiness review — 15 September 2026

## Outcome and scope

**Ready for the local interview demonstration. No blocking issue found in the
exercised path.** Reviewed checkout: local clone of
origin `https://github.com/retinapeg/fleetcast-odysse.git`, branch `main`, base HEAD
`a872130d5fbef86869a3085d0418283722c750ae`. The tree was clean before changes.
No commit or push was made. No Institutional Coding / Workbench files were touched;
no /hackathon or external agent session was invoked.

## Findings and minimal fixes

| Severity | Evidence / finding | Resolution |
|---|---|---|
| P2, fixed | Original app hid baseline scores in an expander; full MAE unit truncated at 1280px | Visible table and improvement caption (`app.py:33`, `app.py:37`); unit on separate line; screenshot inspected |
| P2, fixed | Original runbook conflated all-zone daily bias with selected-zone plots | Selected-zone caption (`app.py:53`) and explicitly all-zone failure section (`app.py:57`) |
| P2, fixed | Interview prose overstated level-shift rejection and lag causality; duplicated handoff claimed eight training days, 15 features and feature importances | Current `docs/INTERVIEW_NOTES.md` states 24 days, ten features, association and no ablation; conflicting duplicate Q&A removed |
| P2, fixed | Empty-state test skipped whenever real evidence existed; populated test never changed selectors | Isolated temporary app test (`tests/test_app.py:7`); actual selector reruns and measured bias checks (`tests/test_app.py:39`) |
| P3, remains | Vega initialization/scale warnings in browser console | No console errors; line/bar charts render. Logs retained; no dependency or renderer detour |
| P3, remains | NumPy timedelta deprecation (`tests/test_fleetcast.py:85`) | Existing passing test; warning recorded, unchanged |

## Science and evidence checks

Source review covered `fleetcast/data.py`, `fleetcast/features.py` and
`fleetcast/model.py`: January-only zone selection, complete-grid coverage guard,
within-zone shifted lags/rolling means, fixed chronological windows, categorical
zone encoding, disabled random early stopping, and validation-MAE selection.
This verifies the implemented protocol; it is not external proof of data completeness
or contemporaneous proof of every historical modelling decision.

Independent standard-library checker:

```bash
.venv/bin/python artifacts/demo-readiness/verify_evidence.py
```

It checks local raw-file sizes/hashes against metadata, the panel hash, every
saved target and both baseline lag values against the panel, date bounds,
13,440 unique zone/time rows and 960 rows per day. All twelve MAE/RMSE/WAPE/bias
values agree with metrics.json within absolute tolerance 1e-9.

| Method | MAE | RMSE | WAPE (ratio) | Bias |
|---|---:|---:|---:|---:|
| Persistence | 14.2913690476 | 22.1895580870 | 0.1935965070 | +0.0098214286 |
| Weekly-naive | 16.2206845238 | 26.0272693535 | 0.2197317733 | +2.2940476190 |
| Boosted trees | 10.8303871469 | 16.5011156753 | 0.1467126847 | +1.9598206369 |

Daily correlation independently recomputed: −0.9173395083482511.
Prediction CSV decompressed SHA-256:
`fca9f9da6da5aff8804b095a25db114ca46023d2f836613ea6b4a1e85719b644`.
All 18 original pipeline/data/first-run files match their pre-edit hashes.
No prepare, download, real-data fit or benchmark reproduction was run in this pass.

## Tests and real browser checks

```bash
.venv/bin/python -m pytest -q
# 29 passed, 0 skipped, 1 existing warning; final run 4.45 s

.venv/bin/streamlit run app.py --server.port 8599 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

The full suite includes its existing synthetic-fixture benchmark fit; it does not
retrain the frozen real-data model. An initial added AppTest chart assertion used
the wrong element name; it was corrected from arrow_vega_lite_chart to vega_lite_chart.

Actual headless Chromium interaction through rote/Playwright verified:

- Headline MAE/WAPE and visible three-method baseline table.
- Zone changes: Clinton East, Lenox Hill West, Penn Station/Madison Sq West.
- Dates 2025-02-17 and 2025-02-24, fresh captions and plots after changes.
- All-zone daily bias +5.16 and −1.29 respectively; Penn Station alone has
  +0.71 and +5.92 respectively. These must not be conflated.
- Four plotted forecast/observed series; both line and volume bar charts present.
- Time slider moves from midnight to 00:30; evidence expander exposes zone/day
  tables and protocol. No download-button interaction claim.
- Zero console errors in observed sessions; Vega warnings recorded, not suppressed.
- Final label-only MAE-unit change checked after reload in browser snapshot and
  screenshot. Earlier selector checks plus final AppTest reruns cover selectors;
  a redundant final browser replay returned an uninformative tool response and
  is not counted as additional verification.
- `/healthz` and `/` returned 200. Ctrl-C produced exit 0; port 8599 then refused
  connection (socket result 61). Owned browser session was closed.

Local captures: `artifacts/demo-readiness/headline.png`, `feb17.png`,
`feb24-failure.png`, `browser-logs/`, `independent-verification.json` and
`original-file-hashes.json`. These remain ignored local artifacts.
Rote workspace `fleetcast-demo-20260915` contains the original browser receipts
(e.g. @24 zone change, @33 Feb 17, @45 Feb 24, @51 slider/expander, @65 final headline).

## Important nonblocking scientific limits

Completed trips omit unmet demand. Immediate previous-bin availability is assumed.
The data covers only two winter months and selected Manhattan zones. There is no
causal fleet benefit, deployment-latency study, significance interval or lag ablation.
The daily gap and bias share the observed count with opposite signs; their correlation
is not an independent causal decomposition. The holdout is exposed by diagnosis.
A diagnosis-driven model change requires fresh development and test periods.

## Interview handoff

Use `docs/INTERVIEW_NOTES.md` for the 60–90 second story and three-minute demo.
Explain the target interval, 24-day initial training window, validation-selected
model, fixed test weights with observed past bins, both baseline comparisons,
positive bias and the need for fresh data to test a fix. Stop at those claims.
