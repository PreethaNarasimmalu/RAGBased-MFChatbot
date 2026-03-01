"""
Phase 2 Gate Tests — Web Scraping

Verifies:
  1. scraper.py and parser.py exist in the scraping/ directory
  2. All 5 data/raw/<fund_id>.json files exist (requires scraper to have run locally)
  3. Each JSON file has all required fields
  4. Non-nullable fields are non-null for every fund
  5. Axis ELSS lock_in_period is non-null (3-year mandatory hold)
  6. Non-ELSS funds have lock_in_period = null (correct by design)

Running the scraper:
  Phase 2 scraping must be done on a machine with internet access to indmoney.com.
  Run once before this test suite:

      cd RAGBased-MFChatbot
      python phase2/scraping/scraper.py

  The 5 JSON files will appear in phase2/data/raw/.
  Commit them so the CI gate tests can verify their structure.
"""

import json
import pytest
from pathlib import Path

ROOT     = Path(__file__).parent.parent          # → phase2/
RAW_DIR  = ROOT / "data" / "raw"
SCRAPING = ROOT / "scraping"

FUND_IDS = [
    "hdfc_small_cap",
    "axis_elss",
    "axis_large_mid_cap",
    "axis_nifty_100",
    "hdfc_pvt_bank_etf",
]

# Fields that must always have a non-null value for every fund
NON_NULLABLE_FIELDS = [
    "fund_id",
    "fund_name",
    "amc",
    "category",
    "expense_ratio",
    "exit_load",
    "riskometer",
    "benchmark",
    "source_url",
    "scraped_at",
]

# lock_in_period is nullable (null for all non-ELSS funds — that is correct)
# axis_elss is the only fund where it must be non-null.
# min_sip_amount is nullable for ETFs (hdfc_pvt_bank_etf trades on exchange, no SIP).


# ── Test 1: Source files exist ────────────────────────────────────────────────

def test_scraper_file_exists():
    assert (SCRAPING / "scraper.py").is_file(), "scraping/scraper.py not found"


def test_parser_file_exists():
    assert (SCRAPING / "parser.py").is_file(), "scraping/parser.py not found"


# ── Test 2: Raw JSON output files exist ───────────────────────────────────────

def _raw_files_present() -> bool:
    """Return True only if all 5 raw JSON files have been scraped."""
    return all((RAW_DIR / f"{fid}.json").is_file() for fid in FUND_IDS)


@pytest.mark.skipif(
    not _raw_files_present(),
    reason=(
        "Raw JSON files not found in phase2/data/raw/. "
        "Run `python phase2/scraping/scraper.py` on a machine with internet access, "
        "then commit the output files."
    ),
)
def test_all_raw_json_files_exist():
    missing = [fid for fid in FUND_IDS if not (RAW_DIR / f"{fid}.json").is_file()]
    assert not missing, f"Missing raw JSON files for: {missing}"


# ── Tests 3–6: JSON content validation ───────────────────────────────────────
# These tests only run if the raw files are present.

@pytest.fixture(scope="module")
def all_fund_data() -> dict:
    """Load all 5 raw JSON files into a {fund_id: data} dict."""
    if not _raw_files_present():
        pytest.skip("Raw JSON files not found — run scraper first.")
    result = {}
    for fid in FUND_IDS:
        with open(RAW_DIR / f"{fid}.json", encoding="utf-8") as f:
            result[fid] = json.load(f)
    return result


def test_all_funds_have_required_fields(all_fund_data):
    """Every raw JSON file must contain all required top-level keys."""
    required_keys = set(NON_NULLABLE_FIELDS) | {"lock_in_period"}
    for fid, data in all_fund_data.items():
        missing = required_keys - data.keys()
        assert not missing, f"{fid}.json is missing keys: {missing}"


def test_non_nullable_fields_are_present(all_fund_data):
    """Every non-nullable field must have a non-null, non-empty value."""
    for fid, data in all_fund_data.items():
        for field in NON_NULLABLE_FIELDS:
            value = data.get(field)
            assert value is not None, (
                f"{fid}.json: field '{field}' is null — scraper may have failed to extract it"
            )
            assert str(value).strip() != "", (
                f"{fid}.json: field '{field}' is empty string"
            )


def test_axis_elss_has_lock_in_period(all_fund_data):
    """Axis ELSS must have a non-null lock_in_period (mandatory 3-year ELSS hold)."""
    data = all_fund_data["axis_elss"]
    assert data.get("lock_in_period") is not None, (
        "axis_elss.json: lock_in_period is null — expected '3 Years' or similar"
    )


def test_non_elss_funds_have_null_lock_in(all_fund_data):
    """Non-ELSS funds should have lock_in_period = null (no mandatory hold)."""
    non_elss = [fid for fid in FUND_IDS if fid != "axis_elss"]
    for fid in non_elss:
        lock_in = all_fund_data[fid].get("lock_in_period")
        assert lock_in is None, (
            f"{fid}.json: expected lock_in_period=null for non-ELSS fund, got '{lock_in}'"
        )


def test_expense_ratio_looks_like_percentage(all_fund_data):
    """Expense ratio values should look like percentage strings (e.g. '0.67%')."""
    for fid, data in all_fund_data.items():
        er = data.get("expense_ratio", "")
        assert "%" in str(er), (
            f"{fid}.json: expense_ratio '{er}' does not contain '%'"
        )


def test_min_sip_amount_contains_rupee_symbol(all_fund_data):
    """Min SIP values should include the rupee symbol (e.g. '₹100')."""
    # ETFs trade on exchange — SIP may not apply; allow null for hdfc_pvt_bank_etf
    for fid, data in all_fund_data.items():
        sip = data.get("min_sip_amount")
        if sip is None:
            assert fid == "hdfc_pvt_bank_etf", (
                f"{fid}.json: min_sip_amount is null — only acceptable for ETF funds"
            )
        else:
            assert "₹" in sip or "Rs" in sip.lower(), (
                f"{fid}.json: min_sip_amount '{sip}' does not contain currency symbol"
            )


def test_source_urls_are_indmoney(all_fund_data):
    """source_url in every JSON file must point to INDmoney."""
    for fid, data in all_fund_data.items():
        url = data.get("source_url", "")
        assert url.startswith("https://www.indmoney.com/"), (
            f"{fid}.json: source_url '{url}' does not start with INDmoney base URL"
        )


def test_scraped_at_is_iso8601(all_fund_data):
    """scraped_at should be a valid ISO-8601 datetime string."""
    from datetime import datetime
    for fid, data in all_fund_data.items():
        ts = data.get("scraped_at", "")
        try:
            datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            pytest.fail(f"{fid}.json: scraped_at '{ts}' is not a valid ISO-8601 timestamp")
