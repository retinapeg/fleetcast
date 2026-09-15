# Verification status

**Verified 15 September 2026 on the target Mac** (Darwin 25.5.0, Apple Silicon),
Python 3.12.14, numpy 2.5.3, pandas 2.3.3, scikit-learn 1.9.1, duckdb 1.5.5,
streamlit 1.63.0. Every command below was executed in this environment and the
output recorded as shown. This file supersedes the earlier authoring-environment
status, which predated any real-data run.

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

## What is still not verified

The dashboard was exercised headless and through its data paths, but not driven
through a browser, so visual layout and real widget interaction remain unverified.
The empty-state branch cannot run while a benchmark exists.
