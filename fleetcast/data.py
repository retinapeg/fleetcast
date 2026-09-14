"""Download official source files, aggregate with DuckDB SQL, record provenance."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from .features import START, TRAIN_END, END, complete_panel, select_zones

SOURCE = "NYC TLC yellow taxi trip records"
BASE = "https://d37ci6vzurychx.cloudfront.net"
FILES = {
    "yellow_tripdata_2025-01.parquet": f"{BASE}/trip-data/yellow_tripdata_2025-01.parquet",
    "yellow_tripdata_2025-02.parquet": f"{BASE}/trip-data/yellow_tripdata_2025-02.parquet",
    "taxi_zone_lookup.csv": f"{BASE}/misc/taxi_zone_lookup.csv",
}

# Only pickup time/location enter the target construction. No dropoff, fare or
# future trip-outcome feature is used. Record-level duplicates are NOT removed:
# two legitimate trips can share these two fields, and there is no unique trip ID.
AGGREGATE_SQL = """
SELECT time_bucket(INTERVAL '30 minutes', pickup_time) AS timestamp,
       zone_id, count(*)::BIGINT AS pickups
FROM valid
GROUP BY 1, 2
ORDER BY 2, 1
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_file(url: str, target: Path, max_bytes: int = 250_000_000) -> dict:
    """Cache downloads; .part files are never treated as successful downloads."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        partial = target.with_suffix(target.suffix + ".part")
        request = Request(url, headers={"User-Agent": "FleetCast-independent-research/0.1"})
        try:
            with urlopen(request, timeout=60) as response, partial.open("wb") as f:
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise ValueError(f"Download exceeds {max_bytes} byte budget: {target.name}")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Download exceeded size budget")
                    f.write(chunk)
                if size == 0 or (length and size != int(length)):
                    raise ValueError("Empty or incomplete download")
            partial.replace(target)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    if target.suffix == ".parquet":
        with target.open("rb") as f:
            if f.read(4) != b"PAR1":
                raise ValueError(f"Not a Parquet file: {target}. Remove this file and retry.")
            f.seek(-4, 2)
            if f.read(4) != b"PAR1":
                raise ValueError(f"Truncated Parquet file: {target}")
    return {"file": target.name, "url": url, "bytes": target.stat().st_size, "sha256": sha256(target)}


def aggregate_files(paths: list[Path], lookup: pd.DataFrame, n_zones: int = 20) -> tuple[pd.DataFrame, dict]:
    # Lazy import: feature/model unit tests can run without download dependencies.
    import duckdb

    if len(paths) != 2:
        raise ValueError("Provide exactly the January and February 2025 files")
    required = {"LocationID", "Borough", "Zone"}
    if not required.issubset(lookup.columns) or lookup["LocationID"].duplicated().any():
        raise ValueError("Invalid zone lookup schema/duplicate IDs")
    windows = pd.DataFrame({
        "filename": [str(p.resolve()) for p in paths],
        "month_start": [START, TRAIN_END],
        "month_end": [TRAIN_END, END],
    })
    with duckdb.connect() as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        con.read_parquet(windows["filename"].tolist(), filename=True, union_by_name=True).create_view("raw_source")
        con.register("file_windows", windows)
        con.register("zone_lookup", lookup)
        con.execute("""
            CREATE TEMP VIEW candidates AS
            SELECT try_cast(tpep_pickup_datetime AS TIMESTAMP) AS pickup_time,
                   try_cast(PULocationID AS INTEGER) AS zone_id, filename
            FROM raw_source
        """)
        con.execute("""
            CREATE TEMP TABLE valid AS
            SELECT c.pickup_time, c.zone_id
            FROM candidates c
            JOIN file_windows w ON c.filename = w.filename
            JOIN zone_lookup z ON c.zone_id = z.LocationID
            WHERE c.pickup_time >= w.month_start AND c.pickup_time < w.month_end
              AND c.zone_id BETWEEN 1 AND 263
        """)
        raw_count = con.execute("SELECT count(*) FROM raw_source").fetchone()[0]
        valid_count = con.execute("SELECT count(*) FROM valid").fetchone()[0]
        counts = con.execute(AGGREGATE_SQL).df()
    counts["timestamp"] = pd.to_datetime(counts["timestamp"])
    expected = pd.date_range(START, END, freq="30min", inclusive="left")
    observed = pd.DatetimeIndex(counts["timestamp"].unique())
    missing_city_bins = expected.difference(observed)
    if len(missing_city_bins):
        raise ValueError(
            f"{len(missing_city_bins)} entirely missing citywide intervals. "
            "Investigate source coverage before interpreting absent zone bins as zero."
        )
    zones = select_zones(counts, lookup, n_zones)
    panel = complete_panel(counts, zones)
    info = {
        "raw_rows": int(raw_count), "valid_time_and_zone_rows": int(valid_count),
        "excluded_rows": int(raw_count - valid_count),
        "selected_zone_ids": zones,
        "panel_rows": len(panel), "retained_pickups": int(panel["pickups"].sum()),
        "selection_rule": f"Top {n_zones} Manhattan zones by January 2025 pickup count; ties by zone ID",
        "training_boundary_exclusive": str(TRAIN_END),
        "source_coverage_check": "Every citywide 30-minute interval represented",
        "missing_zone_bin_assumption": "Zero after source coverage checks; completeness not guaranteed by TLC",
        "duplicate_rule": "Retained; no unique trip ID, identical pickup fields are not proof of duplication",
        "timestamp_policy": "NYC local naive time; Jan-Feb 2025 only, no DST transition within period",
        "rejected_record_rule": "Null/unparseable pickup time, wrong source month, or unknown/non-NYC zone",
    }
    return panel, info


def prepare(root: Path) -> Path:
    raw = root / "data" / "raw"
    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    sources = []
    for name, url in FILES.items():
        print(f"Fetching/checking {name} ...", flush=True)
        sources.append(fetch_file(url, raw / name))
    lookup = pd.read_csv(raw / "taxi_zone_lookup.csv")
    paths = [raw / f"yellow_tripdata_2025-{month:02d}.parquet" for month in (1, 2)]
    panel, quality = aggregate_files(paths, lookup)
    panel_path = processed / "panel.csv.gz"
    # Fixed gzip mtime makes the compressed dataset checksum reproducible.
    panel.to_csv(panel_path, index=False, compression={"method": "gzip", "mtime": 0})
    lookup[lookup["LocationID"].isin(quality["selected_zone_ids"])].to_csv(processed / "zones.csv", index=False)
    manifest = {
        "source": SOURCE,
        "source_page": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "panel_sha256": sha256(panel_path), "quality": quality,
        "target": "Observed completed yellow-taxi pickups per zone per 30 minutes, not total/unserved demand",
        "data_is_synthetic": False,
    }
    (processed / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(panel):,} zone/time rows -> {panel_path}")
    return panel_path
