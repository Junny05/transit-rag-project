import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class AlertIndex:
    """Holds the current set of alerts and their embeddings.

    Thread-safe swap-in-place refresh: a background thread can call
    `refresh()` with a new alert list while request-handling threads call
    `find_closest()`, without either seeing a half-updated state.
    """

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL, model=None):
        # `model` param allows tests to inject a fake/lightweight model
        # instead of loading the real SentenceTransformer weights.
        self._model = model if model is not None else SentenceTransformer(model_name)
        self._lock = threading.Lock()
        self._alert_strings: List[str] = []
        self._embeddings: Optional[np.ndarray] = None
        self._last_updated: Optional[datetime] = None

    def refresh(self, alert_strings: List[str]) -> None:
        """Recompute embeddings for a new list of alerts and swap them in."""
        if alert_strings:
            new_embeddings = self._model.encode(alert_strings)
        else:
            new_embeddings = np.empty((0, self._model.get_sentence_embedding_dimension()))

        with self._lock:
            self._alert_strings = alert_strings
            self._embeddings = new_embeddings
            self._last_updated = datetime.now(timezone.utc)

        logger.info("Alert index refreshed: %d alerts", len(alert_strings))

    @property
    def last_updated(self) -> Optional[datetime]:
        with self._lock:
            return self._last_updated

    @property
    def is_ready(self) -> bool:
        with self._lock:
            return self._embeddings is not None

    def find_closest(self, query: str) -> Optional[str]:
        """Return the single closest alert string to the query, or None if
        the index is empty (e.g. no active alerts right now)."""
        with self._lock:
            alert_strings = self._alert_strings
            embeddings = self._embeddings

        if embeddings is None or len(alert_strings) == 0:
            return None

        query_embedding = self._model.encode([query])[0]
        diff = embeddings - query_embedding
        squared_dists = (diff ** 2).sum(axis=1)
        closest_index = int(np.argmin(squared_dists))
        return alert_strings[closest_index]
