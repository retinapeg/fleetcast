"""Small fixed-model benchmark; chronological validation and final holdout."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .data import SOURCE, sha256
from .features import FEATURES, TRAIN_END, TEST_START, END, build_features, split_features

MODEL_NAMES = ("persistence", "weekly_naive", "boosted_trees")


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.shape != predicted.shape or actual.ndim != 1 or not actual.size:
        raise ValueError("Metrics need equally sized nonempty 1D arrays")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Non-finite metric inputs")
    if (actual < 0).any() or (predicted < 0).any():
        raise ValueError("Counts/predictions cannot be negative")
    error = predicted - actual
    denominator = actual.sum()
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "wape": float(np.abs(error).sum() / denominator) if denominator > 0 else None,
        "bias": float(error.mean()),
        "rows": int(actual.size),
    }


def new_model() -> HistGradientBoostingRegressor:
    # Fixed recipe before seeing test results. No random internal validation split.
    return HistGradientBoostingRegressor(
        loss="poisson", max_iter=120, max_leaf_nodes=15,
        learning_rate=0.08, l2_regularization=1.0,
        early_stopping=False, random_state=42,
        categorical_features=[name == "zone_code" for name in FEATURES],
    )


def predictions(frame: pd.DataFrame, fitted: HistGradientBoostingRegressor) -> pd.DataFrame:
    result = frame[["timestamp", "zone_id", "pickups"]].copy()
    result["persistence"] = frame["lag_1"].to_numpy()
    result["weekly_naive"] = frame["lag_336"].to_numpy()
    result["boosted_trees"] = np.maximum(fitted.predict(frame[FEATURES]), 0)
    return result


def score_predictions(frame: pd.DataFrame) -> dict:
    return {name: metrics(frame["pickups"].to_numpy(), frame[name].to_numpy()) for name in MODEL_NAMES}


def benchmark(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    features = build_features(panel)
    train, validation, test = split_features(features)
    if train["pickups"].sum() <= 0:
        raise ValueError("Poisson model needs some positive training targets")
    with threadpool_limits(limits=2):
        model = new_model().fit(train[FEATURES], train["pickups"])
        validation_results = score_predictions(predictions(validation, model))
        # MAE is the predefined selection metric; on identical rows it ranks like WAPE.
        chosen = min(MODEL_NAMES, key=lambda name: validation_results[name]["mae"])
        best_baseline = min(MODEL_NAMES[:2], key=lambda name: validation_results[name]["mae"])
        # Recipe and selection are now frozen. Refit only on information before test.
        development = pd.concat([train, validation], ignore_index=True)
        model = new_model().fit(development[FEATURES], development["pickups"])
        test_predictions = predictions(test, model)
    result = {
        "validation": validation_results, "test": score_predictions(test_predictions),
        "recommended_model_from_validation": chosen,
        "baseline_selected_on_validation": best_baseline,
    }
    protocol = {
        "seed": 42,
        "features": FEATURES,
        "target_interval": "[timestamp, timestamp + 30 minutes)",
        "first_feature_timestamp": str(features["timestamp"].min()),
        "train_end_exclusive": str(TRAIN_END),
        "validation_end_exclusive": str(TEST_START),
        "test_end_exclusive": str(END),
        "partition_rows": {"train": len(train), "validation": len(validation), "test": len(test)},
        "evaluation": "Rolling one-step-ahead forecasts; weights fixed during each evaluation period",
        "past_test_observations": "Earlier observed bins may be lag features for later origins; future bins never are",
        "availability_assumption": "Previous 30-minute pickup totals available at each forecast origin (zero latency)",
        "model_recipe": {"loss": "poisson", "max_iter": 120, "max_leaf_nodes": 15,
                         "learning_rate": 0.08, "l2_regularization": 1.0, "early_stopping": False},
        "test_policy": "One frozen holdout. Re-running is reproduction, not a fresh independent test. No tuning to this score.",
    }
    return test_predictions, result, protocol


def run(root: Path, output: Path) -> Path:
    data_dir = root / "data" / "processed"
    panel_path, provenance_path = data_dir / "panel.csv.gz", data_dir / "provenance.json"
    if not panel_path.exists() or not provenance_path.exists():
        raise FileNotFoundError("No verified real dataset. First run: uv run python -m fleetcast prepare")
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("source") != SOURCE or provenance.get("data_is_synthetic") is not False:
        raise ValueError("Real benchmark requires the official TLC ingestion manifest; no synthetic fallback")
    if provenance.get("panel_sha256") != sha256(panel_path):
        raise ValueError("Panel checksum differs from provenance. Investigate before benchmarking.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Output is nonempty; preserve it. Choose a new --output path for a documented reproduction.")
    panel = pd.read_csv(panel_path, parse_dates=["timestamp"])
    predicted, result, protocol = benchmark(panel)
    output.mkdir(parents=True, exist_ok=True)
    predicted.to_csv(output / "predictions.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    (output / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    zones = pd.read_csv(data_dir / "zones.csv")
    zones.to_csv(output / "zones.csv", index=False)
    by_zone, by_day = [], []
    for key, group in predicted.groupby("zone_id"):
        for name in MODEL_NAMES:
            by_zone.append({"zone_id": int(key), "model": name, **metrics(group.pickups.to_numpy(), group[name].to_numpy())})
    for day, group in predicted.groupby(predicted["timestamp"].dt.date):
        for name in MODEL_NAMES:
            by_day.append({"date": str(day), "model": name, **metrics(group.pickups.to_numpy(), group[name].to_numpy())})
    pd.DataFrame(by_zone).merge(zones[["LocationID", "Zone"]], left_on="zone_id", right_on="LocationID", how="left").to_csv(output / "by_zone.csv", index=False)
    pd.DataFrame(by_day).to_csv(output / "by_day.csv", index=False)
    code_hash = hashlib.sha256()
    for path in sorted((root / "fleetcast").glob("*.py")):
        code_hash.update(path.name.encode())
        code_hash.update(path.read_bytes())
    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_provenance": provenance, "protocol": protocol,
        "python": platform.python_version(),
        "versions": {name: version(name) for name in ("numpy", "pandas", "scikit-learn", "duckdb")},
        "source_code_sha256": code_hash.hexdigest(),
    }
    (output / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    report = ["# FleetCast — first real-data benchmark", "",
              "Independent case study. NYC yellow taxis are a proxy, not Odysse's London fleet.", "",
              "## Protocol", "",
              "Train: Jan 8–31 2025 after seven-day lag warmup. Validate: Feb 1–14. Test: Feb 15–28.",
              "Rolling 30-minute-ahead predictions with fixed evaluation-period weights and observed prior bins.",
              "Previous pickup totals are assumed immediately available. This is not a live system.", "",
              f"Model selected on validation: **{result['recommended_model_from_validation']}**.",
              f"Baseline selected on validation: **{result['baseline_selected_on_validation']}**.", "",
              "## Held-out results", "",
              "| Method | MAE | RMSE | WAPE | Bias |", "|---|---:|---:|---:|---:|"]
    for name, score in result["test"].items():
        wape = "N/A" if score["wape"] is None else f"{100 * score['wape']:.2f}%"
        report.append(f"| {name} | {score['mae']:.3f} | {score['rmse']:.3f} | {wape} | {score['bias']:.3f} |")
    report += ["", "## Interpretation limits", "",
               "These are forecast errors, not a measured reduction in waits or an increase in revenue.",
               "The observations cover completed trips, not rejected requests or unmet demand.",
               "No supply/driver-availability data, causal experiment, dispatch policy or RL result is claimed.",
               "Top-zone selection uses only January; this omits low-volume zones and limits generalisation.",
               "Inspect by_zone.csv and by_day.csv for systematic failure, not only the aggregate score.",
               "Two winter months in one city do not establish seasonal robustness or UK transferability.",
               "The public files are retrospective. Real telemetry latency must be measured before deployment.",
               "Do not tune the model after inspecting this holdout and continue calling it untouched.", ""]
    (output / "REPORT.md").write_text("\n".join(report))
    print(f"Benchmark complete -> {output}. Read REPORT.md; no uplift is guaranteed.")
    return output
