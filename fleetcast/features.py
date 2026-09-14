"""Time-indexed features. A row at t predicts pickups in [t, t + 30 min)."""
from __future__ import annotations

import numpy as np
import pandas as pd

START = pd.Timestamp("2025-01-01")
TRAIN_END = pd.Timestamp("2025-02-01")
TEST_START = pd.Timestamp("2025-02-15")
END = pd.Timestamp("2025-03-01")
FREQUENCY = "30min"
LAGS = (1, 2, 48, 336)
FEATURES = [
    "zone_code", "slot", "day_of_week", "weekend",
    "lag_1", "lag_2", "lag_48", "lag_336", "rolling_4", "rolling_48",
]


def select_zones(counts: pd.DataFrame, lookup: pd.DataFrame, n: int = 20) -> list[int]:
    """Select Manhattan zones using ONLY the initial training period."""
    if n < 1:
        raise ValueError("n must be positive")
    if lookup["LocationID"].duplicated().any():
        raise ValueError("Duplicate zone IDs in lookup")
    allowed = lookup.loc[lookup["Borough"].eq("Manhattan"), "LocationID"]
    rows = counts.loc[
        counts["timestamp"].ge(START)
        & counts["timestamp"].lt(TRAIN_END)
        & counts["zone_id"].isin(allowed)
    ]
    totals = rows.groupby("zone_id", as_index=False)["pickups"].sum()
    totals = totals[totals["pickups"] > 0]
    totals = totals.sort_values(["pickups", "zone_id"], ascending=[False, True])
    if totals.empty:
        raise ValueError("No positive Manhattan training-period observations")
    return sorted(totals.head(n)["zone_id"].astype(int).tolist())


def complete_panel(counts: pd.DataFrame, zones: list[int]) -> pd.DataFrame:
    """Zero-fill absent zone bins only after upstream full-file coverage checks."""
    if not zones or len(zones) != len(set(zones)):
        raise ValueError("zones must be nonempty and unique")
    if counts.duplicated(["zone_id", "timestamp"]).any():
        raise ValueError("Counts must already be aggregated to unique zone/time rows")
    index = pd.MultiIndex.from_product(
        [zones, pd.date_range(START, END, freq=FREQUENCY, inclusive="left")],
        names=["zone_id", "timestamp"],
    )
    selected = counts[counts["zone_id"].isin(zones)]
    panel = selected.set_index(["zone_id", "timestamp"])[["pickups"]].reindex(index, fill_value=0)
    panel = panel.reset_index()
    validate_panel(panel)
    panel["pickups"] = panel["pickups"].astype("int64")
    return panel


def validate_panel(panel: pd.DataFrame) -> None:
    required = {"timestamp", "zone_id", "pickups"}
    if not required.issubset(panel.columns) or panel.empty:
        raise ValueError("Need a nonempty panel with timestamp, zone_id, pickups")
    if panel[list(required)].isna().any().any():
        raise ValueError("Null timestamp, zone_id or pickup count")
    if not pd.api.types.is_datetime64_any_dtype(panel["timestamp"]):
        raise ValueError("timestamp must be datetime, not strings")
    if panel["timestamp"].dt.tz is not None:
        raise ValueError("This fixed Jan-Feb case study expects NYC local naive timestamps")
    if panel.duplicated(["zone_id", "timestamp"]).any():
        raise ValueError("Duplicate zone/time rows")
    y = panel["pickups"].to_numpy(dtype=float)
    if not np.isfinite(y).all() or (y < 0).any() or (y != np.floor(y)).any():
        raise ValueError("Counts must be finite nonnegative integers")
    z = panel["zone_id"].to_numpy(dtype=float)
    if not np.isfinite(z).all() or (z != np.floor(z)).any():
        raise ValueError("zone_id must contain finite integers")
    expected = pd.date_range(START, END, freq=FREQUENCY, inclusive="left")
    for _, frame in panel.groupby("zone_id"):
        actual = pd.DatetimeIndex(frame["timestamp"].sort_values())
        if not actual.equals(expected):
            raise ValueError("Each zone must cover Jan-Feb 2025 at exactly 30-minute intervals")


def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Strictly past-only per-zone lags; calendar features for known forecast time."""
    validate_panel(panel)
    frame = panel.sort_values(["zone_id", "timestamp"]).reset_index(drop=True).copy()
    mapping = {zone: i for i, zone in enumerate(sorted(frame["zone_id"].unique()))}
    frame["zone_code"] = frame["zone_id"].map(mapping)
    group = frame.groupby("zone_id", sort=False)["pickups"]
    for lag in LAGS:
        frame[f"lag_{lag}"] = group.shift(lag)
    for window in (4, 48):
        # Shift first, then roll WITHIN each zone. Never use the target bin.
        frame[f"rolling_{window}"] = group.transform(
            lambda s: s.shift(1).rolling(window, min_periods=window).mean()
        )
    t = frame["timestamp"].dt
    frame["slot"] = t.hour * 2 + t.minute // 30
    frame["day_of_week"] = t.dayofweek
    frame["weekend"] = (t.dayofweek >= 5).astype(int)
    return frame.dropna(subset=FEATURES).reset_index(drop=True)


def split_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = frame[frame["timestamp"] < TRAIN_END].copy()
    validation = frame[(frame["timestamp"] >= TRAIN_END) & (frame["timestamp"] < TEST_START)].copy()
    test = frame[frame["timestamp"] >= TEST_START].copy()
    if any(part.empty for part in (train, validation, test)):
        raise ValueError("Training, validation and test partitions must all be nonempty")
    return train, validation, test
