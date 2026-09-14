import json
from pathlib import Path
import pytest


def test_app_empty_state():
    pytest.importorskip("streamlit", reason="Streamlit not installed in the artifact authoring environment")
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    if (root / "artifacts" / "first-run" / "metrics.json").exists():
        pytest.skip("Real benchmark exists; verify the populated app separately")
    app = AppTest.from_file(str(root / "app.py")).run(timeout=30)
    assert not app.exception
    assert len(app.warning) == 1


def test_app_populated_state():
    pytest.importorskip("streamlit", reason="Streamlit not installed in the artifact authoring environment")
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    if not (root / "artifacts" / "first-run" / "metrics.json").exists():
        pytest.skip("No real benchmark yet; the empty-state test covers this case")
    app = AppTest.from_file(str(root / "app.py")).run(timeout=60)
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 3
    assert len(app.selectbox) == 2
    assert len(app.selectbox[0].options) == 20
    assert len(app.selectbox[1].options) == 14
    assert len(app.dataframe) == 3
    # The displayed headline must be the measured score, never a hard-coded one.
    scores = json.loads((root / "artifacts" / "first-run" / "metrics.json").read_text())
    chosen = scores["recommended_model_from_validation"]
    assert app.metric[0].value == chosen
    assert app.metric[1].value.startswith(f"{scores['test'][chosen]['mae']:.2f}")
