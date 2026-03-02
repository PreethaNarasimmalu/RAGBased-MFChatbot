"""
Phase 4 Gate Tests — Chatbot Core

Test groups:
  1.  File existence         (5 tests)  — always pass
  2.  Safety gate — PII      (4 tests)  — always pass, no external deps
  3.  Safety gate — advice   (3 tests)  — always pass
  4.  Safety gate — perf     (2 tests)  — always pass
  5.  Safety gate — pass     (2 tests)  — always pass
  6.  Query preprocessor     (6 tests)  — always pass
  7.  Prompt templates       (3 tests)  — always pass
  8.  Pipeline — refusals    (4 tests)  — always pass (gate fires before LLM/DB)
  9.  Pipeline — integration (3 tests)  — skip if no GROQ_API_KEY or empty ChromaDB

Run all always-passing tests (groups 1-8):
    pytest phase4/tests/test_phase4.py -v -k "not integration"

Run all tests (requires scraped data + ingest + GROQ_API_KEY):
    pytest phase4/tests/test_phase4.py -v
"""

import os
import sys
import pytest
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent.parent
PHASE4_CHATBOT = ROOT / "phase4" / "chatbot"
PHASE3_INGEST  = ROOT / "phase3" / "ingestion"
CHROMA_DIR     = ROOT / "chroma_db"

sys.path.insert(0, str(PHASE4_CHATBOT))
sys.path.insert(0, str(PHASE3_INGEST))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _chroma_populated() -> bool:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_or_create_collection("mf_faq")
        return col.count() > 0
    except Exception:
        return False


def _groq_key_present() -> bool:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    return bool(os.getenv("GROQ_API_KEY"))


# ══════════════════════════════════════════════════════════════════════════════
# 1. File existence
# ══════════════════════════════════════════════════════════════════════════════

def test_safety_gate_file_exists():
    assert (PHASE4_CHATBOT / "safety_gate.py").is_file()

def test_query_preprocessor_file_exists():
    assert (PHASE4_CHATBOT / "query_preprocessor.py").is_file()

def test_prompt_templates_file_exists():
    assert (PHASE4_CHATBOT / "prompt_templates.py").is_file()

def test_llm_client_file_exists():
    assert (PHASE4_CHATBOT / "llm_client.py").is_file()

def test_pipeline_file_exists():
    assert (PHASE4_CHATBOT / "pipeline.py").is_file()


# ══════════════════════════════════════════════════════════════════════════════
# 2. Safety gate — PII blocking
# ══════════════════════════════════════════════════════════════════════════════

from safety_gate import check, PASS, REFUSE_PII, REFUSE_ADVICE, REFUSE_PERF
from safety_gate import REFUSAL_MESSAGE_PII, REFUSAL_MESSAGE_ADVICE, REFUSAL_MESSAGE_PERF


def test_safety_gate_blocks_pan():
    """Valid PAN number in query must be blocked."""
    assert check("My PAN is ABCDE1234F, what is the expense ratio?") == REFUSE_PII

def test_safety_gate_blocks_aadhaar():
    """Aadhaar number (xxxx-xxxx-xxxx) must be blocked."""
    assert check("Aadhaar 1234-5678-9012 for HDFC small cap") == REFUSE_PII

def test_safety_gate_blocks_phone():
    """Indian 10-digit mobile number must be blocked."""
    assert check("My number is 9876543210 what is exit load?") == REFUSE_PII

def test_safety_gate_blocks_email():
    """Email address in query must be blocked."""
    assert check("Send details to user@example.com") == REFUSE_PII


# ══════════════════════════════════════════════════════════════════════════════
# 3. Safety gate — Advice blocking
# ══════════════════════════════════════════════════════════════════════════════

def test_safety_gate_blocks_should_i():
    assert check("Should I invest in HDFC Small Cap?") == REFUSE_ADVICE

def test_safety_gate_blocks_recommend():
    assert check("Which fund do you recommend for long term?") == REFUSE_ADVICE

def test_safety_gate_blocks_portfolio():
    assert check("How should I build my portfolio?") == REFUSE_ADVICE


# ══════════════════════════════════════════════════════════════════════════════
# 4. Safety gate — Performance blocking
# ══════════════════════════════════════════════════════════════════════════════

def test_safety_gate_blocks_past_performance():
    assert check("What is the past performance of HDFC Small Cap?") == REFUSE_PERF

def test_safety_gate_blocks_cagr():
    assert check("What is the CAGR of Axis ELSS fund?") == REFUSE_PERF


# ══════════════════════════════════════════════════════════════════════════════
# 5. Safety gate — Factual queries pass
# ══════════════════════════════════════════════════════════════════════════════

def test_safety_gate_passes_expense_ratio_query():
    assert check("What is the expense ratio of HDFC Small Cap Fund?") == PASS

def test_safety_gate_passes_exit_load_query():
    assert check("What is the exit load for Axis ELSS?") == PASS


# ══════════════════════════════════════════════════════════════════════════════
# 6. Query preprocessor
# ══════════════════════════════════════════════════════════════════════════════

from query_preprocessor import preprocess, detect_fund, is_mf_query, OUT_OF_SCOPE_MESSAGE


def test_preprocessor_detects_hdfc_small_cap():
    _, fund_id, _ = preprocess("What is the expense ratio of HDFC Small Cap?")
    assert fund_id == "hdfc_small_cap"

def test_preprocessor_detects_axis_elss():
    _, fund_id, _ = preprocess("What is the lock-in period for Axis ELSS fund?")
    assert fund_id == "axis_elss"

def test_preprocessor_detects_axis_nifty_100():
    _, fund_id, _ = preprocess("Tell me the benchmark for Axis Nifty 100 index fund")
    assert fund_id == "axis_nifty_100"

def test_preprocessor_detects_hdfc_etf():
    _, fund_id, _ = preprocess("What is the riskometer of HDFC Private Bank ETF?")
    assert fund_id == "hdfc_pvt_bank_etf"

def test_preprocessor_out_of_scope_for_unknown_fund():
    """Query about a fund not in our 5 should be flagged out-of-scope."""
    _, fund_id, out_of_scope = preprocess("What is the expense ratio of SBI Bluechip Fund?")
    assert fund_id is None
    assert out_of_scope is True

def test_preprocessor_not_out_of_scope_for_non_mf_query():
    """Non-MF query (no MF keywords) should not be flagged as out-of-scope."""
    _, fund_id, out_of_scope = preprocess("What is the weather today?")
    assert fund_id is None
    assert out_of_scope is False


# ══════════════════════════════════════════════════════════════════════════════
# 7. Prompt templates
# ══════════════════════════════════════════════════════════════════════════════

from prompt_templates import SYSTEM_PROMPT, build_user_message


def test_system_prompt_contains_constraint_citation():
    """System prompt must enforce 'Last updated:' citation."""
    assert "Last updated:" in SYSTEM_PROMPT

def test_system_prompt_contains_out_of_scope_rule():
    """System prompt must contain the out-of-scope redirect URL."""
    assert "indmoney.com/mutual-funds/all" in SYSTEM_PROMPT

def test_build_user_message_injects_context():
    """build_user_message must wrap facts in [CONTEXT] markers."""
    chunks = [{
        "text":       "The expense ratio of HDFC Small Cap Fund is 0.55%.",
        "fund_name":  "HDFC Small Cap Fund",
        "field":      "expense_ratio",
        "source_url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
        "scraped_at": "2026-03-01T10:00:00+05:30",
    }]
    msg = build_user_message("What is the expense ratio of HDFC Small Cap?", chunks)
    assert "[CONTEXT]" in msg
    assert "[END CONTEXT]" in msg
    assert "0.55%" in msg
    assert "indmoney.com" in msg
    assert "Question:" in msg


# ══════════════════════════════════════════════════════════════════════════════
# 8. Pipeline — refusal paths (no LLM or ChromaDB needed)
# These work because the safety gate fires BEFORE embed/retrieve/LLM calls.
# ══════════════════════════════════════════════════════════════════════════════

from pipeline import answer
from safety_gate import REFUSAL_MESSAGE_PII, REFUSAL_MESSAGE_ADVICE
from query_preprocessor import OUT_OF_SCOPE_MESSAGE


def test_pipeline_refuses_pii():
    """Pipeline must return PII refusal for a query with a PAN number."""
    result = answer("My PAN is ABCDE1234F what is the expense ratio?")
    assert result == REFUSAL_MESSAGE_PII

def test_pipeline_refuses_advice():
    """Pipeline must return advice refusal for 'should I invest'."""
    result = answer("Should I invest in HDFC Small Cap Fund?")
    assert result == REFUSAL_MESSAGE_ADVICE

def test_pipeline_refuses_performance():
    """Pipeline must return performance refusal for CAGR queries."""
    result = answer("What is the CAGR of Axis ELSS fund?")
    assert "performance" in result.lower() or "returns" in result.lower()

def test_pipeline_redirects_out_of_scope_fund():
    """Pipeline must redirect queries about funds not in our 5."""
    result = answer("What is the expense ratio of SBI Bluechip Fund?")
    assert "indmoney.com/mutual-funds/all" in result


# ══════════════════════════════════════════════════════════════════════════════
# 9. Pipeline — integration tests (require ChromaDB + GROQ_API_KEY)
# Run: python phase3/ingestion/ingest.py  (once)
#      add GROQ_API_KEY to .env
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_pipeline_expense_ratio_answer_has_citation():
    """Integration: factual query returns an answer with 'Last updated from sources:'."""
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    result = answer("What is the expense ratio of HDFC Small Cap Fund?")
    assert "Last updated from sources:" in result, (
        f"Citation missing from answer:\n{result}"
    )

@pytest.mark.integration
def test_pipeline_source_url_is_indmoney():
    """Integration: source URL in every answer must be an indmoney.com URL."""
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    result = answer("What is the exit load for Axis ELSS fund?")
    assert "indmoney.com" in result, (
        f"Expected indmoney.com URL in answer:\n{result}"
    )

@pytest.mark.integration
def test_pipeline_lock_in_axis_elss():
    """Integration: lock-in query for Axis ELSS returns '3' in the answer."""
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    result = answer("What is the lock-in period for Axis ELSS tax saver fund?")
    assert "3" in result, (
        f"Expected '3 years' in lock-in answer:\n{result}"
    )
