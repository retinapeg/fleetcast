# FleetCast — Build and Evaluation Handoff

**Date:** 13 September 2026; independently re-verified 15 September 2026
**Status:** Real-data benchmark complete and verified end to end. Metrics recomputed from
the saved predictions by a standalone stdlib script; a fresh `prepare` + `run` reproduces
the benchmark bit-for-bit; dashboard boots clean. The holdout positive bias is now
diagnosed (weekly-lag staleness) rather than merely reported. See `docs/TEST_STATUS.md`.

---

## Quick Start — Reproduction

```bash
# Install dependencies and lock them
uv sync

# Run tests (28 pass, 1 expected skip — see Test Results)
uv run pytest -q

# Download official TLC Parquet + zone lookup and prepare zone/time panel
uv run python -m fleetcast prepare

# Train model, validate, refit, evaluate on chronological holdout
uv run python -m fleetcast run

# Launch read-only Streamlit dashboard
uv run streamlit run app.py
```

Measured on this machine: `uv sync` ~15 s on a warm cache (longer on first run, which also fetches CPython 3.12.14); `pytest -q` 37.57 s; `prepare` ~1–2 min dominated by the ~120 MB of Parquet downloads, then cached; `run` under a minute. Streamlit serves on http://localhost:8501.

---

## Test Results

**Environment:** macOS (Darwin 25.5.0, Apple Silicon), Python 3.12.14, numpy 2.5.3, pandas 2.3.3, scikit-learn 1.9.1, duckdb 1.5.5, streamlit 1.63.0

### Unit & integration tests (29 total)
```
28 passed, 1 skipped, 1 warning
```

The one skip is expected and is **not** a dependency skip. `tests/test_app.py` holds two mutually exclusive dashboard tests: `test_app_empty_state` runs only when no benchmark exists, and `test_app_populated_state` runs only when one does. Exactly one applies at any time. With artifacts present, the populated test runs and the empty-state test skips with the reason `"Real benchmark exists; verify the populated app separately"`.

`test_app_populated_state` was added during this build: the repository previously had no automated coverage of the dashboard's populated path at all — it only tested the empty state and then skipped once real artifacts appeared. The new test asserts the app renders without exception or error, that the zone selector has 20 options and the day selector 14, that all three error tables render, and that the headline metric equals the measured MAE from `metrics.json` rather than a hard-coded value.

**Coverage:**
- Data download and hash validation (SHA-256 checks)
- Parquet schema projection and date/zone filtering
- Complete zone × timestamp grid creation (zero-filling)
- Leakage validation: lag features use only past-observed bins
- Rolling window features constructed with past-only data
- Chronological split integrity (training < validation < test)
- Model serialization and reproducibility
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
- **Coverage:** Completed trips only. Missing: rejected requests, demand surges, unmet passenger waits, vehicle availability, supply repositioning.

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
- Fixed recipe: model hyperparameters and features chosen on validation; not refitted to test results.
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
- Fast training on 10k rows; explainable feature importances available.

**What this model is not:**
- Not a neural network, LSTM, or transformer (overkill for 15 features, small data).
- Not XGBoost/LightGBM (scikit-learn Poisson sufficient; no GPU needed).
- Not a time-series model (no ARIMA, Prophet, or state-space; lagged features are explicit).
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
- Times Sq/Theatre District: MAE 14.08 (events, tourist surges)
- Midtown Center: MAE 13.51

**Interpretation:** Read MAE and WAPE together, not MAE alone. Penn Station is worst on both (MAE 18.1, WAPE 21.6%), so it is genuinely harder — likely surge behaviour around a transport hub that lagged pickups cannot anticipate. Midtown Center has high MAE (13.5) but the *best* WAPE in the panel (11.5%), which is a volume effect rather than a modelling failure. Ranking zones by MAE alone would conflate those two very different cases.

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

## Diagnosed failure pattern - weekly-lag staleness around an irregular week

Added 15 September 2026. This is a **diagnosis of the existing frozen result**, computed
from `artifacts/first-run/predictions.csv.gz`. No model was changed, no feature was added
and no metric was recomputed in the model's favour. The holdout scores above are untouched.

### The question
The model overpredicts by +1.96 pickups per zone-bin across the holdout while persistence
is unbiased (+0.01). Earlier drafts of this document guessed a January-to-February level
shift. That guess is wrong.

### Evidence against the level-shift explanation
Mean observed pickups per zone-bin are essentially flat across the two holdout weeks:

| Holdout week | Mean observed | Model bias | Model MAE |
|---|---:|---:|---:|
| 15-21 Feb (contains Presidents' Day) | 73.40 | **+3.02** | 11.35 |
| 22-28 Feb (ordinary week) | 74.24 | **+0.90** | 10.31 |

Demand did not fall. The bias more than tripled anyway, so a level shift cannot explain it.

### What the bias is associated with
The bias tracks how far the **same half-hour one week earlier** sat from what actually
happened - which is exactly what the `lag_336` feature and the weekly-naive baseline read.
Across the 14 holdout days, the correlation between `observed - (observed one week earlier)`
and the model's daily bias is **r = -0.917** (r-squared approx 0.84). That is a strong
*association*: the day-to-day bias pattern moves closely with weekly-lag staleness. It is
not a causal decomposition, and it does not establish that `lag_336` produces 84% of the
bias. No ablation was run - dropping or gating `lag_336` and re-measuring would be the
test, and that test needs a fresh period, not this holdout.

The mechanism is visible on two specific days:

| Date | Day | Observed | One week earlier | Gap | Model bias |
|---|---|---:|---:|---:|---:|
| Mon 17 Feb | Presidents' Day | 52.24 | 65.69 | **-13.45** | **+5.16** |
| Mon 24 Feb | ordinary Monday | 57.40 | 52.24 | **+5.16** | **-1.29** |

Presidents' Day demand came in far below the previous Monday, and the model - anchored on
the weekly lag - overpredicted. One week later the *holiday itself* became the lag feature
for an ordinary Monday, and the model underpredicted. The error reverses sign, which is the
signature of a stale seasonal feature rather than a biased level.

The window 17-21 Feb is **36% of holdout rows but contributes 61% of the total +1.96 bias**
(bias +3.34 inside that window against +1.20 outside it).

### Why this matters beyond the bias number
The same weekly-lag exposure is the most plausible link to the **baseline rank flip**
already reported, though this too is an association rather than a demonstrated cause: weekly-naive
was the better baseline on validation (13.93 vs persistence 15.07) and the worse one on test
(16.22 vs 14.29). The validation window, 1-14 Feb, contains no public holiday; the test
window does. Any method leaning on a 7-day lag degrades in that window, the pure weekly
baseline most of all. One irregular day coincides with movement in both the baseline ranking and the
model's bias - which is why the model's win is reported against both baselines, not the
convenient one.

### Honest limits of this diagnosis
Presidents' Day is a verifiable US federal holiday on 17 February 2025 and its
school-recess week is a plausible driver, but this analysis establishes the **statistical
pattern**, not the causal mechanism. No holiday calendar, weather series or event feed was
joined. The correlation is computed on 14 daily points, which is a small sample. The obvious
remedy - an irregular-day indicator - has deliberately **not** been implemented, because
the diagnosis used the holdout and the holdout can no longer serve as a clean test for it.

---

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

### Smoke test — what was actually verified
Run headless on port 8599:
- Server boots cleanly; `/healthz` and `/` both return HTTP 200; no errors or tracebacks in the startup log.
- Every data path the page uses was exercised directly in Python: all six required artifact files present, `data_is_synthetic` is `False`, selected model resolves to `boosted_trees` (MAE 10.83), zone selector has 20 options, day selector has 14, the line chart returns 48 rows for a zone/day with all four series present, the ranking bar chart returns 20 named zones with no unmapped names, and the download payload is 238,363 bytes.
- The server was stopped afterwards; no Streamlit processes are left running.

**Not verified:** the page was not driven through a browser, so visual layout, actual widget interaction, and the missing-artifacts empty state were not exercised as a user would. The empty state is a straightforward file-existence branch, but it remains untested.

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
| Streamlit dashboard | Implemented, tested | Boots (HTTP 200); `test_app_populated_state` asserts selectors, tables and headline metric; **not browser-driven** |
| Dashboard empty/error state | Implemented, **not exercised now** | `test_app_empty_state` covers it, but only applies before a benchmark exists |
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

## Known Limitations & Future Work

### Limitations
1. **Zero-ingestion-latency assumption:** Features assume t−1 pickup counts available instantly at time t. Real deployment requires telemetry SLA study.
2. **Completed trips only:** Rejected requests, demand surges, and unmet waits invisible.
3. **No supply data:** Vehicle availability, repositioning costs, and driver behavior not modeled.
4. **Seasonal scope:** Two winter months; does not validate summer travel, holidays, or multi-year patterns.
5. **Zone scope:** Top 20 Manhattan zones only; excludes outer boroughs and low-activity zones.
6. **Not a revenue model:** Lower forecast error does not prove shorter waits, higher fares, or fleet revenue.
7. **Positive bias, now diagnosed (15 Sep 2026):** the model overpredicts in every zone (+0.72 to +4.09, overall +1.96) while persistence is essentially unbiased (+0.01). It still wins clearly on MAE, RMSE and WAPE. The earlier hypothesis in this document - a level shift between January training data and the late-February holdout - is **refuted by the data**: the two test weeks have almost identical mean demand (73.40 vs 74.24 pickups per zone-bin). See "Diagnosed failure pattern" below for the pattern the bias is associated with.

### Defensible next steps (if more time)
1. **Act on the diagnosed bias:** the pattern is consistent with weekly-lag staleness around an irregular week being a major driver, and is not consistent with a level shift (see "Diagnosed failure pattern"). The cheap fix is a holiday/irregular-day indicator feature, or down-weighting `lag_336` when the previous week's same slot diverges from the recent local level. Both must be selected on validation only; the Feb 15-28 holdout has now been examined and cannot serve as a clean test for any such change.
2. **Latency sensitivity:** Measure telemetry delay; retrain features with realistic lag.
3. **External features:** Test impact of hour/day boundaries on edge cases (midnight, holidays).
4. **Outer boroughs:** Extend to all zones if outer-borough trip patterns are similar.
5. **Multi-horizon:** Evaluate 1-step vs 2-step vs 4-step-ahead (diminishing returns expected).
6. **Vehicle supply:** Enrich with hourly supply snapshots (if available) to separate supply from demand.
7. **Online validation:** Prospective holdout on future months (not yet available).

---

## Three-Minute Interview Walkthrough

### Opening (30 sec)
"I built a 30-minute pickup forecasting system for NYC taxi zones using public data. The goal: given history up to time t, predict pickups in the next 30 minutes per zone, compare against persistence and weekly seasonality baselines, and identify where the model fails."

### Data & methodology (60 sec)
"I used official NYC TLC trip records (Jan–Feb 2025) and aggregated pickups into 30-minute buckets per zone. To avoid data leakage, I constructed all features (lags, rolling means, hour, day-of-week) using only past observations. I split chronologically—training on Jan 8–31, validation on Feb 1–14, and held out Feb 15–28 untouched. This respects time-series structure; random train/test splits would be invalid."

"I implemented two baselines: persistence (last 30 min) and weekly seasonal (same time last week). Then I trained a gradient-boosted tree with Poisson loss. It's simple, interpretable, and fast—no neural networks or hyperparameter searches."

### Results (45 sec)
"On the holdout, the model achieved MAE of 10.8 pickups/zone/30-min, compared to 14.3 for persistence and 16.2 for weekly seasonal — a 24% reduction against the baseline that actually performed best on the test period, persistence, and 33% against weekly seasonal. Worth noting: weekly seasonal was the stronger baseline on validation and the weaker one on test, which is itself a reminder that baseline ranking is not stable across periods. However, performance is not uniform: residential zones like Lenox Hill forecast well (MAE ~7), but high-traffic hubs like Penn Station are harder (MAE ~18). This suggests the model captures steady demand but struggles with unpredictable surge events."

### Limitations & next steps (45 sec)
"Three honest limitations: First, I assume previous pickup counts are instantly available—real systems have telemetry delay. Second, this dataset covers completed trips only; rejected or unmet requests are missing. Third, one forecast model doesn't generalize across all zone types. I don't claim this reduces wait times or increases revenue; that would require supply and travel-time data."

"The failure I would actually lead with is the bias. The model overpredicts by about 2 pickups per zone-bin while persistence is unbiased. I assumed a level shift and the data refuted it - both holdout weeks have the same mean demand. It lines up with the weekly lag: across the 14 holdout days, the gap between what happened and what happened in the same slot a week earlier correlates with the model's daily bias at r = -0.917. I'd call that strongly associated, not proven - I didn't run the ablation. Presidents' Day is the clearest case, and the sign flips the following Monday when the holiday itself becomes the lag feature. The same weekly-lag exposure is the most plausible link to my baseline ranking flipping between validation and test. I did not implement the fix, because I had already spent the holdout diagnosing it."

---

## Technical Interview Questions & Answers

### 1. "Why did you choose a 30-minute forecast horizon?"
**Answer:**  
NYC taxi dispatch operates at sub-hourly resolution; drivers need to know demand within the next 30–60 minutes to reposition meaningfully. A 30-minute horizon is short enough to be relevant and long enough that persistence isn't automatic. Longer horizons (hourly, daily) have diminishing signal from lagged features; shorter ones (5-min) would require ingestion faster than available.

### 2. "How do you prevent data leakage in time-series forecasting?"
**Answer:**  
I construct all features using only observations strictly before the forecast time t: lags end at t−1, rolling windows use history up to t−1, and calendar features (hour, day) are deterministic. I never include the same bin's outcome or any future bins. During testing, I freeze model weights and use rolling one-step-ahead evaluation: predict t+30min given history up to t, then move to t+30min and repeat. This mimics real deployment where you forecast once, observe, and move forward.

### 3. "Why gradient boosting over neural networks or ARIMA?"
**Answer:**  
For this problem, boosting is sufficient: 10 features, 23,040 training rows, nonlinear interactions (e.g., slot × lag_48 varying by zone). Neural networks would overfit at this data size and add tuning surface with no measured benefit. ARIMA assumes linear autocorrelation; boosting learns nonlinear patterns from lagged features and categorical interactions without those assumptions. I verified this on validation MAE before committing to the test set.

### 4. "The model performs worse on Penn Station. Why?"
**Answer:**  
Penn Station is a high-traffic commuter/tourist hub with unpredictable surges: events, weather, service delays, and crowd dynamics. Lagged pickups alone don't capture these exogenous shocks. Zones like Lenox Hill are more residential and have steadier demand driven by local patterns. A single model can't fit both. Next step: fit a categorical model (high-volatility vs. steady) or add external features (weather, event calendars, service alerts).

### 5. "How would you deploy this in production?"
**Answer:**  
Three steps: First, measure actual telemetry latency—verify that previous pickup counts are available within the forecast window. Second, set up online validation: retrain monthly on fresh data while holding out recent dates to detect if patterns drift. Third, implement a feedback loop: compare predictions to observed outcomes, alert if error degrades, and trigger retraining. I'd avoid real-time streaming initially; batch hourly or daily predictions are sufficient for fleet positioning.

### 6. "What does this NOT establish?"
**Answer:**  
Lower forecast error is not evidence that repositioning will reduce waits, increase revenue, or improve driver earnings. Those outcomes depend on vehicle supply, travel times, and policy (surge pricing, incentives). This forecasts completed trip counts, not latent demand or unmet requests. The model is trained on NYC yellow taxis in winter 2025; results don't generalize to other cities or seasons without revalidation.

### 7. "How did you choose your validation/test split?"
**Answer:**  
I used chronological windows: 8 days training, 14 days validation, 14 days test. This ensures no temporal leakage and mimics the actual decision point (choose a model after validation, then evaluate once on future data). I didn't use random splits or nested cross-validation; time series require contiguous windows. If I had more data, I'd use multiple validation/test cycles to estimate error variance.

### 8. "What's the biggest assumption in your feature engineering?"
**Answer:**  
That the previous half-hour's pickup count is available immediately at forecast time t (zero-ingestion-latency). In reality, billing, deduplication, and data pipelines introduce 5–60+ minute delays. If actual latency is 30 minutes, the most recent feature is stale, and model accuracy drops. I'd measure this in a real system and retrain features if latency is systematic.

---

## Reproduction Recipe (for Codex or manual review)

```bash
# Start fresh. Note: artifacts/first-run is the frozen evidence set - do NOT delete it.
# A reproduction writes to a separate directory and leaves the original untouched.
cd /Users/leonardaarons-ditson/Code/fleetcast-odysse
rm -rf .venv data/processed

# Install
uv sync
uv run pytest -q        # Before prepare/run: 28 pass, 1 skip (populated-app test N/A)

# Ingest
uv run python -m fleetcast prepare
# Expected output: 56,640 zone/time rows -> data/processed/panel.csv.gz

# Train & evaluate into a separate directory, preserving the frozen first run
uv run python -m fleetcast run --output artifacts/reproduction
# Expected output: benchmark written to artifacts/reproduction/
# Verified 15 Sep 2026: metrics and predictions.csv.gz are bit-identical to first-run

# Verify outputs exist
ls artifacts/reproduction/
# Expected files: REPORT.md, metrics.json, predictions.csv.gz, by_zone.csv, by_day.csv, zones.csv, metadata.json

# Re-run the suite now that artifacts exist: 28 pass, 1 skip (empty-state test N/A)
uv run pytest -q

# Dashboard
uv run streamlit run app.py
# Open http://localhost:8501, select zone & day, inspect charts and tables
# Verify zone selector works, predictions/observed match REPORT.md metrics
```

---

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
