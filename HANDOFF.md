# FleetCast — Build and Evaluation Handoff

**Date:** 13 September 2026; independently re-verified 15 September 2026
**Status:** Real-data benchmark complete and verified end to end. Metrics recomputed from
the saved predictions by a standalone stdlib script; a fresh `prepare` + `run` reproduces
the benchmark bit-for-bit; dashboard boots clean. The holdout positive bias is now
characterised as associated with weekly-lag staleness; no causal ablation was run. See `docs/TEST_STATUS.md`.

---

## Current interview launch (15 September 2026)

```bash
cd fleetcast-odysse
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8599 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8599. Ctrl-C stops the server. Read the current project story,
demo script and technical answers in `docs/INTERVIEW_NOTES.md`.
No sync, download, prepare or training is needed. Frozen evidence remains in
`artifacts/first-run/`. `REVIEW.md` records the current independent checks.

The sections below preserve the original build evidence; current verification
supersedes the earlier test count and headless-only dashboard status.

## Test Results

**Environment:** macOS (Darwin 25.5.0, Apple Silicon), Python 3.12.14, numpy 2.5.3, pandas 2.3.3, scikit-learn 1.9.1, duckdb 1.5.5, streamlit 1.63.0

### Unit & integration tests (29 total)
```
28 passed, 1 skipped, 1 warning
```

The one skip is expected and is **not** a dependency skip. `tests/test_app.py` holds two mutually exclusive dashboard tests: `test_app_empty_state` runs only when no benchmark exists, and `test_app_populated_state` runs only when one does. Exactly one applies at any time. With artifacts present, the populated test runs and the empty-state test skips with the reason `"Real benchmark exists; verify the populated app separately"`.

`test_app_populated_state` was added during this build: the repository previously had no automated coverage of the dashboard's populated path at all — it only tested the empty state and then skipped once real artifacts appeared. The new test asserts the app renders without exception or error, that the zone selector has 20 options and the day selector 14, that all three error tables render, and that the headline metric equals the measured MAE from `metrics.json` rather than a hard-coded value.

**Combined test and manual-verification coverage (not all unit-tested):**
- Data download and hash validation (SHA-256 checks)
- Parquet schema projection and date/zone filtering
- Complete zone × timestamp grid creation (zero-filling)
- Leakage validation: lag features use only past-observed bins
- Rolling window features constructed with past-only data
- Chronological split integrity (training < validation < test)
- Synthetic benchmark execution and separately recorded real-data reproduction
- Baseline calculations (persistence, weekly naive)
- Aggregation correctness and metric calculations

**Note:** One `DeprecationWarning` raised from `tests/test_fleetcast.py:85` (bare-integer NumPy timedelta arithmetic). Non-blocking and not suppressed; the test passes. Worth a one-line fix if the suite is rerun under a future NumPy.

**Dependency skips:** none. The DuckDB and Streamlit integration tests that were skipped in the authoring environment do execute here now that project dependencies are installed. The only remaining skip is the mutually exclusive empty-state dashboard test described above.

---

## Data

### Sources
All three files downloaded from `d37ci6vzurychx.cloudfront.net` and hashed at ingestion. Byte counts and SHA-256 digests are recorded in `artifacts/first-run/metadata.json` under `data_provenance.sources`.

| File | Bytes | SHA-256 (prefix) |
|---|---:|---|
| yellow_tripdata_2025-01.parquet | 59,158,238 | `9af277e4c0d3f9de…` |
| yellow_tripdata_2025-02.parquet | 60,343,086 | `037cba555a73663f…` |
| taxi_zone_lookup.csv | 12,331 | `1a99e105092230f8…` |

### Ingestion counts (measured, from `data_provenance.quality`)
- Raw trip rows read: **7,052,769**
- Rows with valid pickup time and known NYC zone: **7,034,560**
- Rows excluded: **18,209** (null/unparseable pickup time, wrong source month, or unknown/non-NYC zone)
- Pickups retained after top-20 Manhattan zone selection: **4,088,332**
- Panel rows emitted: **56,640** (20 zones × 2,832 half-hour bins)

Zone selection rule: top 20 Manhattan zones by January 2025 pickup count, ties broken by zone ID — computed on January only, never on validation or test data. Selected IDs: 48, 68, 79, 107, 140, 141, 142, 161, 162, 163, 164, 170, 186, 230, 234, 236, 237, 238, 239, 249.

Duplicate policy: identical pickup rows are **retained**. The reduced view has no unique trip ID, so coinciding pickups in the same zone and minute are not proof of duplication.

### Prepared dataset
**Path:** `data/processed/panel.csv.gz`
**Size:** 56,640 rows × 3 columns — `zone_id`, `timestamp`, `pickups`
**Structure:** Complete zone × 30-minute time panel. The panel stores only observed counts; all lag, rolling and calendar features are derived in memory by `fleetcast/features.py` at train/predict time, so no leaked or precomputed feature is persisted to disk.

| Column | Type | Notes |
|---|---|---|
| timestamp | datetime | NYC local naive time, 30-min buckets, 1 Jan – 28 Feb 2025 |
| zone_id | int | LocationID; 20 top-volume Manhattan zones selected on January only |
| pickups | int | Observed trip count in [t, t+30m); zero-filled for missing buckets |

The ten model features (`fleetcast/features.py:FEATURES`) are exactly:

| Feature | Notes |
|---|---|
| zone_code | Zone identity, passed as a categorical feature |
| slot | Half-hour slot of day (0–47), not raw hour |
| day_of_week | 0=Mon, 6=Sun |
| weekend | 1 if Sat or Sun, else 0 |
| lag_1 | Pickups at t−30m (past-only) |
| lag_2 | Pickups at t−60m |
| lag_48 | Pickups at same half-hour, previous day |
| lag_336 | Pickups at same half-hour, previous week (7 × 48) |
| rolling_4 | Shifted mean of past 4 bins = past 2 hours |
| rolling_48 | Shifted mean of past 48 bins = past 24 hours |

There is no `lag_3` and no `rolling_12`; the implemented set is the four lags in `LAGS = (1, 2, 48, 336)` plus two shifted rolling means. All lags and rolling means are within-zone and end at or before t.

### Data assumptions & limitations
- **Zero-filling:** Missing zone × time buckets interpreted as zero pickups after validation that each zone appears in both Jan and Feb.
- **Latency:** Features assume previous bin's pickup count is available at forecast time t (zero-ingestion-latency assumption). Real deployment must measure telemetry delay.
- **Timezone:** All times converted to NYC local (UTC−5 in Jan–Feb, no DST transition).
- **Scope:** Top 20 Manhattan zones by January activity. Excludes outer boroughs, low-volume zones, and seasonal patterns outside Jan–Feb.
- **Combined test and manual-verification coverage (not all unit-tested):** Completed trips only. Missing: rejected requests, unmet demand, passenger waits, vehicle availability, supply repositioning.

---

## Splits & Experiment Protocol

| Stage | Dates | Zones | Rows | Purpose |
|---|---|---|---|---|
| **Lag warmup** | 1–7 Jan | 20 | — | Discarded; 336-bin lag not yet available |
| **Training** | 8–31 Jan | 20 | 23,040 | Fit model (first feature timestamp 2025-01-08 00:00) |
| **Validation** | 1–14 Feb | 20 | 13,440 | Select model; choose baseline |
| **Test (holdout)** | 15–28 Feb | 20 | 13,440 | Evaluate fixed recipe, no tuning |

**Key protocol elements:**
- Chronological: no random shuffling; contiguous time windows.
- Rolling one-step-ahead: during test, model weights frozen; earlier test bins available as history for later forecasts (realistic replay).
- Fixed recipe: recipe fixed before evaluation; model selected on validation; not refitted to test results.
- Identical rows: all baseline and model scores computed on the same 13,440 prediction rows.

---

## Model & Baselines

### Baselines
1. **Persistence:** y_hat(t) = y(t−1)  
   Cheap, interpretable, represents "no change from last 30 min."

2. **Weekly naive:** y_hat(t) = y(t−336)  
   Captures 7-day seasonal pattern; weekly shops, commute cycles.

### Model: HistGradientBoostingRegressor (Poisson)
**Selected on:** Validation MAE performance.

**Configuration** (`fleetcast/model.py:new_model`, mirrored in `metadata.json:protocol.model_recipe`):
- Loss: `poisson` (nonnegative count target)
- max_iter: 120
- max_leaf_nodes: 15
- learning_rate: 0.08
- l2_regularization: 1.0
- early_stopping: `False` — no random internal validation split
- random_state: 42
- `zone_code` declared as a categorical feature
- Predictions clipped at 0 via `np.maximum(..., 0)`

The recipe is fixed in code before test evaluation and refitted on all pre-test data. No hyperparameter search was run at any point.

**Why this model:**
- Gradient boosting handles nonlinear lag/rolling/categorical interactions without explicit feature engineering.
- Poisson loss is appropriate for count-valued targets (pickups per zone per 30 min).
- No random splits; reproducible from code alone (no pkl needed).
- 23,040 initial training rows and ten features; no feature-importance analysis was run.

**What this model is not:**
- No neural-network comparison was run; do not claim a result against one.
- Not XGBoost/LightGBM (scikit-learn Poisson sufficient; no GPU needed).
- Time-series forecasting via lagged tabular features; no ARIMA, Prophet or state-space comparison.
- Not calibrated: Poisson loss does not produce valid prediction intervals.

---

## Results — Chronological Test Holdout (15–28 Feb 2025)

### Aggregate scores
```
Method           MAE     RMSE    WAPE    Bias      Rows
─────────────────────────────────────────────────────────
persistence     14.29   22.19   19.4%   +0.01    13,440
weekly_naive    16.22   26.03   22.0%   +2.29    13,440
boosted_trees   10.83   16.50   14.7%   +1.96    13,440
```

**Key finding:** Boosted trees achieves **24% MAE reduction** over persistence and **33% over weekly_naive**, on the same 13,440 rows.

**Independently verified:** these four metrics were recomputed for all three methods directly from `predictions.csv.gz` and match `REPORT.md` / `metrics.json` to four decimal places. The headline numbers are derived from the stored outputs, not hard-coded.

**Baseline ranking is not stable:** weekly_naive was the stronger baseline on validation (13.93 vs persistence 15.07) but the weaker one on test (16.22 vs 14.29). The model beats both in both periods, but this instability is a caution against reporting improvement against a single baseline.

**Metric definitions:**
- **MAE:** Mean absolute error in pickups per zone per 30-minute bucket.
- **RMSE:** Root mean squared error; penalizes large misses.
- **WAPE:** Weighted absolute percentage error = sum(|pred − actual|) / sum(actual). Undefined (null) when actual=0.
- **Bias:** Mean(predicted − observed). Positive = systematic overprediction.

### By-zone breakdown
**Best performing zones (lowest MAE):**
- Lenox Hill West: MAE 7.43
- Lenox Hill East: MAE 7.51
- Upper West Side North: MAE 8.01

**Worst performing zones (highest MAE):**
- Penn Station/Madison Sq West: MAE 18.12 (model underpredicts volatile commuter hub)
- Times Sq/Theatre District: MAE 14.08 (cause not established)
- Midtown Center: MAE 13.51

**Interpretation:** Read MAE and WAPE together, not MAE alone. Penn Station is worst on both (MAE 18.1, WAPE 21.6%), so it has worse absolute and volume-normalised errors in this sample. Transport-hub surges are a hypothesis, not a measured cause. Midtown Center has high MAE (13.5) but the *best* WAPE in the panel (11.5%), illustrating how volume normalisation changes rankings, without identifying the cause. Ranking zones by MAE alone would conflate those two very different cases.

**Systematic overprediction:** the model's bias is positive in all 20 zones (range +0.72 to +4.09, overall +1.96), against persistence's near-zero +0.01. This is the most notable open issue in the result and is discussed under Limitations.

### By-day breakdown
Model MAE across the 14 test days ranges 9.21 – 12.83 (mean 10.83). First seven days average 11.35, last seven 10.31, so there is no degradation as the holdout progresses. Worst days are 15 Feb (12.83), 21 Feb (12.17) and 22 Feb (12.13); 15 Feb is the first test day and 21–22 Feb is a Fri/Sat pair, so the weekend and cold-start slices are worth inspecting before drawing conclusions.

### Full results files
- `artifacts/first-run/metrics.json` — validation and test scores (JSON)
- `artifacts/first-run/predictions.csv.gz` — all 13,440 test predictions + observed pickups
- `artifacts/first-run/by_zone.csv` — MAE/RMSE/WAPE/Bias per zone (20 rows × 3 models)
- `artifacts/first-run/by_day.csv` — MAE/RMSE per day (14 rows × 3 models)
- `artifacts/first-run/zones.csv` — zone ID, name, Borough
- `artifacts/first-run/metadata.json` — protocol, data provenance, feature list

---

## Failure pattern — association with weekly-lag staleness

The frozen predictions give model bias +1.96 versus persistence +0.01. In the first
holdout week (15–21 Feb), observed mean is 73.40 and model bias +3.02. In the second
(22–28 Feb), observed mean is 74.24 and bias +0.90. Similar weekly means do not
support a simple weekly-average explanation of the bias difference; they do not
rule out all distribution shifts or a difference from January.

Daily mean observed-minus-weekly-lag correlates with model daily bias at
r = −0.91734 across 14 days. On 17 Feb, observed = 52.24, weekly lag = 65.69,
model bias = +5.16. On 24 Feb, observed = 57.40, weekly lag = 52.24,
model bias = −1.29. These are all-zone daily averages.

This is a post-hoc association, not proof that the lag or a holiday caused the
errors. The two quantities share observed counts with opposite signs, there are
only 14 temporally dependent daily observations, and no ablation was run.
No claim that the lag “explains 84%” is justified. Diagnosis-driven changes need
new development data and a separate untouched test period. The original scores
and predictions remain unchanged. See `docs/INTERVIEW_NOTES.md` for the demo.

## Dashboard

**Path:** `app.py`  
**Command:** `uv run streamlit run app.py`

### Features
1. **Metric cards:** Model name, holdout MAE, holdout WAPE
2. **Zone selector:** Dropdown of 20 Manhattan zones
3. **Day selector:** Holdout period dates (15–28 Feb)
4. **Line chart:** Observed pickups vs boosted_trees, persistence, weekly_naive for selected zone/day
5. **Time-slider:** Select forecast origin to view predicted ranking of zones by demand
6. **Bar chart:** Top zones by model prediction at selected time
7. **Expandable sections:**
   - Baseline comparison table (all 3 methods, all metrics)
   - Zone-level error table (importances: which zones break down)
   - Daily error table (temporal stability check)
   - Download button: predictions.csv.gz for external analysis
   - Protocol summary (JSON: splits, features, model config)
   - Honest disclaimers (completed trips ≠ demand, no revenue claims, no supply data)

### Original smoke test — historical record
Run headless on port 8599:
- Server boots cleanly; `/healthz` and `/` both return HTTP 200; no errors or tracebacks in the startup log.
- Every data path the page uses was exercised directly in Python: all six required artifact files present, `data_is_synthetic` is `False`, selected model resolves to `boosted_trees` (MAE 10.83), zone selector has 20 options, day selector has 14, the line chart returns 48 rows for a zone/day with all four series present, the ranking bar chart returns 20 named zones with no unmapped names, and the download payload is 238,363 bytes.
- The server was stopped afterwards; no Streamlit processes are left running.

**At that earlier check:** the page was not driven through a browser, so visual layout, actual widget interaction, and the missing-artifacts empty state were not exercised as a user would. The empty state is a straightforward file-existence branch, but was untested at that point. Current browser and isolated empty-state checks are in `docs/TEST_STATUS.md`.

### Safety & honesty features
- Checks for real-data results (metadata.data_is_synthetic=false); halts if synthetic.
- Displays required commands if no benchmark yet (no illustrative scores substituted).
- Disables live training; read-only replay only.
- Explicit caveat: "This is not a dispatch system or Odysse fleet data."

---

## Component Status: implemented / tested / untested / blocked

| Component | Status | Evidence |
|---|---|---|
| Dependency install + lockfile | Implemented, tested | `uv sync`; 47 packages; `uv.lock` written |
| TLC download + SHA-256 hashing | Implemented, tested | 3 files, byte counts and digests in `metadata.json` |
| DuckDB aggregation + zone/time panel | Implemented, tested | 56,640 rows; covered by suite |
| Leakage-safe features | Implemented, tested | `test_lags_and_rolling_are_past_only` passes |
| Chronological split | Implemented, tested | Split boundaries asserted in suite and `metadata.json` |
| Baselines (persistence, weekly_naive) | Implemented, tested | Scored on identical 13,440 rows |
| Poisson boosted-tree model | Implemented, tested | Fixed recipe; reproducible from code, seed 42 |
| Holdout evaluation + metrics | Implemented, **independently verified** | MAE/RMSE/WAPE/bias recomputed from `predictions.csv.gz`, matched REPORT.md exactly |
| Streamlit dashboard | Implemented, tested | Boots (HTTP 200); `test_app_populated_state` asserts selectors, tables and headline metric; browser-driven in the current readiness pass; see `docs/TEST_STATUS.md` |
| Dashboard empty state | Tested in isolated AppTest copy | Runs alongside populated state; no missing-artifact skip now |
| Positive-bias explanation | **Characterised, not causally proven** | Strongly associated with weekly-lag staleness; r=-0.917 across 14 test days, no ablation |
| Ingestion latency sensitivity | **Not attempted** | Out of scope; zero-latency assumed |

**Blocked:** nothing. No download failures, no dependency conflicts, no hook or permission blockers. Graphify was not used — `graphify-out/graph.json` does not exist in this project, and the build prompt says not to take a tooling detour to create it, so source was read directly.

## Implementation Checklist

### ✓ Completed
- [x] Environment reproduction (uv sync, .python-version, uv.lock)
- [x] Real-data ingestion (official TLC Parquet, SHA-256 validation)
- [x] Schema validation and filtering (valid timestamps, zone IDs, locations)
- [x] Complete zone × time grid (zero-filled)
- [x] Leakage-safe feature engineering (lag, rolling, calendar features all past-only)
- [x] Chronological train/val/test split (contiguous windows, no random shuffle)
- [x] Baseline implementations (persistence, weekly_naive)
- [x] Model training with Poisson loss (HistGradientBoostingRegressor)
- [x] Validation-based model selection (no test peeping)
- [x] Refit on pre-test data (fixed recipe before holdout)
- [x] Chronological holdout evaluation (one-step-ahead rolling replay)
- [x] Metric computation (MAE, RMSE, WAPE, Bias) by zone and by day
- [x] Streamlit dashboard (read-only, real-data checks, honest disclaimers)
- [x] Unit tests (29 total; 28 pass, 1 expected skip) covering data quality, leakage, split integrity, baselines and reproducibility
- [x] New test added for the dashboard's populated path (previously uncovered)
- [x] REPORT.md with interpreted findings
- [x] INTERVIEW_NOTES.md with measured results

### ✗ Explicitly out of scope (not attempted, as specified)
- [ ] Reinforcement learning, vehicle relocation, dispatch optimization
- [ ] Real-time ingestion or live system deployment
- [ ] LLM features, embeddings, external APIs, synthetic data
- [ ] Hyperparameter grid search or AutoML
- [ ] Causal inference or counterfactual analysis
- [ ] Prediction intervals or Bayesian posterior
- [ ] Multi-step-ahead forecasts
- [ ] Non-NYC data or years beyond Jan–Feb 2025
- [ ] Authentication, cloud databases, Kubernetes

---

## Interview narrative, limitations and next steps

Use `docs/INTERVIEW_NOTES.md` as the single current interview script. It replaces
the earlier duplicated Q&A, including incorrect claims about eight training days,
feature importances, proved surge mechanisms, neural-network overfitting and
hourly/daily prediction sufficiency. Training covers **24 days**, with **10 features**.
No comparisons with neural networks/ARIMA, latency study or causal ablation were run.

The clean-start reproduction described in `docs/TEST_STATUS.md` is historical
evidence. Do not delete the environment or processed data, run preparation, or
retrain for tomorrow's demonstration. Frozen first-run artifacts are sufficient.

## Key Files

| File | Purpose |
|---|---|
| `pyproject.toml` | Dependencies, Python version |
| `fleetcast/__main__.py` | Entry point for `prepare` and `run` commands |
| `fleetcast/data.py` | Download, validate, load TLC Parquet; complete grid |
| `fleetcast/features.py` | Lag, rolling, calendar feature construction |
| `fleetcast/model.py` | Baselines, HistGradientBoostingRegressor, evaluation |
| `tests/test_fleetcast.py` | 28 unit + integration tests (leakage, schema, reproducibility) |
| `app.py` | Streamlit dashboard (read-only historical replay) |
| `docs/INTERVIEW_NOTES.md` | Explanation, 8 talking points, limitations |
| `artifacts/first-run/REPORT.md` | Measured benchmark results |
| `artifacts/first-run/metrics.json` | Validation and test scores (JSON) |
| `artifacts/first-run/predictions.csv.gz` | Full holdout predictions and observed |

---

**End of handoff. Ready for review, deployment testing, or interview.**
