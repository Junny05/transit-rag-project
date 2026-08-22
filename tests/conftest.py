import os
import sys
import numpy as np
import pytest

# Set required env vars before anything in app/ is imported, since
# config.py reads them at module load time.
os.environ.setdefault("MTA_API_KEY", "test-mta-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")


class _FakeSentenceTransformer:
    """Stand-in for SentenceTransformer so the test suite never downloads
    real model weights or needs network access."""

    def __init__(self, *args, **kwargs):
        pass

    def get_sentence_embedding_dimension(self):
        return 2

    def encode(self, texts):
        # Deterministic hash-based vector so equal strings -> equal vectors,
        # without needing a lookup table like the retrieval unit tests use.
        return np.array([[float(hash(t) % 100), float(hash(t[::-1]) % 100)] for t in texts])


@pytest.fixture(autouse=True, scope="session")
def _patch_sentence_transformer():
    # Patch both the source module AND app.retrieval's already-bound
    # reference (it does `from sentence_transformers import SentenceTransformer`,
    # so patching the source module alone doesn't affect that name once imported).
    import sentence_transformers
    import app.retrieval as retrieval_module

    sentence_transformers.SentenceTransformer = _FakeSentenceTransformer
    retrieval_module.SentenceTransformer = _FakeSentenceTransformer
    yield
