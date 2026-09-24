import json
from datetime import date
from pathlib import Path
import pytest


def test_app_empty_state(tmp_path):
    pytest.importorskip("streamlit", reason="Streamlit not installed in this environment")
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    # Exercise the missing-artifact branch without moving or modifying real evidence.
    isolated_app = tmp_path / "app.py"
    isolated_app.write_text((root / "app.py").read_text())
    app = AppTest.from_file(str(isolated_app)).run(timeout=30)
    assert not app.exception
    assert len(app.warning) == 1


def test_app_populated_state():
    pytest.importorskip("streamlit", reason="Streamlit not installed in this environment")
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    if not (root / "artifacts" / "first-run" / "metrics.json").exists():
        pytest.skip("No real benchmark yet; the empty-state test covers this case")
    app = AppTest.from_file(str(root / "app.py")).run(timeout=90)
    assert not app.exception
    assert not app.error
    scores = json.loads((root / "artifacts" / "first-run" / "metrics.json").read_text())
    chosen = scores["recommended_model_from_validation"]
    test = scores["test"]

    # Headline KPIs: model, both baselines, WAPE — all read from the metrics file,
    # never hard-coded in the page.
    headline = {m.label: m.value for m in app.metric}
    assert headline["Model MAE"] == f"{test[chosen]['mae']:.2f}"
    assert headline["Persistence MAE"] == f"{test['persistence']['mae']:.2f}"
    assert headline["Previous-week MAE"] == f"{test['weekly_naive']['mae']:.2f}"
    assert headline["Model WAPE"] == f"{test[chosen]['wape']:.1%}"
    gain = 1 - test[chosen]["mae"] / test["persistence"]["mae"]
    assert app.metric[0].delta == f"{-gain:.1%} vs persistence"
    assert headline["Full-holdout model bias"] == f"{test[chosen]['bias']:+.2f}"

    # Four tabs' content all renders in one pass: results, replay, failure, evidence.
    assert len(app.selectbox) == 2
    assert len(app.selectbox[0].options) == 20
    assert len(app.selectbox[1].options) == 14
    assert len(app.dataframe) == 4
    assert len(app.get("vega_lite_chart")) == 4
    # The main demonstration opens on the derived MOST TYPICAL day (smallest absolute
    # weekly gap), not the failure case; the failure walkthrough is one tab away.
    assert app.selectbox[1].value == date(2025, 2, 27)

    # Real saved-artifact replay: no training or downloads. Exercise reruns, not just defaults.
    for zone, day, bias in [(186, date(2025, 2, 17), 5.157693503768236),
                            (140, date(2025, 2, 24), -1.2918080907197265)]:
        app.selectbox[0].set_value(zone)
        app.selectbox[1].set_value(day).run(timeout=60)
        assert not app.exception and not app.error
        assert app.selectbox[0].value == zone
        assert app.selectbox[1].value == day
        # The failure tab reports the all-zone daily bias for the selected day.
        assert {m.label: m.value for m in app.metric}["Selected day's bias"] == f"{bias:+.2f}"
        daily = app.dataframe[1].value.set_index("Date")
        assert daily.loc[day, "Model bias"] == pytest.approx(bias)
        assert len(app.get("vega_lite_chart")) == 4
        app.select_slider[0].set_value(app.select_slider[0].value.replace(hour=12)).run(timeout=60)
        assert not app.exception and not app.error
    app.toggle[0].set_value(False).run(timeout=60)
    assert not app.exception and not app.error
    assert len(app.get("vega_lite_chart")) == 4
    assert "No lag ablation" in app.warning[0].value
