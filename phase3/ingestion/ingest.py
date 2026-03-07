"""
Phase 3 — Ingest Pipeline

Orchestrates the full data ingestion flow:
  1. Load raw fund JSON files from phase2/data/raw/
  2. Convert each fund's facts into natural-language text chunks (chunker.py)
  3. Embed all chunks with sentence-transformers (embedder.py)
  4. Upsert chunks + embeddings into ChromaDB (vector_store.py)

Run from the repo root:
    python phase3/ingestion/ingest.py

Expected output:
    ChromaDB collection 'mf_faq' populated with 30 chunks
    (5 funds × 6 fact fields; null fields produce templated chunks).
"""

import sys
from pathlib import Path

# Allow running as a script from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from chunker import build_chunks
from embedder import embed_texts
from vector_store import CHROMA_DIR, upsert_chunks


def ingest(
    raw_dir: Path | None = None,
    chroma_dir: Path = CHROMA_DIR,
) -> int:
    """
    Run the full ingest pipeline.

    Args:
        raw_dir:    Override path to phase2/data/raw/ (used in tests).
        chroma_dir: Override ChromaDB storage path (used in tests).

    Returns:
        Number of chunks ingested.
    """
    # 1. Build chunks from raw JSON files
    chunk_kwargs: dict = {}
    if raw_dir is not None:
        chunk_kwargs["raw_dir"] = raw_dir

    chunks = build_chunks(**chunk_kwargs)
    print(f"[ingest] {len(chunks)} chunks built")

    # 2. Embed all chunk texts
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    dims = len(embeddings[0]) if embeddings else 0
    print(f"[ingest] {len(embeddings)} embeddings generated ({dims}d each)")

    # 3. Upsert into ChromaDB
    upsert_chunks(chunks, embeddings, persist_dir=chroma_dir)
    print(f"[ingest] ChromaDB upsert complete -> collection 'mf_faq' at {chroma_dir}")

    return len(chunks)


if __name__ == "__main__":
    count = ingest()
    print(f"\nDone. {count} chunks ingested into ChromaDB.")
