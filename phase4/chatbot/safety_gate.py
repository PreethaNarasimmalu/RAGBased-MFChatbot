"""
Phase 4 — Safety Gate

Three-stage input filter (runs before any LLM or vector DB call):

  Stage 1 — Regex blocklist: PII patterns (instant, zero cost)
             PAN · Aadhaar · account numbers · OTPs · phone · email
  Stage 2 — Keyword check:  advice triggers
  Stage 3 — Keyword check:  performance / return claim triggers

Operational constraint: No PII is ever stored. If Stage 1 fires,
the query is dropped immediately and nothing is logged.

Returns one of: PASS | REFUSE_PII | REFUSE_ADVICE | REFUSE_PERF
"""

import re

# ── Stage 1: PII Patterns ──────────────────────────────────────────────────────

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("PAN",     re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')),
    ("Aadhaar", re.compile(r'\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b')),
    ("Phone",   re.compile(r'\b[6-9]\d{9}\b')),
    ("Email",   re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')),
    ("AcctNo",  re.compile(r'\b\d{9,18}\b')),
    ("OTP",     re.compile(r'\b(?:otp|one[\s\-]?time[\s\-]?pass(?:word)?)\b', re.IGNORECASE)),
]

# ── Stage 2: Advice Keywords ───────────────────────────────────────────────────

_ADVICE_KEYWORDS = [
    "should i",
    "recommend",
    "better fund",
    "which fund",
    "should i buy",
    "should i invest",
    "invest in",
    "worth investing",
    "which is better",
    "give advice",
    "financial advice",
    "tax advice",
    "portfolio",
    "outperform",
    "best fund",
]

# ── Stage 3: Performance / Return Keywords ─────────────────────────────────────

_PERFORMANCE_KEYWORDS = [
    "past performance",
    "cagr",
    "annualised return",
    "annualized return",
    "how much will i get",
    "how much profit",
    "historical return",
    "compare performance",
    "better return",
    "gave better return",
    "higher return",
]

# ── Result constants ───────────────────────────────────────────────────────────

PASS          = "PASS"
REFUSE_PII    = "REFUSE_PII"
REFUSE_ADVICE = "REFUSE_ADVICE"
REFUSE_PERF   = "REFUSE_PERF"

# ── Refusal messages (Constraint 4: clarity & transparency, ≤ 3 sentences) ────

REFUSAL_MESSAGE_PII = (
    "I cannot process queries containing personal information "
    "(PAN, Aadhaar, account number, OTP, email, or phone number). "
    "Please remove any personal details and try again."
)

REFUSAL_MESSAGE_ADVICE = (
    "This assistant provides facts only and does not offer investment advice. "
    "For personalised guidance, consult a SEBI-registered investment adviser: "
    "https://www.sebi.gov.in/investors.html"
)

REFUSAL_MESSAGE_PERF = (
    "This assistant does not compute or compare fund returns or past performance. "
    "For official performance data, please refer to the fund's factsheet on INDmoney: "
    "https://www.indmoney.com/mutual-funds/all"
)

_MESSAGES = {
    REFUSE_PII:    REFUSAL_MESSAGE_PII,
    REFUSE_ADVICE: REFUSAL_MESSAGE_ADVICE,
    REFUSE_PERF:   REFUSAL_MESSAGE_PERF,
}


# ── Public API ─────────────────────────────────────────────────────────────────

def check(query: str) -> str:
    """
    Run the safety gate on the raw query string.

    Returns:
        PASS          — safe to proceed to RAG pipeline
        REFUSE_PII    — query contains personal information
        REFUSE_ADVICE — query asks for investment advice
        REFUSE_PERF   — query asks for performance/return data
    """
    # Stage 1: PII (check original case — PAN is uppercase)
    for _label, pattern in _PII_PATTERNS:
        if pattern.search(query):
            return REFUSE_PII

    lower = query.lower()

    # Stage 2: Advice
    for kw in _ADVICE_KEYWORDS:
        if kw in lower:
            return REFUSE_ADVICE

    # Stage 3: Performance claims
    for kw in _PERFORMANCE_KEYWORDS:
        if kw in lower:
            return REFUSE_PERF

    return PASS


def get_refusal_message(gate_result: str) -> str:
    """Return the human-readable refusal message for a given gate result."""
    return _MESSAGES.get(gate_result, "")
