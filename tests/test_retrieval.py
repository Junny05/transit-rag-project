import numpy as np
import pytest

from app.retrieval import AlertIndex


class FakeModel:
    """Deterministic stand-in for SentenceTransformer.

    Maps known strings to hand-picked 2D vectors so we can assert exactly
    which alert should be considered "closest" to a query, without
    depending on real embedding weights.
    """

    VECTORS = {
        "L train delayed": [1.0, 0.0],
        "4/5/6 running with delays": [0.0, 1.0],
        "Signal problems on the A line": [0.9, 0.1],
        "query: L train": [1.0, 0.05],
        "query: A line": [0.85, 0.15],
    }

    def get_sentence_embedding_dimension(self):
        return 2

    def encode(self, texts):
        return np.array([self.VECTORS[t] for t in texts])


@pytest.fixture
def index():
    return AlertIndex(model=FakeModel())


def test_index_not_ready_before_first_refresh(index):
    assert index.is_ready is False
    assert index.find_closest("query: L train") is None


def test_refresh_populates_index(index):
    index.refresh(["L train delayed", "4/5/6 running with delays"])
    assert index.is_ready is True
    assert index.last_updated is not None


def test_find_closest_returns_nearest_alert(index):
    index.refresh(["L train delayed", "4/5/6 running with delays"])
    result = index.find_closest("query: L train")
    assert result == "L train delayed"


def test_find_closest_distinguishes_similar_alerts(index):
    index.refresh(["L train delayed", "Signal problems on the A line"])
    result = index.find_closest("query: A line")
    assert result == "Signal problems on the A line"


def test_refresh_with_empty_alerts_clears_index(index):
    index.refresh(["L train delayed"])
    assert index.find_closest("query: L train") == "L train delayed"

    index.refresh([])
    assert index.find_closest("query: L train") is None


def test_refresh_swaps_atomically_not_incrementally(index):
    # Simulates the real production bug this replaces: refresh() should
    # replace the whole alert set, not append to a stale one.
    index.refresh(["L train delayed"])
    index.refresh(["4/5/6 running with delays"])
    assert index.find_closest("query: L train") == "4/5/6 running with delays"
