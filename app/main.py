import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.gtfs_feed import get_current_alerts, FeedFetchError
from app.retrieval import AlertIndex
from app.llm import generate_answer

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("transit_rag")

index = AlertIndex()

# Tracks whether the last feed refresh attempt succeeded, so /health can
# report degraded state instead of just "up"/"down".
_feed_status = {"ok": False, "error": None, "last_attempt": None}


class AskResponse(BaseModel):
    answer: str
    alerts_last_updated: str | None
    stale: bool


def _refresh_feed_once() -> None:
    _feed_status["last_attempt"] = time.time()
    try:
        alerts = get_current_alerts()
        index.refresh(alerts)
        _feed_status["ok"] = True
        _feed_status["error"] = None
    except FeedFetchError as exc:
        # Don't crash the app or wipe out the last-known-good alerts —
        # serve stale data rather than nothing.
        _feed_status["ok"] = False
        _feed_status["error"] = str(exc)
        logger.error("Feed refresh failed, serving stale data: %s", exc)


async def _refresh_loop() -> None:
    while True:
        await asyncio.get_event_loop().run_in_executor(None, _refresh_feed_once)
        await asyncio.sleep(settings.FEED_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    # Do the first fetch synchronously so /ask has data as soon as the app
    # reports ready, then kick off periodic background refreshes.
    _refresh_feed_once()
    refresh_task = asyncio.create_task(_refresh_loop())
    yield
    refresh_task.cancel()


app = FastAPI(title="Transit Alert RAG Assistant", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok" if index.is_ready else "starting",
        "feed_ok": _feed_status["ok"],
        "feed_error": _feed_status["error"],
        "alerts_last_updated": index.last_updated.isoformat() if index.last_updated else None,
    }


@app.get("/ask", response_model=AskResponse)
def ask_endpoint(question: str = Query(..., min_length=1, max_length=500)):
    context = index.find_closest(question)

    if context is None:
        # No alerts in the index at all (feed empty or never loaded yet) —
        # this is a real state, not an error, so don't 500.
        answer = "I don't know"
    else:
        try:
            answer = generate_answer(question, context)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise HTTPException(status_code=502, detail="Answer generation failed, try again shortly")

    return AskResponse(
        answer=answer,
        alerts_last_updated=index.last_updated.isoformat() if index.last_updated else None,
        stale=not _feed_status["ok"],
    )
