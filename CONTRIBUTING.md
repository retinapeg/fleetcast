# Contributing

### Setup and checks

```bash
uv sync
uv run pytest -q
```

Python 3.12 is requested by `.python-version`. Model fitting in the tests uses
synthetic fixtures only; real TLC data is fetched by `uv run python -m fleetcast prepare`.

### Scope and integrity rules

Priority: valid problem definition, as-of features, chronological evaluation,
reproducible numbers, honest claims, then UI clarity. More code is not a success metric.

- Keep the existing stack: Python, DuckDB SQL, pandas, scikit-learn, Streamlit.
  No new frameworks, and no LLM calls, RL or simulation inside the product.
- Respect the predeclared splits and data-availability assumptions. Never use
  holdout results for feature selection or tuning while still calling that
  holdout untouched. A strong baseline winning is an acceptable result.
- Do not remove tests, shrink the evaluated data to improve a score, invent
  metrics or substitute synthetic data outside explicit tests.
- `artifacts/first-run/` is the frozen evidence set. A reproduction uses a new
  output directory (`--output artifacts/reproduction`) and is labelled a repeat of
  an already-examined holdout, not a new experiment.
