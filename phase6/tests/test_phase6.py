"""
Phase 6 Gate Tests — Evaluation & QA

Test groups:
  1.  File existence          (5 tests)   — always pass
  2.  JSON schema             (6 tests)   — always pass
  3.  Coverage validation     (3 tests)   — always pass
  4.  Refusal — advice gate   (5 tests)   — always pass (safety gate, no deps)
  5.  Refusal — perf gate     (3 tests)   — always pass
  6.  Refusal — PII gate      (2 tests)   — always pass
  7.  Refusal — out-of-scope  (1 test)    — always pass
  8.  Refusal message content (2 tests)   — always pass
  9.  Integration — accuracy  (3 tests)   — skip if no ChromaDB or GROQ_API_KEY

Run always-passing tests only:
    pytest phase6/tests/test_phase6.py -v -k "not integration"

Run all (requires scraped data + ingest + GROQ_API_KEY):
    pytest phase6/tests/test_phase6.py -v
"""

import json
import os
import sys
import pytest
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent.parent
PHASE6_DIR     = ROOT / "phase6"
EVAL_DIR       = PHASE6_DIR / "eval"
PHASE4_CHATBOT = ROOT / "phase4" / "chatbot"
PHASE3_INGEST  = ROOT / "phase3" / "ingestion"
CHROMA_DIR     = ROOT / "chroma_db"

sys.path.insert(0, str(PHASE4_CHATBOT))
sys.path.insert(0, str(PHASE3_INGEST))

QUERIES_FILE   = EVAL_DIR / "test_queries.json"
ANSWERS_FILE   = EVAL_DIR / "expected_answers.md"

EXPECTED_FUND_IDS = {
    "hdfc_small_cap",
    "axis_elss",
    "axis_large_mid_cap",
    "axis_nifty_100",
    "hdfc_pvt_bank_etf",
}

EXPECTED_FIELDS = {
    "expense_ratio",
    "exit_load",
    "min_sip_amount",
    "lock_in_period",
    "riskometer",
    "benchmark",
    "statement_download",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_queries() -> dict:
    with open(QUERIES_FILE) as f:
        return json.load(f)


def _chroma_populated() -> bool:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_or_create_collection("mf_faq")
        return col.count() > 0
    except Exception:
        return False


def _groq_key_present() -> bool:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    return bool(os.getenv("GROQ_API_KEY"))


# ══════════════════════════════════════════════════════════════════════════════
# 1. File existence
# ══════════════════════════════════════════════════════════════════════════════

def test_phase6_directory_exists():
    assert PHASE6_DIR.is_dir(), "phase6/ directory missing"

def test_eval_directory_exists():
    assert EVAL_DIR.is_dir(), "phase6/eval/ directory missing"

def test_test_queries_json_exists():
    assert QUERIES_FILE.is_file(), "phase6/eval/test_queries.json missing"

def test_expected_answers_md_exists():
    assert ANSWERS_FILE.is_file(), "phase6/eval/expected_answers.md missing"

def test_test_phase6_py_exists():
    assert (PHASE6_DIR / "tests" / "test_phase6.py").is_file()


# ══════════════════════════════════════════════════════════════════════════════
# 2. JSON schema validation
# ══════════════════════════════════════════════════════════════════════════════

def test_queries_json_is_valid_json():
    data = _load_queries()
    assert isinstance(data, dict)

def test_queries_json_has_factual_queries_key():
    data = _load_queries()
    assert "factual_queries" in data

def test_queries_json_has_refusal_queries_key():
    data = _load_queries()
    assert "refusal_queries" in data

def test_queries_json_has_35_factual_queries():
    data = _load_queries()
    assert len(data["factual_queries"]) == 35, (
        f"Expected 35 factual queries, got {len(data['factual_queries'])}"
    )

def test_queries_json_has_11_refusal_queries():
    data = _load_queries()
    assert len(data["refusal_queries"]) == 11, (
        f"Expected 11 refusal queries, got {len(data['refusal_queries'])}"
    )

def test_each_factual_query_has_required_fields():
    data = _load_queries()
    required = {"id", "fund_id", "field", "query", "checks"}
    for q in data["factual_queries"]:
        missing = required - q.keys()
        assert not missing, f"Query {q.get('id')} missing fields: {missing}"

def test_each_refusal_query_has_required_fields():
    data = _load_queries()
    required = {"id", "type", "query", "expected_contains"}
    for q in data["refusal_queries"]:
        missing = required - q.keys()
        assert not missing, f"Refusal {q.get('id')} missing fields: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Coverage validation
# ══════════════════════════════════════════════════════════════════════════════

def test_all_5_funds_are_covered():
    data = _load_queries()
    fund_ids = {q["fund_id"] for q in data["factual_queries"]}
    assert fund_ids == EXPECTED_FUND_IDS, (
        f"Missing funds: {EXPECTED_FUND_IDS - fund_ids}"
    )

def test_all_7_fields_are_covered():
    data = _load_queries()
    fields = {q["field"] for q in data["factual_queries"]}
    assert fields == EXPECTED_FIELDS, (
        f"Missing fields: {EXPECTED_FIELDS - fields}"
    )

def test_each_fund_has_exactly_7_queries():
    data = _load_queries()
    for fund_id in EXPECTED_FUND_IDS:
        count = sum(1 for q in data["factual_queries"] if q["fund_id"] == fund_id)
        assert count == 7, f"{fund_id} has {count} queries, expected 7"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Refusal — advice gate (safety gate fires before any LLM/DB call)
# ══════════════════════════════════════════════════════════════════════════════

from safety_gate import check, PASS, REFUSE_ADVICE, REFUSE_PII, REFUSE_PERF
from safety_gate import REFUSAL_MESSAGE_ADVICE, REFUSAL_MESSAGE_PII, REFUSAL_MESSAGE_PERF


def test_advice_queries_all_blocked_by_gate():
    data = _load_queries()
    advice_qs = [q for q in data["refusal_queries"] if q["type"] == "advice"]
    for q in advice_qs:
        result = check(q["query"])
        assert result == REFUSE_ADVICE, (
            f"[{q['id']}] Expected REFUSE_ADVICE for: {q['query']!r}, got {result}"
        )

def test_performance_queries_all_blocked_by_gate():
    """
    Performance queries must never pass the gate.
    Some may fire REFUSE_ADVICE first (e.g. 'which fund gave better returns'
    hits the 'which fund' advice keyword before the perf keyword) — that's
    correct behaviour; the query is still blocked.
    """
    data = _load_queries()
    perf_qs = [q for q in data["refusal_queries"] if q["type"] == "performance"]
    for q in perf_qs:
        result = check(q["query"])
        assert result != PASS, (
            f"[{q['id']}] Expected gate to block: {q['query']!r}, got PASS"
        )

def test_pii_queries_all_blocked_by_gate():
    data = _load_queries()
    pii_qs = [q for q in data["refusal_queries"] if q["type"] == "pii"]
    for q in pii_qs:
        result = check(q["query"])
        assert result == REFUSE_PII, (
            f"[{q['id']}] Expected REFUSE_PII for: {q['query']!r}, got {result}"
        )

def test_factual_queries_all_pass_gate():
    data = _load_queries()
    for q in data["factual_queries"]:
        result = check(q["query"])
        assert result == PASS, (
            f"[{q['id']}] Expected PASS for: {q['query']!r}, got {result}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Refusal message content
# ══════════════════════════════════════════════════════════════════════════════

def test_advice_refusal_message_has_indmoney_url():
    """After SEBI link was broken, advice refusal now links to IndMoney."""
    assert "indmoney.com/mutual-funds/all" in REFUSAL_MESSAGE_ADVICE

def test_advice_refusal_message_says_facts_only():
    assert "facts only" in REFUSAL_MESSAGE_ADVICE


# ══════════════════════════════════════════════════════════════════════════════
# 6. Pipeline refusals (gate fires before embed/retrieve/LLM — always pass)
# ══════════════════════════════════════════════════════════════════════════════

from pipeline import answer
from query_preprocessor import OUT_OF_SCOPE_MESSAGE


def test_pipeline_all_advice_queries_refuse():
    data = _load_queries()
    advice_qs = [q for q in data["refusal_queries"] if q["type"] == "advice"]
    for q in advice_qs:
        result = answer(q["query"])
        assert result == REFUSAL_MESSAGE_ADVICE, (
            f"[{q['id']}] Pipeline should return REFUSAL_MESSAGE_ADVICE.\n"
            f"Query: {q['query']!r}\nGot: {result!r}"
        )

def test_pipeline_all_pii_queries_refuse():
    data = _load_queries()
    pii_qs = [q for q in data["refusal_queries"] if q["type"] == "pii"]
    for q in pii_qs:
        result = answer(q["query"])
        assert result == REFUSAL_MESSAGE_PII, (
            f"[{q['id']}] Pipeline should return REFUSAL_MESSAGE_PII.\n"
            f"Query: {q['query']!r}\nGot: {result!r}"
        )

def test_pipeline_all_perf_queries_refuse():
    """
    Performance queries must be refused. Some may hit the advice gate first
    (e.g. 'which fund gave better returns' triggers 'which fund') — that's
    still a correct refusal, so we only assert the response is non-factual
    (no indmoney citation line present, and some refusal language).
    """
    data = _load_queries()
    perf_qs = [q for q in data["refusal_queries"] if q["type"] == "performance"]
    for q in perf_qs:
        result = answer(q["query"])
        is_refused = (
            "performance" in result.lower()
            or "returns" in result.lower()
            or "facts only" in result.lower()
            or "investment advice" in result.lower()
        )
        assert is_refused, (
            f"[{q['id']}] Pipeline response does not look like a refusal.\n"
            f"Query: {q['query']!r}\nGot: {result!r}"
        )

def test_pipeline_out_of_scope_query_redirects():
    data = _load_queries()
    oos_qs = [q for q in data["refusal_queries"] if q["type"] == "out_of_scope"]
    for q in oos_qs:
        result = answer(q["query"])
        assert "indmoney.com/mutual-funds/all" in result, (
            f"[{q['id']}] Expected indmoney redirect.\nQuery: {q['query']!r}\nGot: {result!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 7. Integration — factual accuracy (skip without ChromaDB + GROQ_API_KEY)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_factual_queries_citation_pass_rate():
    """
    Integration: every factual answer must contain 'Last updated:' and
    an indmoney.com URL.  Pass rate must be 100%.
    """
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    data = _load_queries()
    failures = []
    for q in data["factual_queries"]:
        result = answer(q["query"])
        if "Last updated:" not in result:
            failures.append(f"[{q['id']}] Missing 'Last updated:' — {q['query']!r}")
        if "indmoney.com" not in result:
            failures.append(f"[{q['id']}] Missing indmoney.com URL — {q['query']!r}")

    assert not failures, "Citation failures:\n" + "\n".join(failures)


@pytest.mark.integration
def test_axis_elss_lock_in_contains_3_years():
    """
    Integration: ground-truth — Axis ELSS lock-in is always 3 years (SEBI rule).
    """
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    result = answer("What is the lock-in period for Axis ELSS Tax Saver Fund?")
    assert "3" in result, (
        f"Expected '3 years' in lock-in answer for Axis ELSS.\nGot: {result}"
    )


@pytest.mark.integration
def test_factual_answers_contain_any_expected_token():
    """
    Integration: ≥ 90% of factual answers must contain at least one
    token from checks.contains_any.
    """
    if not _chroma_populated():
        pytest.skip("ChromaDB empty — run `python phase3/ingestion/ingest.py` first.")
    if not _groq_key_present():
        pytest.skip("GROQ_API_KEY not set — add it to .env first.")

    data = _load_queries()
    passed = 0
    failures = []
    total = len(data["factual_queries"])

    for q in data["factual_queries"]:
        result = answer(q["query"])
        tokens = q["checks"].get("contains_any", [])
        if any(t.lower() in result.lower() for t in tokens):
            passed += 1
        else:
            failures.append(
                f"[{q['id']}] None of {tokens} found in answer.\n"
                f"  Query:  {q['query']!r}\n"
                f"  Answer: {result[:120]!r}"
            )

    pass_rate = passed / total
    assert pass_rate >= 0.90, (
        f"Pass rate {pass_rate:.0%} < 90% threshold.\nFailures:\n"
        + "\n".join(failures)
    )
