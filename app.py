"""Read-only, single-page historical replay. No data or training on page load."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "first-run"

st.set_page_config(page_title="FleetCast | Pickup forecasting", page_icon="🚕", layout="wide")
st.title("FleetCast")
st.caption("30-minute pickup forecasting · NYC yellow taxis · Independent mobility case study")
st.info("HISTORICAL HOLDOUT REPLAY — not live demand, a dispatch system, or Odysse fleet data.")

required = ["metrics.json", "metadata.json", "predictions.csv.gz", "zones.csv", "by_zone.csv", "by_day.csv"]
if any(not (OUT / name).exists() for name in required):
    st.warning("No completed real-data benchmark yet. No illustrative scores are being substituted.")
    st.code("uv run python -m fleetcast prepare\nuv run python -m fleetcast run", language="bash")
    st.stop()

scores = json.loads((OUT / "metrics.json").read_text())
meta = json.loads((OUT / "metadata.json").read_text())
if meta["data_provenance"].get("data_is_synthetic") is not False:
    st.error("This view requires verified real-data results.")
    st.stop()
forecast = pd.read_csv(OUT / "predictions.csv.gz", parse_dates=["timestamp"])
zones = pd.read_csv(OUT / "zones.csv")
chosen = scores["recommended_model_from_validation"]
score = scores["test"][chosen]
a, b, c = st.columns(3)
a.metric("Model selected on validation", chosen)
b.metric("Holdout MAE", f"{score['mae']:.2f} pickups / zone / 30 min")
c.metric("Holdout WAPE", "N/A" if score["wape"] is None else f"{score['wape']:.1%}")

names = dict(zip(zones["LocationID"], zones["Zone"]))
zone = st.selectbox("Taxi zone", sorted(names), format_func=lambda z: f"{names[z]} · {z}")
days = sorted(forecast["timestamp"].dt.date.unique())
day = st.selectbox("Holdout day · New York local time", days)
view = forecast[(forecast.zone_id == zone) & (forecast.timestamp.dt.date == day)].set_index("timestamp")
st.subheader("Forecast versus observed pickups")
st.line_chart(view[["pickups", "boosted_trees", "persistence", "weekly_naive"]])
st.caption("Each forecast uses only earlier observed bins. This is one-step-ahead replay, not a two-week-ahead prediction.")

st.subheader("Which zones are forecast to be busiest?")
time = st.select_slider("Forecast origin · local time", options=sorted(view.index.to_list()))
ranking = forecast[forecast.timestamp == time][["zone_id", chosen]].copy()
ranking["Zone"] = ranking.zone_id.map(names)
st.bar_chart(ranking.set_index("Zone")[chosen].sort_values(ascending=False))
st.caption("A pickup-volume ranking is not a relocation recommendation: existing supply and travel costs are missing.")

with st.expander("Baselines, errors and reproducibility", expanded=False):
    st.write("Test period: 15–28 February 2025. The model/recipe was selected before test evaluation.")
    st.dataframe(pd.DataFrame(scores["test"]).T)
    st.write("Errors by zone")
    st.dataframe(pd.read_csv(OUT / "by_zone.csv"))
    st.write("Errors by day")
    st.dataframe(pd.read_csv(OUT / "by_day.csv"))
    st.download_button("Download held-out predictions", (OUT / "predictions.csv.gz").read_bytes(),
                       file_name="fleetcast-heldout-predictions.csv.gz", mime="application/gzip")
    st.json(meta["protocol"])
with st.expander("What this does not establish", expanded=True):
    st.write("Completed-trip counts are not total demand. This dataset has no rejected requests or live vehicle availability. "
             "Forecast accuracy is not evidence of revenue uplift, reduced waiting time, or a causal fleet benefit. "
             "NYC winter taxi patterns are not validated London ride-hailing patterns. "
             "Previous-bin pickup data is assumed available immediately; real data latency needs testing.")
