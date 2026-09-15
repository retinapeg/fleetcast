"""Read-only, single-page historical replay. No data or training on page load."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "first-run"

LABELS = {"pickups": "Observed", "boosted_trees": "Model", "persistence": "Persistence",
          "weekly_naive": "Previous week"}
INK, BLUE, GREY, AMBER = "#0f172a", "#2563eb", "#94a3b8", "#f59e0b"

st.set_page_config(page_title="FleetCast | Pickup forecasting", page_icon="🚕", layout="wide")
st.html("""<style>
  .block-container {padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px;}
  [data-testid="stMetricValue"] {font-size: 1.9rem;}
  [data-testid="stMetricLabel"] {opacity: .75;}
  h1 {margin-bottom: .1rem;} h3 {margin-top: .4rem;}
</style>""")


@st.cache_data(show_spinner=False)
def load_json(name: str):
    return json.loads((OUT / name).read_text())


@st.cache_data(show_spinner=False)
def load_csv(name: str, parse_dates: tuple[str, ...] = ()):
    return pd.read_csv(OUT / name, parse_dates=list(parse_dates))


st.title("FleetCast")
st.caption("30-minute pickup forecasting · NYC yellow taxis · Independent mobility case study")

required = ["metrics.json", "metadata.json", "predictions.csv.gz", "zones.csv", "by_zone.csv", "by_day.csv"]
if any(not (OUT / name).exists() for name in required):
    st.warning("No completed real-data benchmark yet. No illustrative scores are being substituted.")
    st.code("uv run python -m fleetcast prepare\nuv run python -m fleetcast run", language="bash")
    st.stop()

scores = load_json("metrics.json")
meta = load_json("metadata.json")
if meta["data_provenance"].get("data_is_synthetic") is not False:
    st.error("This view requires verified real-data results.")
    st.stop()

forecast = load_csv("predictions.csv.gz", ("timestamp",))
zones = load_csv("zones.csv")
chosen = scores["recommended_model_from_validation"]
score, base, weekly = (scores["test"][k] for k in (chosen, "persistence", "weekly_naive"))
gain_base = 1 - score["mae"] / base["mae"]
gain_weekly = 1 - score["mae"] / weekly["mae"]

st.info("HISTORICAL HOLDOUT REPLAY — not live demand, a dispatch system, or Odysse fleet data.", icon="🗄️")

# ── Headline ────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Model MAE", f"{score['mae']:.2f}", delta=f"{-gain_base:.1%} vs persistence",
          delta_color="inverse", border=True, help="Mean absolute error in pickups per zone per 30 minutes.")
k2.metric("Persistence MAE", f"{base['mae']:.2f}", border=True, help="Previous half-hour, carried forward.")
k3.metric("Previous-week MAE", f"{weekly['mae']:.2f}", border=True, help="Same half-hour, seven days earlier.")
k4.metric("Model WAPE", "N/A" if score["wape"] is None else f"{score['wape']:.1%}", border=True,
          help="Absolute error as a share of observed volume.")
st.caption(
    f"Holdout 15–28 February 2025 · {len(forecast):,} predictions · 20 Manhattan zones · 30-minute bins · "
    f"units are pickups per zone per 30 min · model **{chosen}**, selected on validation before the test was scored."
)

results, replay, failure, evidence = st.tabs(
    ["Results", "Forecast replay", "Where it fails", "Evidence & limits"])

# ── Results ─────────────────────────────────────────────────────────────────
with results:
    st.subheader("Holdout baseline comparison")
    table = (pd.DataFrame(scores["test"]).T
             .rename(index=LABELS, columns={"mae": "MAE", "rmse": "RMSE", "wape": "WAPE", "bias": "Bias",
                                            "rows": "Rows"}))
    table.index.name = "Method"
    st.dataframe(
        table.reset_index(),
        width="stretch", hide_index=True,
        column_config={
            "Method": st.column_config.TextColumn(width="medium"),
            "MAE": st.column_config.NumberColumn(format="%.2f", help="Lower is better. Selection metric."),
            "RMSE": st.column_config.NumberColumn(format="%.2f"),
            "WAPE": st.column_config.NumberColumn(format="percent"),
            "Bias": st.column_config.NumberColumn(format="%+.2f", help="Predicted minus observed."),
            "Rows": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption(
        f"MAE reduction: **{gain_base:.1%}** vs persistence; **{gain_weekly:.1%}** vs previous-week. "
        "Same 13,440 rows for all three methods. Bias = predicted minus observed; positive means overprediction."
    )

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Mean absolute error by method**")
        st.bar_chart(table[["MAE"]].rename(columns={"MAE": "MAE (pickups / zone / 30 min)"}),
                     color=[BLUE], height=240, horizontal=True)
    with right:
        st.markdown("**Read this alongside the headline**")
        st.markdown(
            f"- The model wins on MAE, RMSE and WAPE against both baselines.\n"
            f"- It does **not** win on bias: **{score['bias']:+.2f}** against persistence's "
            f"**{base['bias']:+.2f}**. Near-zero bias is not accuracy — persistence errors telescope and cancel.\n"
            f"- Previous-week was the better baseline on **validation** "
            f"({scores['validation']['weekly_naive']['mae']:.2f} vs "
            f"{scores['validation']['persistence']['mae']:.2f}); persistence was better on **test**. "
            "The model, not a baseline, was selected on validation MAE.\n"
            "- One two-week holdout. No confidence interval or significance test was run, and 13,440 "
            "zone-bins are not independent samples."
        )

# ── Forecast replay ─────────────────────────────────────────────────────────
with replay:
    names = dict(zip(zones["LocationID"], zones["Zone"]))
    days = sorted(forecast["timestamp"].dt.date.unique())
    # Open on the day whose previous-week reference is furthest out of step with observed
    # activity: the exact failure mechanism examined in the next tab. Derived, not a fixed date.
    stale = (forecast["weekly_naive"] - forecast["pickups"]).groupby(forecast.timestamp.dt.date).mean()
    opening = stale.abs().idxmax()

    pick_zone, pick_day = st.columns(2)
    zone = pick_zone.selectbox("Taxi zone", sorted(names), format_func=lambda z: f"{names[z]} · {z}")
    day = pick_day.selectbox("Holdout day · New York local time", days, index=days.index(opening))

    view = forecast[(forecast.zone_id == zone) & (forecast.timestamp.dt.date == day)].set_index("timestamp")
    head, toggle = st.columns([3, 1], vertical_alignment="bottom")
    head.subheader(f"{names[zone]} · {day}")
    with_baselines = toggle.toggle("Show baselines", value=True,
                                   help="Persistence and the previous-week reference, on the same axis.")
    columns = ["pickups", chosen] + (["persistence", "weekly_naive"] if with_baselines else [])
    palette = [INK, BLUE] + ([GREY, AMBER] if with_baselines else [])
    st.line_chart(view[columns].rename(columns=LABELS), color=palette, height=360,
                  x_label="Forecast origin · New York local time", y_label="Pickups per 30 minutes")

    m1, m2, m3 = st.columns(3)
    m1.metric("Bins shown", f"{len(view)}")
    m2.metric("Model MAE here", f"{(view[chosen] - view.pickups).abs().mean():.2f}")
    m3.metric("Model bias here", f"{(view[chosen] - view.pickups).mean():+.2f}")
    st.caption(
        "These three numbers describe **this zone and day only** — not the full-period score. "
        "Each forecast uses only earlier observed bins: one-step-ahead replay, not a two-week-ahead prediction. "
        f"The day selector opens on {opening}, whose previous-week reference is furthest out of step with observed "
        f"activity ({stale.loc[opening]:+.2f} pickups / zone / 30 min). All 14 holdout days are selectable and "
        "none is excluded; it is a starting point, not a filtered result."
    )

    st.divider()
    st.subheader("Which zones are forecast to be busiest?")
    time = st.select_slider("Forecast origin · local time", options=sorted(view.index.to_list()))
    ranking = forecast[forecast.timestamp == time][["zone_id", chosen]].copy()
    ranking["Zone"] = ranking.zone_id.map(names)
    st.bar_chart(ranking.set_index("Zone")[chosen].rename("Forecast pickups").sort_values(),
                 color=[BLUE], height=420, horizontal=True)
    st.caption("A pickup-volume ranking is not a relocation recommendation: existing supply and travel costs are missing.")

# ── Failure analysis ────────────────────────────────────────────────────────
with failure:
    st.subheader("Positive bias, and the pattern behind it")
    daily = forecast.groupby(forecast.timestamp.dt.date)[["pickups", "weekly_naive", chosen]].mean()
    daily["Gap"] = daily.pickups - daily.weekly_naive
    daily["Model bias"] = daily[chosen] - daily.pickups
    correlation = daily["Gap"].corr(daily["Model bias"])

    f1, f2, f3 = st.columns(3)
    f1.metric("Full-holdout model bias", f"{score['bias']:+.2f}", border=True,
              help="Overprediction, in pickups per zone per 30 minutes.")
    f2.metric("Weekly-gap / bias correlation", f"{correlation:.3f}", border=True,
              help="Across the 14 holdout days. Association only.")
    f3.metric("Selected day's bias", f"{daily.loc[day, 'Model bias']:+.2f}", border=True,
              help=f"All-zone average for {day}, the day chosen in the Forecast replay tab.")

    st.markdown(
        "The model overpredicts in **all 20 zones**. Day by day, that bias tracks how far the previous week's "
        "activity sits from the current week's: when last week ran *higher* than today, the model runs high too."
    )
    daily_out = (daily.rename(columns={"pickups": "Observed", "weekly_naive": "Previous week", chosen: "Model"})
                 .rename_axis("Date").reset_index())
    st.dataframe(
        daily_out, width="stretch", hide_index=True, height=530,
        column_config={
            "Date": st.column_config.DateColumn(format="ddd D MMM"),
            "Observed": st.column_config.NumberColumn(format="%.2f"),
            "Previous week": st.column_config.NumberColumn(format="%.2f"),
            "Model": st.column_config.NumberColumn(format="%.2f"),
            "Gap": st.column_config.NumberColumn(format="%+.2f", help="Observed minus previous week."),
            "Model bias": st.column_config.NumberColumn(format="%+.2f", help="Model minus observed."),
        },
    )
    st.markdown("**The two series, day by day**")
    st.line_chart(daily[["Gap", "Model bias"]], color=[AMBER, BLUE], height=260,
                  x_label="Holdout day", y_label="Pickups / zone / 30 min")
    st.caption(
        "All-zone daily averages — **not** the selected zone's error. Compare 2025-02-17 (gap −13.45, bias +5.16) "
        "with 2025-02-24 (gap +5.16, bias −1.29): the sign of the bias flips with the sign of the gap."
    )
    st.warning(
        "Post-hoc association, not causal proof. No lag ablation was run. "
        "Both quantities share the observed count with opposite signs, so correlation alone cannot isolate the mechanism. "
        "This holdout has been inspected: any diagnosis-driven change needs a fresh test period."
    )

    st.divider()
    st.subheader("Error by zone")
    by_zone = load_csv("by_zone.csv")
    wide = by_zone.pivot(index="Zone", columns="model", values="mae")
    wide["Model WAPE"] = by_zone[by_zone.model == chosen].set_index("Zone")["wape"]
    wide["Model bias"] = by_zone[by_zone.model == chosen].set_index("Zone")["bias"]
    wide = (wide.rename(columns={chosen: "Model MAE", "persistence": "Persistence MAE",
                                 "weekly_naive": "Previous-week MAE"})
            .sort_values("Model MAE", ascending=False)
            [["Model MAE", "Persistence MAE", "Previous-week MAE", "Model WAPE", "Model bias"]]
            .reset_index())
    st.dataframe(
        wide, width="stretch", hide_index=True, height=320,
        column_config={
            "Zone": st.column_config.TextColumn(width="medium"),
            "Model MAE": st.column_config.NumberColumn(format="%.2f"),
            "Persistence MAE": st.column_config.NumberColumn(format="%.2f"),
            "Previous-week MAE": st.column_config.NumberColumn(format="%.2f"),
            "Model WAPE": st.column_config.NumberColumn(format="percent"),
            "Model bias": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    st.caption(
        "Penn Station/Madison Sq West has the highest model MAE (18.12) and WAPE (21.64%); Lenox Hill West the "
        "lowest MAE (7.43); Midtown Center the lowest WAPE (11.47%) despite MAE 13.51 — scale changes the ranking. "
        "Transport-hub surges are a plausible hypothesis, not an established explanation. The model still beats "
        "both baselines in every zone."
    )

# ── Evidence & limits ───────────────────────────────────────────────────────
with evidence:
    st.subheader("What this does not establish")
    with st.container(border=True):
        st.markdown(
            "⚠️ **Completed-trip counts are not total demand** — this dataset has no rejected requests or live "
            "vehicle availability.\n\n"
            "⚠️ **Forecast accuracy is not evidence** of revenue uplift, reduced waiting time, or a causal "
            "fleet benefit.\n\n"
            "⚠️ **NYC winter taxi patterns are not validated London ride-hailing patterns.**\n\n"
            "⚠️ **Previous-bin pickup data is assumed available immediately**; real data latency needs testing."
        )

    st.subheader("Protocol")
    p1, p2 = st.columns(2)
    p1.markdown(
        "| Stage | Target timestamps (NYC local) |\n|---|---|\n"
        "| Zone selection / raw history | 1–31 Jan 2025 |\n"
        "| Training after lag warmup | 8–31 Jan 2025 |\n"
        "| Validation / model choice | 1–14 Feb 2025 |\n"
        "| Final holdout | 15–28 Feb 2025 |"
    )
    p2.markdown(
        "For a forecast at `t`, the label is pickups in `[t, t+30 min)`, and features use bins ending at or "
        "before `t`. All zones at a timestamp share a split. The recipe was fixed on validation, then refit on "
        "all pre-test data; holdout weights never change, while earlier observed test bins become history at "
        "later origins."
    )

    st.subheader("Error tables and raw predictions")
    st.markdown("**Error by day**")
    by_day = load_csv("by_day.csv")
    day_wide = by_day.pivot(index="date", columns="model", values="mae")
    day_wide["Model bias"] = by_day[by_day.model == chosen].set_index("date")["bias"]
    day_wide = (day_wide.rename(columns={chosen: "Model MAE", "persistence": "Persistence MAE",
                                         "weekly_naive": "Previous-week MAE"})
                [["Model MAE", "Persistence MAE", "Previous-week MAE", "Model bias"]]
                .rename_axis("Date").reset_index())
    st.dataframe(
        day_wide, width="stretch", hide_index=True, height=320,
        column_config={
            "Model MAE": st.column_config.NumberColumn(format="%.2f"),
            "Persistence MAE": st.column_config.NumberColumn(format="%.2f"),
            "Previous-week MAE": st.column_config.NumberColumn(format="%.2f"),
            "Model bias": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    d1, d2 = st.columns(2)
    d1.download_button("Download held-out predictions", (OUT / "predictions.csv.gz").read_bytes(),
                       file_name="fleetcast-heldout-predictions.csv.gz", mime="application/gzip",
                       width="stretch")
    d2.download_button("Download per-zone errors", (OUT / "by_zone.csv").read_bytes(),
                       file_name="fleetcast-by-zone.csv", mime="text/csv", width="stretch")

    with st.expander("Run protocol (metadata.json)"):
        st.json(meta["protocol"])
    with st.expander("Data provenance (source files and hashes)"):
        st.json(meta["data_provenance"])
