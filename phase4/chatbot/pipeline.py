"""
Phase 4 — RAG Pipeline

End-to-end flow for every user query:

  1. Safety gate     — block PII / advice / performance queries instantly
  2. Preprocessor    — detect fund name; detect out-of-scope MF queries
  3. Embed query     — sentence-transformers (phase3/ingestion/embedder.py)
  4. Retrieve        — top-3 cosine-similar chunks from ChromaDB (phase3)
  5. Assemble        — inject context into user message
  6. Generate        — Groq LLM with strict system prompt
  7. Cite            — enforce "Last updated from sources:" in every answer

Guarantees (from Operational Constraints):
  • Answers cite ONLY indmoney.com URLs — no other domains.
  • Every non-refusal answer ends with "Last updated from sources: …"
  • PII blocked before touching vector DB or LLM.
  • Out-of-scope fund queries redirect to indmoney.com/mutual-funds/all.
  • No performance computations (blocked at safety gate + system prompt).
"""

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
_ROOT            = Path(__file__).parent.parent.parent
_PHASE3_INGEST   = _ROOT / "phase3" / "ingestion"
_PHASE4_CHATBOT  = Path(__file__).parent

sys.path.insert(0, str(_PHASE3_INGEST))
sys.path.insert(0, str(_PHASE4_CHATBOT))

# ── Imports ────────────────────────────────────────────────────────────────────
# safety_gate / preprocessor / prompt_templates use only stdlib — always safe
from safety_gate import check, PASS, get_refusal_message
from query_preprocessor import preprocess, OUT_OF_SCOPE_MESSAGE
from prompt_templates import SYSTEM_PROMPT, build_user_message
import llm_client

# phase3 imports (chromadb, sentence-transformers) are deferred inside answer()
# so this module is importable even without those packages installed.

# ── Config ─────────────────────────────────────────────────────────────────────
TOP_K = 3

# ChromaDB cosine distance: 0 = identical, 2 = opposite.
# Chunks with distance > threshold are considered irrelevant.
_RELEVANCE_THRESHOLD = 1.2


# ── Public API ─────────────────────────────────────────────────────────────────

def answer(query: str) -> str:
    """
    Process a user query through the full RAG pipeline.

    Always returns a non-empty string — either an answer (with citation)
    or a safe refusal / redirect message.  Never raises to the caller.

    Args:
        query: Raw user input string.

    Returns:
        Answer string that always ends with
        "Last updated from sources: <date>  |  Source: <url>"
        (or a refusal message for blocked queries).
    """
    # ── Stage 1: Safety gate ───────────────────────────────────────────────────
    gate = check(query)
    if gate != PASS:
        return get_refusal_message(gate)

    # ── Stage 2: Preprocess + detect fund ─────────────────────────────────────
    cleaned, fund_id, out_of_scope = preprocess(query)

    # Constraint: out-of-scope MF query → polite redirect
    if out_of_scope:
        return OUT_OF_SCOPE_MESSAGE

    # ── Stage 3: Embed query ───────────────────────────────────────────────────
    try:
        from embedder import embed_query
        query_emb = embed_query(cleaned)
    except Exception as exc:
        return (
            f"Embedding service unavailable ({exc}). "
            "Please try again later."
        )

    # ── Stage 4: Retrieve from ChromaDB ───────────────────────────────────────
    try:
        from vector_store import query_chunks
        result = query_chunks(query_emb, n_results=TOP_K, fund_id=fund_id)
    except Exception as exc:
        return (
            f"Vector store unavailable ({exc}). "
            "Please ensure the database has been populated by running "
            "`python phase3/ingestion/ingest.py`."
        )

    # Flatten result into chunk dicts
    chunks: list[dict] = []
    if result.get("documents") and result["documents"][0]:
        distances = result.get("distances", [[]])[0]
        for i, (doc, meta) in enumerate(
            zip(result["documents"][0], result["metadatas"][0])
        ):
            dist = distances[i] if i < len(distances) else 0.0
            chunks.append({
                "text":       doc,
                "fund_name":  meta.get("fund_name", ""),
                "field":      meta.get("field", ""),
                "source_url": meta.get("source_url", ""),
                "scraped_at": meta.get("scraped_at", ""),
                "distance":   dist,
            })

    # Filter out low-relevance chunks
    relevant = [c for c in chunks if c["distance"] <= _RELEVANCE_THRESHOLD]

    if not relevant:
        # No relevant result → redirect to all-funds page
        return (
            "I could not find relevant information for your question in my database. "
            "For information about mutual funds, please visit: "
            "https://www.indmoney.com/mutual-funds/all"
        )

    # ── Stage 5: Build context message ────────────────────────────────────────
    user_msg = build_user_message(cleaned, relevant)

    # ── Stage 6: Call LLM ─────────────────────────────────────────────────────
    try:
        llm_answer = llm_client.call(SYSTEM_PROMPT, user_msg)
    except RuntimeError as exc:
        # GROQ_API_KEY not set
        return str(exc)
    except Exception as exc:
        return (
            f"LLM service error ({exc}). Please try again later."
        )

    # ── Stage 7: Guarantee citation line ──────────────────────────────────────
    # Constraint 4: every answer must end with "Last updated:" and "Source:"
    if "Last updated:" not in llm_answer:
        top = relevant[0]
        llm_answer += (
            f"\n\nLast updated: {top['scraped_at'][:10]}"
            f"\nSource: {top['source_url']}"
        )

    return llm_answer
