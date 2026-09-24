# Current verification status — 15 September 2026

## Superseding note — presentation rebuild, 15 September 2026 (later the same day)

`app.py` was rebuilt into a four-tab layout (Results / Forecast replay / Where it
fails / Evidence & limits) with cached artifact loads, formatted number columns, a
baselines toggle and a gap-vs-bias chart. `.streamlit/config.toml` (presentation
only) and `demo.sh` were added. No pipeline, data, model or saved artifact changed.

What was verified in that pass, and what was not:

| Check | Command / action | Result |
|---|---|---|
| Full suite | `.venv/bin/python -m pytest -q` | **29 passed, 1 existing warning** |
| Rendered page | Cached headless-shell over CDP, all four tabs screenshotted | No exception; headline, tables, charts and caveats render |
| Launcher startup | `./demo.sh` with `open` shadowed by a stub | Pre-flight passed, `/healthz` and `/` both 200, browser-open invoked with the right URL |
| Launcher Ctrl-C | — | **NOT verified.** Only background startup was exercised; the interactive SIGINT/trap path is untested |
| Busy-port branch | — | **NOT verified.** The prompt-and-kill path in `demo.sh` was never exercised |

The browser-verification row in the table below predates this rebuild and describes
the earlier single-page layout ("evidence expander"). It remains as a dated historical
record; it is **not** a description of the current file.


**PASS for the local demo.** Base HEAD
`a872130d5fbef86869a3085d0418283722c750ae`, branch `main`.
App presentation, tests and demo documentation changed; the pipeline, source
data and frozen predictions did not. No real-data model training or downloads ran.

## Checks executed in this readiness pass

| Check | Exact command / action | Result |
|---|---|---|
| Full suite | `.venv/bin/python -m pytest -q` | **29 passed, 0 skipped, 1 warning**, final run 4.45 s |
| Independent evidence | `.venv/bin/python artifacts/demo-readiness/verify_evidence.py` | PASS: all 12 metrics within 1e-9; 13,440 unique rows; 20 zones; all targets and baseline lags match local panel; source and panel hashes match |
| Server | `.venv/bin/streamlit run app.py --server.port 8599 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false` | Starts; `/healthz` and `/` both HTTP 200 |
| Real browser | Headless Chromium through Playwright, http://127.0.0.1:8599 | Headline, baseline table, line/bar charts, zone/day selectors and evidence expander exercised |
| Zone changes | Clinton East → Lenox Hill West → Penn Station/Madison Sq West | Captions/plots update; no app error |
| Date changes | 2025-02-17 → 2025-02-24 | All-zone daily bias +5.16 → −1.29; both dates selectable |
| Time slider | 2025-02-24 00:00 → 00:30 using keyboard | New timestamp renders; both charts remain present |
| Empty state | AppTest executes a copy of app.py in pytest temporary directory | Warning shown; frozen artifacts never moved |
| Final visual check | Browser reload after MAE unit moved beneath number | 10.83 and complete unit visible; screenshot inspected |
| Shutdown | Ctrl-C to owned Streamlit process, then socket connection check | Process exit 0; port 8599 refuses connection |
| Preservation | SHA-256 before/after comparison | All 18 original pipeline/data/first-run files unchanged |

The suite's existing benchmark test fits **synthetic test fixtures only**. The
real TLC benchmark was not rerun, retrained or optimised in this pass.
The earlier empty-state skip was removed by testing an isolated temporary copy.

## Warnings and validation limits

- Browser console: **zero errors** in the observed sessions. Vega emits warnings
  during initial rendering/reruns about infinite extents and categorical scale
  binding (11 on initial load, 52 across the first interaction session). Plots
  render with data; these warnings are not suppressed or claimed fixed.
- Existing NumPy timedelta DeprecationWarning remains at tests/test_fleetcast.py:85.
- One initial new chart assertion failed because AppTest calls this element
  `vega_lite_chart`, not `arrow_vega_lite_chart`; corrected, then suite passed.
- A browser automation wait for the changed headline timed out before explicit
  page reload. Reload and fresh snapshot verified the final label. This was not
  a Python application exception. No browser-engine changes were attempted.
- Screenshots cover headline/baselines, the 17 Feb chart, and the 24 Feb failure
  table. No claim of exhaustive browser/device coverage or download-button testing.
- Synthetic-provenance rejection and corrupted-artifact handling were not
  separately exercised. The app requires the intact frozen bundle.

Local evidence: `artifacts/demo-readiness/` contains the independent checker and
JSON result, original-file hashes, three screenshots and browser logs/snapshots.
This directory follows the existing ignored-artifact policy; it is local evidence.

## Historical full reproduction evidence

The earlier prepare/run and fresh-download verification below is retained as prior
evidence. It was **not repeated** in this readiness pass. The holdout has since been
inspected for diagnosis and is not a clean test for diagnosis-driven changes.

# Verification status

**Verified 15 September 2026 on the target Mac** (Darwin 25.5.0, Apple Silicon),
Python 3.12.14, numpy 2.5.3, pandas 2.3.3, scikit-learn 1.9.1, duckdb 1.5.5,
streamlit 1.63.0. Every command below was executed in this environment and the
output recorded as shown. This file supersedes the earlier status, which
predated any real-data run.

## What was executed

| Check | Command | Result |
|---|---|---|
| Environment | `uv sync` | exit 0 |
| Test suite | `uv run pytest -q` | **28 passed, 1 skipped, 1 warning** (42.6 s) |
| Real ingestion | `uv run python -m fleetcast prepare` | exit 0; 56,640 zone/time rows |
| Benchmark reproduction | `uv run python -m fleetcast run --output artifacts/reproduction` | exit 0 |
| Dashboard | `uv run streamlit run app.py --server.port 8599 --server.headless true` | `/healthz` 200, `/` 200, no errors, no stray process |

The single skip is expected and is not a dependency skip: `tests/test_app.py`
holds two mutually exclusive dashboard tests, and with a benchmark present the
populated-state test runs while the empty-state test skips.

## Data provenance re-confirmed against a fresh download

All three files were re-downloaded from `d37ci6vzurychx.cloudfront.net` on
15 September 2026. Byte counts matched `artifacts/first-run/metadata.json` exactly:
`yellow_tripdata_2025-01.parquet` 59,158,238 B, `yellow_tripdata_2025-02.parquet`
60,343,086 B, `taxi_zone_lookup.csv` 12,331 B.

The derived panel hash matched the digest recorded at the original run:

```
recomputed sha256(data/processed/panel.csv.gz)
  = d16915527ae14c246d23a02d16fa5186a88530c69fc93d93a669958781305fa5
recorded  metadata.json:data_provenance.panel_sha256
  = d16915527ae14c246d23a02d16fa5186a88530c69fc93d93a669958781305fa5   MATCH
```

## Reproducibility: bit-identical

`artifacts/reproduction/` was generated from scratch and compared against the
frozen `artifacts/first-run/`:

- every validation and test metric is **bitwise identical** (all three methods, all four metrics);
- `recommended_model_from_validation` is identical;
- `predictions.csv.gz` decompresses to an **identical SHA-256**
  (`fca9f9da6da5aff8804b095a25db114ca46023d2f836613ea6b4a1e85719b644`).

This confirms the claim that the fixed recipe is reproducible from code alone with
seed 42 and that no fitted artefact needs to be stored. Reproduction is **not** a
fresh holdout; the test period was scored once and not tuned against.

## Metrics independently recomputed

The four headline metrics were recomputed for all three methods directly from
`artifacts/first-run/predictions.csv.gz` using a standalone Python-standard-library
implementation (`csv` + `math` only, no pandas and no project code), so the check
shares no code path with the pipeline that produced them.

All twelve values matched `metrics.json` to within 1e-9 on all 13,440 rows:

```
persistence     MAE 14.2913690476  RMSE 22.1895580870  WAPE 0.1935965070  bias +0.0098214286
weekly_naive    MAE 16.2206845238  RMSE 26.0272693535  WAPE 0.2197317733  bias +2.2940476190
boosted_trees   MAE 10.8303871469  RMSE 16.5011156753  WAPE 0.1467126847  bias +1.9598206369
```

Derived headline figures: 24.2% MAE reduction against persistence, 33.2% against
weekly-naive, on the same 13,440 rows.

## Known non-blocking issue

One `DeprecationWarning` from `tests/test_fleetcast.py:85` (bare-integer NumPy
timedelta arithmetic). The test passes; the warning is not suppressed. It will
become an error under a future NumPy and is a one-line fix when that happens.

## Earlier browser limitation (superseded by current check above)

The dashboard was exercised headless and through its data paths, but not driven
through a browser, so visual layout and real widget interaction remain unverified.
The empty-state branch cannot run while a benchmark exists.
