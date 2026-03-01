"""
Phase 3 — Embedder

Thin wrapper around sentence-transformers for generating dense embeddings.

Model: all-MiniLM-L6-v2
  - Free and local — no API key required
  - 384-dimensional embeddings
  - Fast on CPU; good semantic similarity for factual Q&A
  - Already pinned in requirements.txt (sentence-transformers==3.0.1)

The model is lazy-loaded on first use and cached as a module-level singleton
so repeated calls within the same process don't reload it from disk.
"""

from __future__ import annotations

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None


def _get_model():
    """Lazy-load the sentence-transformers model (singleton)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of text strings.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors (one per input text), each a list of floats.
    """
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string.

    Args:
        query: The user query or search string.

    Returns:
        Embedding vector as a list of floats.
    """
    return embed_texts([query])[0]
