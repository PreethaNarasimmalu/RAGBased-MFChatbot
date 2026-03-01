"""
Phase 2 — HTML Parser

Extracts 7 structured fact fields from a fully-rendered INDmoney fund page.

Strategy: INDmoney is a Next.js SPA. All structured data is embedded in a
  <script id="__NEXT_DATA__" type="application/json"> tag in the rendered HTML.
  We parse that JSON directly — no fragile CSS selectors needed.

JSON path:
  props → pageProps → mutualFundsDetailData → data
    → fund_overview.info[]    (list of {name, value, description} objects)
    → risk_meter.widget_properties.zone_title  (riskometer label)
"""

import json
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_next_data(html: str) -> dict:
    """Find and parse the __NEXT_DATA__ JSON script tag embedded in the page."""
    soup = BeautifulSoup(html, "lxml")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__", "type": "application/json"})
    if not script_tag or not script_tag.string:
        raise ValueError(
            "__NEXT_DATA__ script tag not found in HTML. "
            "The page may not have loaded fully, or INDmoney changed its structure."
        )
    return json.loads(script_tag.string)


def _get_mf_data(next_data: dict) -> dict:
    """Navigate __NEXT_DATA__ to the mutual fund detail data node."""
    try:
        page_props = next_data["props"]["pageProps"]
        return page_props["mutualFundsDetailData"]["data"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"Unexpected __NEXT_DATA__ structure — could not reach "
            f"props.pageProps.mutualFundsDetailData.data: {exc}"
        )


def _info_map(mf_data: dict) -> dict:
    """
    Build a lookup dict from the fund_overview.info array.
    Keys are the 'name' field (e.g., 'Expense ratio', 'Exit Load').
    """
    info_list = mf_data.get("fund_overview", {}).get("info", [])
    return {item["name"]: item for item in info_list if "name" in item}


# ── Public API ────────────────────────────────────────────────────────────────

def parse_fund_html(html: str, fund_meta: dict) -> dict:
    """
    Parse rendered INDmoney fund page HTML and return a structured dict.

    Args:
        html:       Full HTML string from Playwright page.content()
        fund_meta:  Dict from sources.json (fund_id, fund_name, amc, category, url)

    Returns:
        Dict with keys:
            fund_id, fund_name, amc, category,
            expense_ratio, exit_load, min_sip_amount, lock_in_period,
            riskometer, benchmark,
            source_url, scraped_at
        Missing optional fields (e.g. lock_in for non-ELSS) are stored as null.
    """
    next_data = _extract_next_data(html)
    mf_data   = _get_mf_data(next_data)
    info      = _info_map(mf_data)

    # 1. Expense Ratio  (e.g. "0.67%")
    expense_ratio = None
    if "Expense ratio" in info:
        expense_ratio = info["Expense ratio"].get("value") or None

    # 2. Benchmark index  (e.g. "BSE 250 SmallCap TR INR")
    benchmark = None
    if "Benchmark" in info:
        benchmark = info["Benchmark"].get("value") or None

    # 3. Minimum SIP Amount
    #    The 'value' field has format "₹100/₹100" (Lumpsum/SIP).
    #    We take the SIP part (index 1); fall back to full string if no '/'.
    #    ETFs have no SIP and show "--" → stored as null.
    min_sip_amount = None
    if "Min Lumpsum/SIP" in info:
        raw = info["Min Lumpsum/SIP"].get("value", "") or ""
        parts = raw.split("/")
        sip_part = (parts[1].strip() if len(parts) >= 2 else parts[0].strip())
        if sip_part and sip_part != "--":
            min_sip_amount = sip_part

    # 4. Exit Load
    #    INDmoney stores the human-readable sentence in 'description' when a load
    #    applies (e.g. "1% if redeemed in 0-1 Years").
    #    For funds with no exit load it leaves description empty and puts "Nil"
    #    (or similar) in the 'value' field — so we fall back to value if needed.
    #    Strip the redundant "Exit Load of " prefix if present.
    exit_load = None
    if "Exit Load" in info:
        desc = info["Exit Load"].get("description", "") or ""
        cleaned = re.sub(r"^Exit Load of\s*", "", desc, flags=re.IGNORECASE).strip()
        if not cleaned:
            # Fall back to the 'value' field (e.g. "Nil", "0 Nil")
            val = info["Exit Load"].get("value", "") or ""
            cleaned = val.strip()
        exit_load = cleaned or None

    # 5. Lock-in Period
    #    Only ELSS funds have a lock-in. Stored as null for all others.
    lock_in_period = None
    if "Lock In" in info:
        raw = info["Lock In"].get("value", "") or ""
        if raw.lower() not in ("no lock-in", "no lock in", ""):
            lock_in_period = raw.strip() or None

    # 6. Riskometer label  (e.g. "Very High Risk")
    riskometer = None
    try:
        riskometer = mf_data["risk_meter"]["widget_properties"]["zone_title"] or None
    except (KeyError, TypeError):
        pass

    return {
        "fund_id":        fund_meta["fund_id"],
        "fund_name":      fund_meta["fund_name"],
        "amc":            fund_meta["amc"],
        "category":       fund_meta["category"],
        "expense_ratio":  expense_ratio,
        "exit_load":      exit_load,
        "min_sip_amount": min_sip_amount,
        "lock_in_period": lock_in_period,
        "riskometer":     riskometer,
        "benchmark":      benchmark,
        "source_url":     fund_meta["url"],
        "scraped_at":     datetime.now(timezone.utc).isoformat(),
    }
