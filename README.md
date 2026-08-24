# 🚇 Transit Alert RAG Assistant

A Retrieval-Augmented Generation (RAG) service that answers natural-language questions about live NYC subway service alerts, built as a production-style FastAPI backend with a Streamlit chat frontend, tested and deployed via CI/CD to AWS EC2.

**Ask it things like:**

> "Is the L train delayed?"
> "Are any stops being skipped on the 7 train?"
> "Any weekend service changes?"

...and get answers grounded in the actual live MTA GTFS-Realtime feed — not a hallucinated guess.

---

## How it works

```
MTA GTFS-Realtime feed (protobuf)
        │
        ▼
  Fetch + parse alerts ──► Embed with sentence-transformers ──► In-memory vector index
        │                                                              │
        │                                                              ▼
        │                                                  User question → nearest alert
        │                                                              │
        └──────────────────────────────────────────────────────────────┘
                                                                        │
                                                                        ▼
                                                        Gemini generates a grounded answer
                                                                        │
                                                                        ▼
                                                        FastAPI /ask ──► Streamlit chat UI
```

The alert index refreshes automatically in the background every 60 seconds, so answers stay current without needing a restart.

## Architecture

The service is split by responsibility rather than living in one script:

| File               | Responsibility                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `app/config.py`    | Environment variables, constants, startup validation                                                                     |
| `app/gtfs_feed.py` | Fetches and parses the MTA GTFS-Realtime feed, with retry logic on network failures                                      |
| `app/retrieval.py` | `AlertIndex` — thread-safe embedding store with atomic refresh, so background updates never race with in-flight requests |
| `app/llm.py`       | Gemini API wrapper with retry logic                                                                                      |
| `app/main.py`      | FastAPI app — wires everything together, runs the background refresh loop, exposes `/ask` and `/health`                  |
| `streamlit_app.py` | Chat-style frontend for demoing the assistant locally                                                                    |

## Testing

19 automated tests (`pytest`), covering:

- GTFS-RT parsing edge cases (missing fields, non-English translations, malformed protobuf bytes)
- Retrieval correctness (nearest-neighbor matching, atomic refresh behavior, empty-index handling)
- API integration (successful answers, LLM failure handling, input validation, stale-data flagging)

Tests run with a faked embedding model and no real network calls, completing in well under 30 seconds. CI runs the full suite on every push and **blocks the build/deploy pipeline if any test fails.**

## CI/CD

GitHub Actions pipeline: **test → build & push Docker image → deploy to EC2**, fully automated on every push to `main`. See [`.github/workflows/`](.github/workflows/).

## Running it locally

**Backend:**

```bash
pip install -r requirements.txt
export MTA_API_KEY=your_mta_key
export GEMINI_API_KEY=your_gemini_key
python -m uvicorn app.main:app --reload
```

**Frontend:**

```bash
pip install streamlit
streamlit run streamlit_app.py
```

**Tests:**

```bash
pytest tests/ -v
```

## Tech stack

FastAPI · sentence-transformers · Google Gemini · GTFS-Realtime (protobuf) · Docker · GitHub Actions · AWS EC2 · Streamlit · pytest
