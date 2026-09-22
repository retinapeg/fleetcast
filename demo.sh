#!/bin/zsh
# FleetCast demo launcher.
# Read-only: starts the dashboard on the frozen first-run artifacts.
# It never downloads, prepares, trains or writes into artifacts/ or data/.
set -u
cd "$(dirname "$0")"

PORT="${FLEETCAST_PORT:-8599}"
HOST=127.0.0.1
OUT=artifacts/first-run
PY=.venv/bin/streamlit

fallback() {
  print -r -- ""
  print -r -- "FALLBACK — do not improvise scores. Present from the saved evidence:"
  print -r -- "  open $OUT/REPORT.md docs/DEMO_CARD.md docs/WALKTHROUGH.md"
  exit 1
}

# --- Pre-flight: environment -------------------------------------------------
if [[ ! -x "$PY" ]]; then
  print -r -- "MISSING: $PY (project environment not installed)."
  print -r -- "Recover with: uv sync"
  fallback
fi

# --- Pre-flight: frozen evidence --------------------------------------------
missing=()
for f in metrics.json metadata.json predictions.csv.gz zones.csv by_zone.csv by_day.csv; do
  [[ -f "$OUT/$f" ]] || missing+=("$OUT/$f")
done
if (( ${#missing[@]} )); then
  print -r -- "MISSING benchmark evidence:"
  for f in "${missing[@]}"; do print -r -- "  $f"; done
  print -r -- "Recover with: uv run python -m fleetcast prepare && uv run python -m fleetcast run"
  fallback
fi

# --- Pre-flight: port --------------------------------------------------------
if lsof -ti ":$PORT" >/dev/null 2>&1; then
  print -r -- "Port $PORT is already in use by PID(s): $(lsof -ti ":$PORT" | tr '\n' ' ')"
  print -r -- "Reusing it is unsafe for a live demo (it may be a stale FleetCast)."
  print -rn -- "Kill it and continue? [y/N] "
  read -r reply
  if [[ "$reply" == [yY] ]]; then
    lsof -ti ":$PORT" | xargs kill 2>/dev/null
    sleep 1
  else
    PORT=$((PORT + 1))
    print -r -- "Using port $PORT instead."
  fi
fi

# --- Launch ------------------------------------------------------------------
URL="http://$HOST:$PORT"
print -r -- "FleetCast — historical holdout replay (15-28 Feb 2025, 13,440 predictions)"
print -r -- "Starting dashboard on $URL  ·  stop with Ctrl-C"

"$PY" run app.py \
  --server.address "$HOST" --server.port "$PORT" \
  --server.headless true --browser.gatherUsageStats false &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' INT TERM

# --- Wait for readiness, then open the browser -------------------------------
ready=0
for _ in {1..30}; do
  if ! kill -0 $SERVER 2>/dev/null; then
    print -r -- "The Streamlit process exited before becoming ready."
    fallback
  fi
  if curl -fsS -o /dev/null "$URL/healthz" 2>/dev/null; then ready=1; break; fi
  sleep 1
done

if (( ready )); then
  print -r -- "Ready. Opening $URL"
  open "$URL" 2>/dev/null || print -r -- "Open $URL manually."
else
  print -r -- "Server did not report healthy within 30s."
  kill $SERVER 2>/dev/null
  fallback
fi

wait $SERVER
