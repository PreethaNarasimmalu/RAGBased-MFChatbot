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
from query_preprocessor import preprocess, OUT_OF_SCOPE_MESSAGE, FUND_CANONICAL_NAMES, FUND_URLS
from prompt_templates import SYSTEM_PROMPT, build_user_message
import llm_client

# phase3 imports (chromadb, sentence-transformers) are deferred inside answer()
# so this module is importable even without those packages installed.

# ── Config ─────────────────────────────────────────────────────────────────────
TOP_K = 3

# Human-readable labels for each stored field
_FIELD_LABELS: dict[str, str] = {
    "expense_ratio":  "Expense Ratio",
    "exit_load":      "Exit Load",
    "min_sip_amount": "Minimum SIP Amount",
    "lock_in_period": "Lock-in Period",
    "riskometer":     "Riskometer (Risk Level)",
    "benchmark":      "Benchmark Index",
}

# Patterns that signal the user is asking "what info do you have about this fund"
_INFO_AVAILABILITY_PATTERNS = [
    "what information do you have",
    "what info do you have",
    "what do you know about",
    "what data do you have",
    "what details do you have",
    "what are the details you have",
    "what details you have",
    "what can you tell me about",
    "what all do you have",
    "what all information",
    "what all details",
    "what information of this fund",
    "what info of this fund",
    "info do you have on this fund",
    "information do you have on this fund",
    "details do you have on",
    "details you have about",
    "details do you have about",
]

# Sentinel text embedded in the "which fund?" response so we can detect it in history
_ASK_FUND_SENTINEL = "Which fund are you asking about?"

ASK_FUND_MESSAGE = (
    f"{_ASK_FUND_SENTINEL} I currently cover these 5 funds:\n\n"
    "1. HDFC Small Cap Fund\n"
    "2. Axis ELSS Tax Saver Fund\n"
    "3. Axis Large & Mid Cap Fund\n"
    "4. Axis Nifty 100 Index Fund\n"
    "5. HDFC Nifty Private Bank ETF\n\n"
    "Please mention the fund name in your question."
)


def _is_info_availability_query(query: str) -> bool:
    """Return True if the user is asking what information the bot has about a fund."""
    lower = query.lower()
    return any(p in lower for p in _INFO_AVAILABILITY_PATTERNS)


def _build_info_availability_response(fund_id: str, chunks: list[dict]) -> str:
    """
    Build a response listing all available fields for a fund (no values).
    """
    fund_name = FUND_CANONICAL_NAMES.get(fund_id, fund_id)
    source_url = FUND_URLS.get(fund_id, "https://www.indmoney.com/mutual-funds/all")

    if not chunks:
        return (
            f"I don't currently have any stored information for {fund_name}. "
            f"You can explore it here: {source_url}"
        )

    available_fields = [
        _FIELD_LABELS.get(c["field"], c["field"])
        for c in chunks
        if c["field"]
    ]
    # Deduplicate while preserving order
    seen = set()
    unique_fields = []
    for f in available_fields:
        if f not in seen:
            seen.add(f)
            unique_fields.append(f)

    field_list = "\n".join(f"  • {f}" for f in unique_fields)
    scraped_at = chunks[0]["scraped_at"][:10] if chunks else ""

    return (
        f"For **{fund_name}**, I have the following information available:\n\n"
        f"{field_list}\n\n"
        f"Feel free to ask me about any of these!\n\n"
        f"Last updated: {scraped_at}  \n"
        f"Source: {source_url}"
    )

# ChromaDB cosine distance: 0 = identical, 2 = opposite.
# Chunks with distance > threshold are considered irrelevant.
_RELEVANCE_THRESHOLD = 1.2


# ── Public API ─────────────────────────────────────────────────────────────────

def answer(query: str, chat_history: list[dict] | None = None) -> str:
    """
    Process a user query through the full RAG pipeline.

    Always returns a non-empty string — either an answer (with citation)
    or a safe refusal / redirect message.  Never raises to the caller.

    Args:
        query:        Raw user input string.
        chat_history: Optional list of prior messages ({"role", "content"}).
                      Used to detect follow-up fund-name replies after an
                      info-availability prompt.

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

    # ── Stage 2b: Info-availability shortcut (before out-of-scope check) ──────
    # Handles two sub-cases:
    #   a) "What details do you have about HDFC Small Cap Fund?" → list fields
    #   b) "What details do you have about a fund?" (no fund) → ask which fund
    #   c) User replies with just a fund name after the bot asked "which fund?" → list fields
    is_info_query = _is_info_availability_query(cleaned)

    # Sub-case (c): fund-only follow-up after the bot asked "which fund?"
    if not is_info_query and fund_id and chat_history:
        last_bot = next(
            (m["content"] for m in reversed(chat_history) if m.get("role") == "assistant"),
            None,
        )
        if last_bot and _ASK_FUND_SENTINEL in last_bot:
            is_info_query = True

    if is_info_query:
        if fund_id:
            try:
                from vector_store import get_all_chunks_for_fund
                all_chunks = get_all_chunks_for_fund(fund_id)
                return _build_info_availability_response(fund_id, all_chunks)
            except Exception as exc:
                return (
                    f"Vector store unavailable ({exc}). "
                    "Please ensure the database has been populated by running "
                    "`python phase3/ingestion/ingest.py`."
                )
        else:
            # No fund mentioned — ask the user to specify one
            return ASK_FUND_MESSAGE

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
    # Constraint 4: every answer must end with "Last updated from sources:"
    if "Last updated from sources:" not in llm_answer:
        top = relevant[0]
        llm_answer += (
            f"\n\nLast updated from sources: {top['scraped_at']}"
            f"  |  Source: {top['source_url']}"
        )

    return llm_answer
