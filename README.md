# Transit Alert RAG Assistant

## What changed from the original single-file version

The original `main.py` fetched the GTFS-RT feed and built embeddings once,
at module import time, with no error handling. That meant alerts never
updated after startup, and any hiccup in the MTA API or malformed feed data
would crash the whole process before it ever came up.

This version splits things into testable pieces:

- **`app/config.py`** — env vars and constants in one place, with a
  `validate()` that fails fast (and loudly) if API keys are missing,
  instead of failing confusingly later.
- **`app/gtfs_feed.py`** — fetching (`fetch_raw_feed`, with retries via
  `tenacity`) and parsing (`parse_alert_strings`) as separate, pure-ish
  functions. Parsing skips malformed/empty entities instead of crashing on
  one bad alert.
- **`app/retrieval.py`** — `AlertIndex` wraps the embedding model + vectors
  behind a thread-safe `refresh()` / `find_closest()` interface, so a
  background thread can swap in new alerts while a request is being
  served, atomically.
- **`app/llm.py`** — Gemini calls isolated with retry logic.
- **`app/main.py`** — wires it together. On startup, does one synchronous
  feed fetch (so `/ask` has data immediately), then refreshes every
  `FEED_REFRESH_INTERVAL_SECONDS` (default 60s) in the background. If a
  refresh fails, it logs the error and **keeps serving the last known
  alerts** rather than crashing or going blank — `/ask` responses include
  `"stale": true` when that's happening, and `/health` reports the feed
  status separately from whether the process is up.

## Running locally

```bash
pip install -r requirements.txt
export MTA_API_KEY=your_key
export GEMINI_API_KEY=your_key
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest tests/ -v
```

19 tests, no network access or real model downloads required — the
embedding model is faked out in `tests/conftest.py`, and the MTA feed is
either built in-memory (`test_gtfs_feed.py`) or monkeypatched
(`test_api.py`).

## What this doesn't cover yet (next steps)

- **Persistent vector store.** Embeddings are still recomputed in memory on
  every refresh cycle. Fine for a few hundred alerts; if you want this to
  survive restarts without recomputing, or scale past one instance, move to
  something like `chromadb` or Postgres + `pgvector`.
- **Metadata filtering.** `find_closest` is still a single brute-force
  nearest-neighbor search over all alerts. If you want to fix the
  documented "symbolic query mismatch on train-line lookups" issue, the
  real fix is tagging alerts with the line(s) they mention and filtering
  before the semantic search, not just a bigger model.
- **Auth / rate limiting** on `/ask` if this is publicly reachable — right
  now anyone hitting the endpoint burns your Gemini quota.
- **Metrics** (`/metrics` + Prometheus) beyond the basic `/health` check.
