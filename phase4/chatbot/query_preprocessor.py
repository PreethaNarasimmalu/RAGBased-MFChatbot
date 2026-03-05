"""
Phase 4 — Query Preprocessor

Responsibilities:
  1. Fund name normalisation — maps user aliases to a canonical fund_id
  2. Out-of-scope detection  — if the query looks like a mutual-fund question
     but doesn't match any of our 5 funds, flag it so the pipeline can
     redirect to https://www.indmoney.com/mutual-funds/all

Out-of-scope rule (from constraints):
  Any query about a mutual fund that is NOT one of the 5 in scope must
  receive a polite response and a link to indmoney.com/mutual-funds/all.
"""

# ── Fund aliases ───────────────────────────────────────────────────────────────

FUND_ALIASES: dict[str, list[str]] = {
    "hdfc_small_cap": [
        "hdfc small cap",
        "hdfc smallcap",
        "hdfc small-cap",
        "hdfc small cap fund",
        "hdfc small cap direct",
    ],
    "axis_elss": [
        "axis elss",
        "axis elss tax saver",
        "elss fund",
        "tax saver fund",
        "axis tax saver",
        "axis elss fund",
        "elss tax saver",
        "axis elss tax",
    ],
    "axis_large_mid_cap": [
        "axis large mid cap",
        "axis large and mid cap",
        "axis large & mid cap",
        "large mid cap",
        "large mid",
        "axis large mid",
        "axis large midcap",
        "axis large & midcap",
    ],
    "axis_nifty_100": [
        "axis nifty 100",
        "nifty 100 index",
        "axis index",
        "axis nifty 100 index",
        "nifty 100",
        "axis nifty100",
    ],
    "hdfc_pvt_bank_etf": [
        "hdfc private bank etf",
        "private bank etf",
        "hdfc nifty private bank etf",
        "hdfc pvt bank etf",
        "hdfc etf",
        "private bank fund",
        "nifty private bank etf",
    ],
}

FUND_CANONICAL_NAMES: dict[str, str] = {
    "hdfc_small_cap":     "HDFC Small Cap Fund",
    "axis_elss":          "Axis ELSS Tax Saver Fund",
    "axis_large_mid_cap": "Axis Large & Mid Cap Fund",
    "axis_nifty_100":     "Axis Nifty 100 Index Fund",
    "hdfc_pvt_bank_etf":  "HDFC Nifty Private Bank ETF",
}

FUND_URLS: dict[str, str] = {
    "hdfc_small_cap":     "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
    "axis_elss":          "https://www.indmoney.com/mutual-funds/axis-elss-tax-saver-fund-direct-plan-growth-option-2631",
    "axis_large_mid_cap": "https://www.indmoney.com/mutual-funds/axis-large-mid-cap-fund-direct-growth-1002028",
    "axis_nifty_100":     "https://www.indmoney.com/mutual-funds/axis-nifty-100-index-fund-direct-growth-1005056",
    "hdfc_pvt_bank_etf":  "https://www.indmoney.com/mutual-funds/hdfc-nifty-private-bank-etf-1042349",
}

# ── Whitelist patterns ─────────────────────────────────────────────────────────
# Queries that look like MF questions but should always reach the LLM
# (e.g. asking which funds the bot covers — no alias needed, no redirect).
_WHITELIST_PATTERNS = [
    "which funds",
    "what funds",
    "5 funds",
    "five funds",
    "funds do you cover",
    "funds you cover",
    "funds you have",
    "funds you know",
    "list of funds",
    "funds covered",
    "what are the funds",
]

# ── Out-of-scope detection ─────────────────────────────────────────────────────
# Keywords that signal the query is about a mutual fund (broad)
_MF_KEYWORDS = [
    "fund",
    "mutual fund",
    "sip",
    "nav",
    "expense ratio",
    "exit load",
    "amc",
    "folio",
    "redemption",
    "nifty",
    "sensex",
    "etf",
    "elss",
    "direct plan",
    "regular plan",
    "lock-in",
    "lock in",
    "benchmark",
    "riskometer",
    "lump sum",
    "lumpsum",
]

OUT_OF_SCOPE_LINK = "https://www.indmoney.com/mutual-funds/all"

OUT_OF_SCOPE_MESSAGE = (
    "I don't have details on that fund — I currently cover only 5 specific mutual funds. "
    "You can explore all available mutual funds on INDmoney here: "
    f"{OUT_OF_SCOPE_LINK}"
)


# ── Public API ─────────────────────────────────────────────────────────────────

def detect_fund(query: str) -> str | None:
    """
    Detect which of our 5 funds the query is about.

    Returns the fund_id if exactly one fund alias matched, else None.
    Multiple matches (ambiguous) also return None → broad retrieval.
    """
    lower = query.lower()
    matches = [
        fid for fid, aliases in FUND_ALIASES.items()
        if any(alias in lower for alias in aliases)
    ]
    return matches[0] if len(matches) == 1 else None


def is_mf_query(query: str) -> bool:
    """Return True if the query contains mutual-fund related keywords."""
    lower = query.lower()
    return any(kw in lower for kw in _MF_KEYWORDS)


def preprocess(query: str) -> tuple[str, str | None, bool]:
    """
    Preprocess the user query.

    Returns:
        cleaned_query  — whitespace-stripped query string
        fund_id        — matched fund_id, or None (broad retrieval)
        out_of_scope   — True if query looks like an MF question but no
                         fund alias matched (→ redirect to all-funds link)
    """
    cleaned = query.strip()
    fund_id = detect_fund(cleaned)

    # Whitelisted queries (e.g. "what funds do you cover?") should never be
    # flagged as out-of-scope even though they match MF keywords.
    lower = cleaned.lower()
    is_whitelisted = any(p in lower for p in _WHITELIST_PATTERNS)

    # Out-of-scope: MF-related query but no matching fund alias
    out_of_scope = (fund_id is None) and is_mf_query(cleaned) and not is_whitelisted

    return cleaned, fund_id, out_of_scope
