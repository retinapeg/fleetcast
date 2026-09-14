"""Synthetic data here is for correctness tests ONLY, never portfolio metrics."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fleetcast.features import (
    START, END, TRAIN_END, TEST_START, FEATURES,
    build_features, complete_panel, select_zones, split_features, validate_panel,
)
from fleetcast.model import benchmark, metrics, new_model, run


@pytest.fixture(scope="module")
def panel():
    times = pd.date_range(START, END, freq="30min", inclusive="left")
    rng = np.random.default_rng(42)
    frames = []
    for zone in (1, 2, 3):
        rate = 10 + zone * 6 + 5 * (1 + np.sin(np.arange(len(times)) * 2 * np.pi / 48))
        frames.append(pd.DataFrame({"timestamp": times, "zone_id": zone, "pickups": rng.poisson(rate)}))
    return pd.concat(frames, ignore_index=True)


def test_panel_valid(panel):
    validate_panel(panel)


@pytest.mark.parametrize("problem", ["duplicate", "missing", "negative", "nan", "fractional", "timezone"])
def test_rejects_invalid_panel(panel, problem):
    frame = panel.copy()
    if problem == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]])
    elif problem == "missing":
        frame = frame.iloc[1:]
    elif problem == "negative":
        frame.loc[0, "pickups"] = -1
    elif problem == "nan":
        frame["pickups"] = frame["pickups"].astype(float)
        frame.loc[0, "pickups"] = np.nan
    elif problem == "fractional":
        frame["pickups"] = frame["pickups"].astype(float)
        frame.loc[0, "pickups"] = 1.5
    else:
        frame["timestamp"] = frame.timestamp.dt.tz_localize("UTC")
    with pytest.raises(ValueError):
        validate_panel(frame)


def test_zone_selection_does_not_see_holdout():
    counts = pd.DataFrame({
        "timestamp": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-02-20"]),
        "zone_id": [1, 2, 2], "pickups": [100, 5, 1_000_000],
    })
    lookup = pd.DataFrame({"LocationID": [1, 2], "Borough": ["Manhattan", "Manhattan"]})
    assert select_zones(counts, lookup, n=1) == [1]


def test_zone_selection_tie_is_deterministic():
    counts = pd.DataFrame({"timestamp": pd.to_datetime(["2025-01-02"] * 2),
                           "zone_id": [2, 1], "pickups": [100, 100]})
    lookup = pd.DataFrame({"LocationID": [1, 2], "Borough": ["Manhattan", "Manhattan"]})
    assert select_zones(counts, lookup, n=1) == [1]


def test_complete_panel_zero_fills_missing_zone_bins():
    counts = pd.DataFrame({"timestamp": [START], "zone_id": [1], "pickups": [7]})
    filled = complete_panel(counts, [1])
    assert len(filled) == 59 * 48
    assert filled.pickups.sum() == 7
    assert filled.iloc[1].pickups == 0


def test_duplicate_count_bins_rejected():
    counts = pd.DataFrame({"timestamp": [START, START], "zone_id": [1, 1], "pickups": [7, 2]})
    with pytest.raises(ValueError):
        complete_panel(counts, [1])


def test_lags_and_rolling_are_past_only(panel):
    features = build_features(panel)
    original = panel[panel.zone_id == 1].reset_index(drop=True)
    row = features[features.zone_id == 1].iloc[0]
    assert row.timestamp == START + pd.Timedelta(days=7)
    assert row.lag_1 == original.iloc[335].pickups
    assert row.lag_48 == original.iloc[288].pickups
    assert row.lag_336 == original.iloc[0].pickups
    assert row.rolling_4 == pytest.approx(original.iloc[332:336].pickups.mean())


def test_future_target_mutation_cannot_change_current_or_past_features(panel):
    cut = pd.Timestamp("2025-02-20 12:00")
    changed = panel.copy()
    changed.loc[changed.timestamp >= cut, "pickups"] += 10000
    a, b = build_features(panel), build_features(changed)
    columns = ["zone_id", "timestamp", *FEATURES]
    pd.testing.assert_frame_equal(a.loc[a.timestamp <= cut, columns], b.loc[b.timestamp <= cut, columns])


def test_one_zones_history_cannot_change_anothers_lags(panel):
    changed = panel.copy()
    changed.loc[changed.zone_id == 1, "pickups"] += 10000
    a, b = build_features(panel), build_features(changed)
    pd.testing.assert_frame_equal(a.loc[a.zone_id == 2, FEATURES], b.loc[b.zone_id == 2, FEATURES])


def test_target_and_future_outcomes_are_not_features():
    forbidden = {"pickups", "dropoff_time", "fare", "revenue", "future_demand", "trip_duration"}
    assert not forbidden.intersection(FEATURES)


def test_chronological_partition_boundaries(panel):
    train, validation, test = split_features(build_features(panel))
    assert train.timestamp.max() < TRAIN_END == validation.timestamp.min()
    assert validation.timestamp.max() < TEST_START == test.timestamp.min()
    assert test.timestamp.max() < END
    assert len(train) == 24 * 48 * 3
    assert len(validation) == len(test) == 14 * 48 * 3


def test_metrics_known_values():
    result = metrics(np.array([0, 2]), np.array([1, 1]))
    assert result["mae"] == 1
    assert result["rmse"] == 1
    assert result["wape"] == 1
    assert result["bias"] == 0


def test_zero_actual_total_has_no_fake_percentage():
    assert metrics(np.array([0, 0]), np.array([0, 1]))["wape"] is None


@pytest.mark.parametrize("actual,predicted", [([], []), ([1], [1, 2]), ([1], [float("nan")]), ([-1], [1]), ([1], [-1])])
def test_invalid_metrics_rejected(actual, predicted):
    with pytest.raises(ValueError):
        metrics(np.array(actual), np.array(predicted))


def test_model_has_no_random_validation_split():
    params = new_model().get_params()
    assert params["early_stopping"] is False
    assert params["random_state"] == 42
    assert params["loss"] == "poisson"


def test_benchmark_runs_and_uses_expected_test_rows(panel):
    predicted, results, protocol = benchmark(panel)
    assert len(predicted) == 14 * 48 * 3
    assert predicted.timestamp.min() == TEST_START
    assert predicted.timestamp.max() < END
    assert (predicted[["persistence", "weekly_naive", "boosted_trees"]] >= 0).all().all()
    assert protocol["partition_rows"]["test"] == len(predicted)
    chosen = min(results["validation"], key=lambda n: results["validation"][n]["mae"])
    assert results["recommended_model_from_validation"] == chosen
    assert set(results["test"]) == {"persistence", "weekly_naive", "boosted_trees"}


def test_no_real_data_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError, match="No verified real dataset"):
        run(tmp_path, tmp_path / "results")


def test_duckdb_aggregation_integration(tmp_path):
    """Dependency-gated here; must run without skip on the fully installed Mac."""
    duckdb = pytest.importorskip("duckdb", reason="DuckDB not installed in the artifact authoring environment")
    from fleetcast.data import aggregate_files
    paths = []
    with duckdb.connect() as con:
        for month, lo, hi in [(1, START, TRAIN_END), (2, TRAIN_END, END)]:
            source = pd.DataFrame({
                "tpep_pickup_datetime": pd.date_range(lo, hi, freq="30min", inclusive="left"),
                "PULocationID": 1,
            })
            con.register("fixture_source", source)
            path = tmp_path / f"yellow_tripdata_2025-{month:02d}.parquet"
            # The generated path is test-controlled; do not do this with untrusted text.
            safe_path = str(path).replace("'", "''")
            con.execute(f"COPY fixture_source TO '{safe_path}' (FORMAT PARQUET)")
            paths.append(path)
    lookup = pd.DataFrame({"LocationID": [1], "Borough": ["Manhattan"], "Zone": ["TEST FIXTURE"]})
    output, quality = aggregate_files(paths, lookup, n_zones=1)
    assert len(output) == 59 * 48
    assert output.pickups.eq(1).all()
    assert quality["excluded_rows"] == 0
