"""Read-only, single-page historical replay. No data or training on page load."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "first-run"

LABELS = {"pickups": "Observed", "boosted_trees": "Model", "persistence": "Persistence",
          "weekly_naive": "Previous week"}
INK, BLUE, GREY, AMBER = "#0f172a", "#2563eb", "#94a3b8", "#f59e0b"

# Calendar notes for the holdout day selector. Labels only: naming a day is not a
# claim that the holiday caused the error.
DAY_NOTES = {date(2025, 2, 17): "Presidents' Day",
             date(2025, 2, 24): "following Monday"}

st.set_page_config(page_title="FleetCast | Pickup forecasting", page_icon="🚕", layout="wide")
st.html("""<style>
  .block-container {padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px;}
  [data-testid="stMetricValue"] {font-size: 1.9rem;}
  [data-testid="stMetricLabel"] {opacity: .75;}
  h1 {margin-bottom: .1rem;} h3 {margin-top: .4rem;}
  /* The headline result dominates the first screen. */
  .st-key-hero [data-testid="stMetricValue"] {font-size: 3.6rem; line-height: 1.05;}
  .st-key-hero [data-testid="stMetricLabel"] {font-size: 1rem; opacity: .9;}
  .st-key-hero [data-testid="stMetricDelta"] {font-size: 1.05rem;}
  .hero-compare {font-size: 1.3rem; line-height: 1.8; font-weight: 600; margin: .1rem 0 .3rem;}
  .hero-lower {font-size: .99rem; opacity: .8; margin-top: .5rem;}
  /* Plain HTML bars: a like-for-like MAE comparison that costs no chart element. */
  .bar-row {display: flex; align-items: center; gap: .75rem; margin: .38rem 0;}
  .bar-name {width: 210px; flex: none; text-align: right; font-size: .95rem;}
  .bar-track {flex: 1; background: #eef2f6; border-radius: 5px; height: 27px;}
  .bar-fill {height: 100%; border-radius: 5px;}
  .bar-val {width: 58px; flex: none; font-weight: 700; font-size: 1.02rem;
            font-variant-numeric: tabular-nums;}
  /* The question and the answer own the first screen. */
  .qa-tag {font-size: .78rem; letter-spacing: .14em; text-transform: uppercase;
           font-weight: 700; opacity: .55; margin-bottom: .15rem;}
  .qa-q {font-size: 1.62rem; line-height: 1.34; font-weight: 700; margin: 0 0 .5rem;}
  .qa-explain {font-size: 1.02rem; line-height: 1.55; opacity: .82; margin: 0 0 .2rem;}
  .qa-a {font-size: 1.22rem; line-height: 1.55; margin: 0;}
  .qa-yes {color: #15803d; font-weight: 800;}
  .qa-chips {font-size: .93rem; opacity: .78; margin-top: .5rem;}
  /* What did we learn: three short points, not paragraphs. */
  .tk {border-left: 4px solid #2563eb; padding: .1rem 0 .1rem .8rem; height: 100%;}
  .tk h4 {margin: 0 0 .3rem; font-size: .85rem; letter-spacing: .09em;
          text-transform: uppercase; opacity: .8; font-weight: 700;}
  .tk p {margin: 0; font-size: .96rem; line-height: 1.5;}
  .tk-amber {border-left-color: #f59e0b;}
</style>""")


@st.cache_data(show_spinner=False)
def load_json(name: str):
    return json.loads((OUT / name).read_text())


@st.cache_data(show_spinner=False)
def load_csv(name: str, parse_dates: tuple[str, ...] = ()):
    return pd.read_csv(OUT / name, parse_dates=list(parse_dates))


# ── 1 · Header ──────────────────────────────────────────────────────────────
st.title("FleetCast")
st.caption("30-minute Manhattan taxi pickup forecasting · NYC yellow taxis · Independent mobility case study")

required = ["metrics.json", "metadata.json", "predictions.csv.gz", "zones.csv", "by_zone.csv", "by_day.csv"]
if any(not (OUT / name).exists() for name in required):
    st.warning("No completed real-data benchmark yet. No illustrative scores are being substituted.")
    st.code("uv run python -m fleetcast prepare\nuv run python -m fleetcast run", language="bash")
    st.stop()

scores = load_json("metrics.json")
meta = load_json("metadata.json")
if meta.get("data_provenance", {}).get("data_is_synthetic") is not False:
    st.error("This view requires verified real-data results.")
    st.stop()

forecast = load_csv("predictions.csv.gz", ("timestamp",))
zones = load_csv("zones.csv")
chosen = scores["recommended_model_from_validation"]
score, base, weekly = (scores["test"][k] for k in (chosen, "persistence", "weekly_naive"))
gain_base = 1 - score["mae"] / base["mae"]
gain_weekly = 1 - score["mae"] / weekly["mae"]

# Daily aggregates drive both the first-screen failure summary and the failure tab.
daily = forecast.groupby(forecast.timestamp.dt.date)[["pickups", "weekly_naive", chosen]].mean()
daily["Gap"] = daily.pickups - daily.weekly_naive
daily["Model bias"] = daily[chosen] - daily.pickups
correlation = daily["Gap"].corr(daily["Model bias"])

st.info("HISTORICAL HOLDOUT REPLAY — not live demand, a dispatch system, or Odysse fleet data.", icon="🗄️")

# ── 2 · The question ────────────────────────────────────────────────────────
st.markdown(
    '<div class="qa-tag">Question</div>'
    '<div class="qa-q">Can we predict yellow-taxi pickups in each Manhattan zone 30 minutes '
    "ahead, better than simple time-series baselines?</div>"
    f'<div class="qa-explain">For each of {len(zones)} Manhattan zones, FleetCast predicts the number of '
    "completed yellow-taxi pickups in the next half-hour using only information available "
    "beforehand.</div>",
    unsafe_allow_html=True,
)
st.divider()

# ── 3 · The answer ──────────────────────────────────────────────────────────
with st.container(key="hero"):
    st.markdown('<div class="qa-tag">Answer</div>', unsafe_allow_html=True)
    headline, answer = st.columns([2, 3], vertical_alignment="center")
    headline.metric(
        "Model MAE", f"{score['mae']:.2f}",
        delta=f"{-gain_base:.1%} vs persistence", delta_color="inverse", border=True,
        help="Mean absolute error in pickups per zone per 30 minutes.",
    )
    answer.markdown(
        f'<div class="qa-a"><span class="qa-yes">YES</span> — on an unseen two-week holdout the model '
        f"reaches <b>MAE {score['mae']:.2f}</b>: <b>{gain_base:.0%} lower</b> than persistence and "
        f"<b>{gain_weekly:.0%} lower</b> than using the previous week.</div>"
        f'<div class="qa-chips">Holdout <b>15–28 Feb 2025</b> &nbsp;·&nbsp; <b>{len(forecast):,}</b> '
        "predictions &nbsp;·&nbsp; <b>Lower is better</b></div>",
        unsafe_allow_html=True,
    )

    # Like-for-like MAE bars, drawn in HTML so the page keeps its four real charts.
    bars = [("Model · Poisson boosted trees", score["mae"], BLUE),
            ("Persistence baseline", base["mae"], GREY),
            ("Previous week baseline", weekly["mae"], AMBER)]
    longest = max(mae for _, mae, _ in bars)
    st.markdown(
        "".join(
            f'<div class="bar-row"><div class="bar-name">{name}</div>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{mae / longest:.1%}; background:{colour};"></div></div>'
            f'<div class="bar-val">{mae:.2f}</div></div>'
            for name, mae, colour in bars
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Mean absolute error, **lower is better** · identical {len(forecast):,} rows for all three methods · "
        "pickups per zone per 30 minutes. The baselines are the honest things to beat: carry the last "
        "half-hour forward, or reuse the same half-hour a week ago."
    )

# ── What did we learn? ──────────────────────────────────────────────────────
st.markdown("#### What did we learn?")
t1, t2, t3 = st.columns(3)
t1.markdown(
    '<div class="tk"><h4>1 · Result</h4><p>The model beats both temporal baselines.</p></div>',
    unsafe_allow_html=True)
t2.markdown(
    f'<div class="tk tk-amber"><h4>2 · Failure</h4><p>Performance degrades around irregular weeks, when the '
    f"weekly-lag signal goes stale. Holdout bias <b>{score['bias']:+.2f}</b>; day-level bias is strongly "
    f"<i>associated</i> with weekly-lag mismatch (r = {correlation:.3f} across {len(daily)} days) — "
    "association, not causal proof.</p></div>", unsafe_allow_html=True)
t3.markdown(
    '<div class="tk"><h4>3 · Limitation</h4><p>Completed pickups are observed trips, not total latent demand. '
    "Lower forecast error does not prove shorter waits or higher revenue.</p></div>",
    unsafe_allow_html=True)
st.write("")

with st.expander("Full metric table — RMSE, WAPE, bias and both baselines"):
    b1, b2, b3 = st.columns(3)
    b1.metric("Persistence MAE", f"{base['mae']:.2f}", border=True, help="Previous half-hour, carried forward.")
    b2.metric("Previous-week MAE", f"{weekly['mae']:.2f}", border=True, help="Same half-hour, seven days earlier.")
    b3.metric("Model WAPE", "N/A" if score["wape"] is None else f"{score['wape']:.1%}", border=True,
              help="Absolute error as a share of observed volume.")

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
        f"Same {len(forecast):,} rows for all three methods. Bias = predicted minus observed; positive means "
        f"overprediction. Model **{chosen}**, selected on validation before the test was scored."
    )

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Mean absolute error by method** — lower is better")
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
            f"- One two-week holdout. No confidence interval or significance test was run, and {len(forecast):,} "
            "zone-bins are not independent samples."
        )

# ── 3 · Forecast · 4 · Failure · 5 & 6 · Method ─────────────────────────────
replay, failure, method = st.tabs(
    ["📈 Forecast", "🔍 Where does the model fail?", "📋 Method & evidence"])

# ── 3 · Main visual: actual vs forecast ─────────────────────────────────────
with replay:
    names = dict(zip(zones["LocationID"], zones["Zone"]))
    days = sorted(forecast["timestamp"].dt.date.unique())
    # One sign convention only — Gap = observed minus previous week, as in the failure tab.
    # The main demonstration opens on the most ORDINARY day: the smallest weekly gap, i.e.
    # the week that behaved most like the one before it. Its mirror image, the largest gap,
    # is the failure case in the next tab. Both derived, neither a fixed date.
    opening = daily["Gap"].abs().idxmin()
    worst_day = daily["Gap"].abs().idxmax()
    # Likewise the zone whose held-out MAE sits closest to the overall model MAE.
    zone_mae = (forecast[chosen] - forecast.pickups).abs().groupby(forecast.zone_id).mean()
    default_zone = int((zone_mae - score["mae"]).abs().idxmin())

    def day_label(d: date) -> str:
        note = DAY_NOTES.get(d)
        return f"{d:%a %-d %b %Y}" + (f" · {note}" if note else "")

    st.subheader("Actual vs forecast")
    st.caption("Pick a zone and a holdout day. Every forecast uses only earlier observed bins.")
    st.markdown(
        f"Opens on a **representative** example — {day_label(opening)} is the holdout day whose weekly "
        f"reference was least out of step, and {names[default_zone]} is the zone whose held-out error sits "
        "closest to the overall model MAE. Neither was picked by eye."
    )
    pick_zone, pick_day = st.columns(2)
    zone = pick_zone.selectbox("① Taxi zone", sorted(names), index=sorted(names).index(default_zone),
                               format_func=lambda z: f"{names[z]} · {z}")
    day = pick_day.selectbox("② Holdout day · New York local time", days, index=days.index(opening),
                             format_func=day_label)

    view = forecast[(forecast.zone_id == zone) & (forecast.timestamp.dt.date == day)].set_index("timestamp")
    head, toggle = st.columns([3, 1], vertical_alignment="bottom")
    head.markdown(f"### {names[zone]} · {day_label(day)}")
    with_baselines = toggle.toggle("Show baselines", value=True,
                                   help="Persistence and the previous-week reference, on the same axis.")
    columns = ["pickups", chosen] + (["persistence", "weekly_naive"] if with_baselines else [])
    palette = [INK, BLUE] + ([GREY, AMBER] if with_baselines else [])
    st.line_chart(view[columns].rename(columns=LABELS), color=palette, height=400,
                  x_label="Forecast origin · New York local time", y_label="Pickups per 30 minutes")

    m1, m2, m3 = st.columns(3)
    m1.metric("Bins shown", f"{len(view)}")
    m2.metric("Model MAE here", f"{(view[chosen] - view.pickups).abs().mean():.2f}")
    m3.metric("Model bias here", f"{(view[chosen] - view.pickups).mean():+.2f}")
    st.caption(
        "These three numbers describe **this zone and day only** — not the full-period score. "
        "Each forecast uses only earlier observed bins: one-step-ahead replay, not a two-week-ahead prediction. "
        f"The day selector opens on **{day_label(opening)}**, the holdout day whose previous-week reference is "
        f"*least* out of step with observed activity (weekly gap {daily.loc[opening, 'Gap']:+.2f}, observed minus "
        f"previous week, in pickups / zone / 30 min); the worst-aligned day is {day_label(worst_day)} at "
        f"{daily.loc[worst_day, 'Gap']:+.2f}. All {len(days)} holdout days are selectable and none is excluded. "
        "Holiday names in the selector are calendar labels, not an explanation of the error."
    )

    st.markdown(
        f"**See where the model fails →** open the **🔍 Where does the model fail?** tab, or pick "
        f"**{day_label(worst_day)}** above and compare it with **{day_label(date(2025, 2, 24))}**."
    )

    with st.expander("Which zones are forecast to be busiest at a given moment?"):
        options = sorted(view.index.to_list())
        midday = next((t for t in options if t.hour == 12 and t.minute == 0), options[0])
        time = st.select_slider("Forecast origin · local time", options=options, value=midday)
        ranking = forecast[forecast.timestamp == time][["zone_id", chosen]].copy()
        ranking["Zone"] = ranking.zone_id.map(names)
        st.bar_chart(ranking.set_index("Zone")[chosen].rename("Forecast pickups").sort_values(),
                     color=[BLUE], height=420, horizontal=True)
        st.caption("A pickup-volume ranking is not a relocation recommendation: existing supply and "
                   "travel costs are missing.")

# ── 4 · Where does the model fail? ──────────────────────────────────────────
with failure:
    st.subheader("Where does the model fail?")
    f1, f2, f3 = st.columns(3)
    f1.metric("Full-holdout model bias", f"{score['bias']:+.2f}", border=True,
              help="Overprediction, in pickups per zone per 30 minutes.")
    f2.metric("Weekly-gap / bias correlation", f"{correlation:.3f}", border=True,
              help=f"Across the {len(daily)} holdout days. Association only.")
    f3.metric("Selected day's bias", f"{daily.loc[day, 'Model bias']:+.2f}", border=True,
              help=f"All-zone average for {day}, the day chosen in the Forecast tab.")

    st.markdown(
        f"**The model overpredicts in all {len(zones)} zones** — holdout bias **{score['bias']:+.2f}** pickups per "
        f"zone per 30 minutes. Day to day that bias moves **opposite** to the weekly gap (observed minus previous "
        f"week): **r = {correlation:.3f}** across {len(daily)} days. When last week ran *higher* than today, the "
        "model runs high too. Both quantities contain today's count, so part of that sign is arithmetic."
    )

    a, b = (date(2025, 2, 17), date(2025, 2, 24))
    if a in daily.index and b in daily.index:
        widest_positive = daily["Gap"].idxmax()
        same_sign = int(((daily["Gap"] > 0) & (daily["Model bias"] > 0)).sum())
        st.markdown(
            "| Holdout day | Weekly gap (observed − previous week) | All-zone model bias |\n|---|---:|---:|\n"
            f"| **{a:%a %-d %b}** · {DAY_NOTES[a]} | {daily.loc[a, 'Gap']:+.2f} | "
            f"**{daily.loc[a, 'Model bias']:+.2f}** |\n"
            f"| **{b:%a %-d %b}** · {DAY_NOTES[b]} | {daily.loc[b, 'Gap']:+.2f} | "
            f"**{daily.loc[b, 'Model bias']:+.2f}** |\n\n"
            f"**{a:%-d %b}** carries the largest weekly gap of the {len(daily)} days; **{b:%-d %b}** is the "
            "contrasting Monday with the gap reversed. They illustrate the pattern rather than prove it: the "
            f"largest *positive* gap is {widest_positive:%-d %b}, and on {same_sign} days gap and bias share a "
            "sign. Select either day in the **Forecast** tab to watch it zone by zone."
        )

    st.markdown("**The two series, day by day**")
    st.line_chart(daily[["Gap", "Model bias"]], color=[AMBER, BLUE], height=280,
                  x_label="Holdout day", y_label="Pickups / zone / 30 min")
    st.warning(
        "Association, not causal proof. No lag ablation was run. "
        "Both quantities share the observed count with opposite signs, so correlation alone cannot isolate the "
        "mechanism, and naming a day a public holiday does not establish that the holiday caused the error. "
        "This holdout has been inspected: any diagnosis-driven change needs a fresh test period."
    )

    with st.expander("Day-by-day table — all 14 holdout days"):
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
        st.caption("All-zone daily averages — **not** the selected zone's error.")

    with st.expander("Error by zone — where the model struggles spatially"):
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
            "lowest MAE (7.43); Midtown Center the lowest WAPE (11.47%) despite MAE 13.51 — scale changes the "
            "ranking. Transport-hub surges are a plausible hypothesis, not an established explanation. The model "
            "still beats both baselines in every zone."
        )

# ── 5 · Methodology · 6 · Technical detail ──────────────────────────────────
with method:
    st.subheader("How it was built")
    s1, s2 = st.columns(2)
    s1.markdown(
        "**Chronological splits**\n\n"
        "| Stage | Dates (NYC local) |\n|---|---|\n"
        "| Train | 8–31 Jan 2025 |\n"
        "| Validation | 1–14 Feb 2025 |\n"
        "| Holdout | 15–28 Feb 2025 |\n\n"
        "Zone selection used January only."
    )
    s2.markdown(
        "**Target**\n\n"
        "Observed pickups per zone in the next 30 minutes.\n\n"
        "**Model**\n\n"
        "Poisson gradient-boosted trees.\n\n"
        "**Baselines**\n\n"
        "Persistence · weekly naive."
    )

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

    with st.expander("Detailed protocol"):
        st.markdown(
            "For a forecast at `t`, the label is pickups in `[t, t+30 min)`, and features use bins ending at or "
            "before `t`: previous half-hour, previous hour, previous day, previous week and shifted rolling means, "
            "plus calendar and categorical zone features. All zones at a timestamp share a split. The recipe was "
            "fixed on validation, then refit on all pre-test data; holdout weights never change, while earlier "
            "observed test bins become history at later origins. This is rolling one-step-ahead evaluation, not a "
            "simultaneous prediction of the whole fortnight."
        )
        st.json(meta["protocol"])

    with st.expander("Data provenance — source files, byte counts and SHA-256 hashes"):
        st.json(meta["data_provenance"])

    with st.expander("Complete metrics — validation and test, every method"):
        st.json(scores)

    with st.expander("Error by day, and raw prediction downloads"):
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
