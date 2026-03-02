"""
Phase 3 — Vector Store

ChromaDB client wrapper for the mf_faq collection.

Collection: mf_faq
  - One document per (fund_id, field) chunk — 30 total
  - Cosine similarity metric (best for normalised sentence embeddings)
  - Persistent storage in chroma_db/ at the project root

Document IDs use the pattern "{fund_id}__{field}" (e.g. "hdfc_small_cap__expense_ratio").
This makes upserts idempotent — re-running ingest replaces stale chunks
rather than adding duplicates.

Metadata per document:
    fund_id     — e.g. "hdfc_small_cap"
    fund_name   — e.g. "HDFC Small Cap Fund - Direct Growth"
    field       — e.g. "expense_ratio"
    source_url  — indmoney.com page URL
    scraped_at  — ISO-8601 timestamp
"""

from pathlib import Path

import chromadb

COLLECTION_NAME = "mf_faq"
CHROMA_DIR = Path(__file__).parent.parent.parent / "chroma_db"


# ── Client helpers ─────────────────────────────────────────────────────────────

def get_collection(persist_dir: Path = CHROMA_DIR) -> chromadb.Collection:
    """Return (or create) the mf_faq ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ── Write ──────────────────────────────────────────────────────────────────────

def upsert_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    persist_dir: Path = CHROMA_DIR,
) -> None:
    """
    Upsert chunks and their embeddings into ChromaDB.

    Args:
        chunks:      List of chunk dicts (text, fund_id, fund_name, field, ...).
        embeddings:  Pre-computed embedding vectors (same order as chunks).
        persist_dir: Path to ChromaDB storage directory.
    """
    collection = get_collection(persist_dir)

    ids       = [f"{c['fund_id']}__{c['field']}" for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "fund_id":    c["fund_id"],
            "fund_name":  c["fund_name"],
            "field":      c["field"],
            "source_url": c["source_url"],
            "scraped_at": c["scraped_at"],
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


# ── Read ───────────────────────────────────────────────────────────────────────

def query_chunks(
    query_embedding: list[float],
    n_results: int = 5,
    fund_id: str | None = None,
    field: str | None = None,
    persist_dir: Path = CHROMA_DIR,
) -> dict:
    """
    Retrieve the top-n most similar chunks for a query embedding.

    Args:
        query_embedding: Embedding vector for the user query.
        n_results:       Number of results to return.
        fund_id:         Optional metadata filter (e.g. "hdfc_small_cap").
        field:           Optional metadata filter (e.g. "expense_ratio").
        persist_dir:     ChromaDB storage path.

    Returns:
        ChromaDB result dict with keys: ids, documents, metadatas, distances.
    """
    collection = get_collection(persist_dir)

    where: dict | None = None
    if fund_id and field:
        where = {"$and": [{"fund_id": {"$eq": fund_id}}, {"field": {"$eq": field}}]}
    elif fund_id:
        where = {"fund_id": {"$eq": fund_id}}
    elif field:
        where = {"field": {"$eq": field}}

    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results":        n_results,
        "include":          ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    return collection.query(**kwargs)
