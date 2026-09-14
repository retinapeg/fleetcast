# Claude build/run assignment

Take this starter to a verified first real-data benchmark and an interview-ready
local dashboard. Execute the work rather than returning only a plan. Use the
existing implementation; do not restart the architecture.

Read CLAUDE.md, docs/BRIEF.md, README.md and docs/TEST_STATUS.md first.
You may install project dependencies into .venv and download the two named official
TLC Parquet files and the zone lookup. No paid APIs, publication, global config
changes, destructive Git commands, email or credential access.

1. Confirm the current directory and inspect the files. Use existing Ponytail
   guidance and Graphify only when already functional; otherwise read the source.
   Do not use /graphify blindly or graph the home folder. No tooling detour.
2. Run `uv sync` and keep the resulting uv.lock. If uv is missing from PATH,
   check the existing ~/.local/bin/uv install before asking for another install.
3. Run `uv run pytest -q`. The authoring environment skipped DuckDB and Streamlit
   dependency tests. With project dependencies installed these should run, not
   silently remain skipped. Fix real issues with small patches and new tests.
4. Run `uv run python -m fleetcast prepare`. Inspect source schemas and the
   resulting provenance.json, exclusion counts and complete-grid assumptions.
   On download failure, report it clearly; do not generate substitute scores.
5. Inspect the protocol BEFORE running the holdout. Confirm lags, zone selection,
   time boundaries and absence of random early stopping. Then run
   `uv run python -m fleetcast run` once. The result may favour a baseline.
6. Inspect REPORT.md, by_zone.csv, by_day.csv and the stored predictions. Compute
   the displayed headline numbers from the outputs; never hard-code desired gains.
7. Run a populated Streamlit smoke test and `uv run streamlit run app.py` locally.
   Check zone/day/time selectors, empty/error states, labels, tables and download.
   Do not leave multiple server processes running. Do not add a new frontend.
8. Update docs/INTERVIEW_NOTES.md with measured findings only. Keep the explanation
   in plain English/ASCII so the owner can learn it without writing LaTeX.
9. Write HANDOFF.md with exact commands, test counts including skips, output paths,
   actual measured scores, remaining limitations, and a three-minute walkthrough.
   Explicitly distinguish implemented, tested, untested and blocked components.

Stop here. Do not add relocation, RL, integrations or deployment. Do not keep
working until the number looks better. A first result is the beginning of an
analysis, not evidence that this solves an operator's fleet problem.

Do not ask about minor aesthetic preferences; use restrained readable defaults.
Ask only when a genuine safety/permission decision or irremediable blocker exists.
Do not claim Codex has reviewed anything. Leave its separate review task ready.
