"""
Phase 3 Gate Tests — Data Processing & Embedding

Verifies:
  1. Source files exist: chunker.py, embedder.py, vector_store.py, ingest.py
  2. Chunker unit tests (no raw files needed):
     - Correct chunk text generated for a valued field
     - Null lock_in_period produces a "no lock-in" chunk (not skipped)
     - ETF "--" min_sip_amount produces a "no SIP" chunk (not skipped)
  3. Chunker produces 30 chunks from the 5 real raw JSON files
  4. Every chunk has all required metadata keys
  5. ChromaDB has exactly 30 documents after ingestion
  6. Every (fund_id, field) pair has exactly 1 document in ChromaDB
  7. source_url and scraped_at metadata present on all chunks
  8. Sample retrieval: expense ratio query → correct top-1 chunk
  9. Lock-in query → axis_elss lock_in_period in top-3

How to run all 13 tests:
  1. Run scraper on Windows:  python phase2/scraping/scraper.py
  2. Run ingest:              python phase3/ingestion/ingest.py
  3. Run tests:               pytest phase3/tests/test_phase3.py -v

Tests 3–9 skip gracefully if raw JSON files or ChromaDB data are absent.
"""

import sys
import pytest
from pathlib import Path

ROOT       = Path(__file__).parent.parent.parent    # → repo root
PHASE2_RAW = ROOT / "phase2" / "data" / "raw"
INGESTION  = ROOT / "phase3" / "ingestion"
CHROMA_DIR = ROOT / "chroma_db"

FUND_IDS = [
    "hdfc_small_cap",
    "axis_elss",
    "axis_large_mid_cap",
    "axis_nifty_100",
    "hdfc_pvt_bank_etf",
]
FIELDS = [
    "expense_ratio",
    "exit_load",
    "min_sip_amount",
    "lock_in_period",
    "riskometer",
    "benchmark",
]
EXPECTED_CHUNKS = len(FUND_IDS) * len(FIELDS)   # 30


# ── Helpers ────────────────────────────────────────────────────────────────────

def _raw_files_present() -> bool:
    return all((PHASE2_RAW / f"{fid}.json").is_file() for fid in FUND_IDS)


def _chroma_populated() -> bool:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_or_create_collection("mf_faq")
        return col.count() > 0
    except Exception:
        return False


def _add_ingestion_to_path():
    sys.path.insert(0, str(INGESTION))


# ── Test 1: Source files exist ─────────────────────────────────────────────────

def test_chunker_file_exists():
    assert (INGESTION / "chunker.py").is_file(), "ingestion/chunker.py not found"


def test_embedder_file_exists():
    assert (INGESTION / "embedder.py").is_file(), "ingestion/embedder.py not found"


def test_vector_store_file_exists():
    assert (INGESTION / "vector_store.py").is_file(), "ingestion/vector_store.py not found"


def test_ingest_file_exists():
    assert (INGESTION / "ingest.py").is_file(), "ingestion/ingest.py not found"


# ── Test 2: Chunker unit tests (no raw files or ChromaDB needed) ───────────────

def test_chunker_valued_field():
    """Chunker generates correct text and metadata for a standard valued field."""
    _add_ingestion_to_path()
    from chunker import _fund_to_chunks

    sample = {
        "fund_id":        "test_fund",
        "fund_name":      "Test Fund Direct Growth",
        "amc":            "Test AMC",
        "category":       "Test",
        "expense_ratio":  "1.00%",
        "exit_load":      "Nil",
        "min_sip_amount": "₹500",
        "lock_in_period": None,
        "riskometer":     "High Risk",
        "benchmark":      "Nifty 50 TR INR",
        "source_url":     "https://www.indmoney.com/test",
        "scraped_at":     "2026-01-01T00:00:00+00:00",
    }
    chunks = _fund_to_chunks(sample)
    assert len(chunks) == 6, f"Expected 6 chunks, got {len(chunks)}"

    er = next(c for c in chunks if c["field"] == "expense_ratio")
    assert "1.00%" in er["text"]
    assert "Test Fund Direct Growth" in er["text"]
    assert er["fund_id"] == "test_fund"
    assert er["source_url"] == "https://www.indmoney.com/test"
    assert er["scraped_at"] == "2026-01-01T00:00:00+00:00"


def test_chunker_null_lock_in_produces_chunk():
    """Null lock_in_period must produce a 'no lock-in' chunk, not be skipped."""
    _add_ingestion_to_path()
    from chunker import _fund_to_chunks

    sample = {
        "fund_id": "test_fund", "fund_name": "Test Fund", "amc": "X",
        "category": "Y", "expense_ratio": "0.5%", "exit_load": "Nil",
        "min_sip_amount": "₹100", "lock_in_period": None,
        "riskometer": "High Risk", "benchmark": "Nifty 50",
        "source_url": "https://www.indmoney.com/test",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    chunks = _fund_to_chunks(sample)
    lock_in = next((c for c in chunks if c["field"] == "lock_in_period"), None)
    assert lock_in is not None, "lock_in_period chunk missing for null value"
    assert "no lock-in" in lock_in["text"].lower(), (
        f"Expected 'no lock-in' in text, got: {lock_in['text']}"
    )


def test_chunker_etf_sip_placeholder_produces_chunk():
    """ETF '--' min_sip_amount must produce a 'no SIP' chunk, not be skipped."""
    _add_ingestion_to_path()
    from chunker import _fund_to_chunks

    sample = {
        "fund_id": "test_etf", "fund_name": "Test ETF", "amc": "X",
        "category": "ETF", "expense_ratio": "0.2%", "exit_load": "0%",
        "min_sip_amount": "--", "lock_in_period": None,
        "riskometer": "Very High Risk", "benchmark": "Nifty 50",
        "source_url": "https://www.indmoney.com/test-etf",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    chunks = _fund_to_chunks(sample)
    sip = next((c for c in chunks if c["field"] == "min_sip_amount"), None)
    assert sip is not None, "min_sip_amount chunk missing for '--' value"
    assert "etf" in sip["text"].lower() or "sip" in sip["text"].lower(), (
        f"Expected ETF/SIP context in text, got: {sip['text']}"
    )


# ── Tests 3–9: Require raw JSON files + populated ChromaDB ────────────────────
# Run `python phase2/scraping/scraper.py` then `python phase3/ingestion/ingest.py`

@pytest.fixture(scope="module")
def chroma_col():
    """Return the populated mf_faq collection (skip if prerequisites missing)."""
    if not _raw_files_present():
        pytest.skip(
            "Raw JSON files not found in phase2/data/raw/. "
            "Run `python phase2/scraping/scraper.py` first."
        )
    if not _chroma_populated():
        pytest.skip(
            "ChromaDB collection is empty. "
            "Run `python phase3/ingestion/ingest.py` first."
        )
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection("mf_faq")


def test_chunker_produces_30_chunks_from_raw_files():
    """Chunker must produce exactly 30 chunks from the 5 real raw JSON files."""
    if not _raw_files_present():
        pytest.skip("Raw JSON files not found — run scraper first.")
    _add_ingestion_to_path()
    from chunker import build_chunks
    chunks = build_chunks(raw_dir=PHASE2_RAW)
    assert len(chunks) == EXPECTED_CHUNKS, (
        f"Expected {EXPECTED_CHUNKS} chunks, got {len(chunks)}"
    )


def test_all_chunks_have_required_metadata_keys():
    """Every generated chunk must contain all required metadata keys."""
    if not _raw_files_present():
        pytest.skip("Raw JSON files not found — run scraper first.")
    _add_ingestion_to_path()
    from chunker import build_chunks
    required = {"text", "fund_id", "fund_name", "field", "source_url", "scraped_at"}
    chunks = build_chunks(raw_dir=PHASE2_RAW)
    for c in chunks:
        missing = required - c.keys()
        assert not missing, (
            f"Chunk [{c.get('fund_id')}/{c.get('field')}] missing keys: {missing}"
        )


def test_chroma_has_30_documents(chroma_col):
    """ChromaDB collection must contain exactly 30 documents after ingestion."""
    count = chroma_col.count()
    assert count == EXPECTED_CHUNKS, (
        f"Expected {EXPECTED_CHUNKS} docs in ChromaDB, found {count}"
    )


def test_each_fund_field_pair_has_one_document(chroma_col):
    """Every (fund_id, field) pair must have exactly 1 document in ChromaDB."""
    for fund_id in FUND_IDS:
        for field in FIELDS:
            doc_id = f"{fund_id}__{field}"
            result = chroma_col.get(ids=[doc_id], include=["metadatas"])
            assert len(result["ids"]) == 1, (
                f"Expected 1 document for id '{doc_id}', found {len(result['ids'])}"
            )


def test_all_docs_have_source_url_and_scraped_at(chroma_col):
    """Every document in ChromaDB must have source_url and scraped_at metadata."""
    all_docs = chroma_col.get(include=["metadatas"])
    for meta in all_docs["metadatas"]:
        assert meta.get("source_url"), f"Missing source_url in: {meta}"
        assert meta.get("scraped_at"), f"Missing scraped_at in: {meta}"


def test_retrieval_expense_ratio_hdfc_small_cap(chroma_col):
    """
    Querying 'expense ratio of HDFC Small Cap' must return that fund's
    expense_ratio chunk as the top result.
    """
    _add_ingestion_to_path()
    from embedder import embed_query

    q = embed_query("What is the expense ratio of HDFC Small Cap Fund?")
    result = chroma_col.query(
        query_embeddings=[q],
        n_results=1,
        include=["metadatas"],
    )
    top = result["metadatas"][0][0]
    assert top["fund_id"] == "hdfc_small_cap", (
        f"Expected fund_id='hdfc_small_cap', got '{top['fund_id']}'"
    )
    assert top["field"] == "expense_ratio", (
        f"Expected field='expense_ratio', got '{top['field']}'"
    )


def test_retrieval_lock_in_axis_elss(chroma_col):
    """
    Querying 'lock-in period for Axis ELSS' must return axis_elss/lock_in_period
    in the top-3 results.
    """
    _add_ingestion_to_path()
    from embedder import embed_query

    q = embed_query("What is the lock-in period for Axis ELSS fund?")
    result = chroma_col.query(
        query_embeddings=[q],
        n_results=3,
        include=["metadatas"],
    )
    top_metas = result["metadatas"][0]
    found = any(
        m["fund_id"] == "axis_elss" and m["field"] == "lock_in_period"
        for m in top_metas
    )
    assert found, (
        "Expected axis_elss/lock_in_period in top-3 results, got: "
        + str([(m["fund_id"], m["field"]) for m in top_metas])
    )
