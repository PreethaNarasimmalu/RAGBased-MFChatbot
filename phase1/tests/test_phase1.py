"""
Phase 1 Gate Tests — Foundation & Setup
Verifies:
  1. Required phase1/ directory structure exists
  2. Project-level config files exist at repo root
  3. sources.json is valid and contains all 5 funds
  4. All 5 INDmoney URLs return reachable HTML via Playwright
"""

import json
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT      = Path(__file__).parent.parent        # → phase1/
REPO_ROOT = Path(__file__).parent.parent.parent # → RAGBased-MFChatbot/

REQUIRED_DIRS = [
    "data/raw",
    "data/processed",
    "scraping",
    "ingestion",
    "chatbot",
    "ui",
    "eval",
    ".github/workflows",
]

# Phase1-specific file
REQUIRED_PHASE1_FILES = [
    "data/sources.json",
]

# Project-level files that live at repo root (shared across all phases)
REQUIRED_ROOT_FILES = [
    "requirements.txt",
    ".env.example",
    ".gitignore",
]

REQUIRED_FUND_IDS = {
    "hdfc_small_cap",
    "axis_elss",
    "axis_large_mid_cap",
    "axis_nifty_100",
    "hdfc_pvt_bank_etf",
}


# ── Test 1: Directory structure ───────────────────────────────────────────────

def test_required_directories_exist():
    missing = [d for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
    assert not missing, f"Missing directories: {missing}"


# ── Test 2: Phase1 files and project-level config files ──────────────────────

def test_required_phase1_files_exist():
    missing = [f for f in REQUIRED_PHASE1_FILES if not (ROOT / f).is_file()]
    assert not missing, f"Missing phase1 files: {missing}"


def test_required_root_files_exist():
    missing = [f for f in REQUIRED_ROOT_FILES if not (REPO_ROOT / f).is_file()]
    assert not missing, f"Missing project-root files: {missing}"


# ── Test 3: sources.json structure ───────────────────────────────────────────

def test_sources_json_has_correct_structure():
    with open(ROOT / "data/sources.json") as f:
        sources = json.load(f)

    assert "funds" in sources, "sources.json must have a 'funds' key"
    assert len(sources["funds"]) == 5, f"Expected 5 funds, got {len(sources['funds'])}"

    required_fields = {"fund_id", "fund_name", "amc", "category", "url"}
    for fund in sources["funds"]:
        missing = required_fields - fund.keys()
        assert not missing, f"Fund {fund.get('fund_id', '?')} missing fields: {missing}"


def test_sources_json_has_correct_fund_ids():
    with open(ROOT / "data/sources.json") as f:
        sources = json.load(f)

    found_ids = {fund["fund_id"] for fund in sources["funds"]}
    assert found_ids == REQUIRED_FUND_IDS, (
        f"Fund ID mismatch.\n  Expected: {REQUIRED_FUND_IDS}\n  Found:    {found_ids}"
    )


def test_sources_json_urls_are_indmoney():
    with open(ROOT / "data/sources.json") as f:
        sources = json.load(f)

    for fund in sources["funds"]:
        url = fund["url"]
        assert url.startswith("https://www.indmoney.com/"), (
            f"Fund {fund['fund_id']} has non-INDmoney URL: {url}"
        )


# ── Test 4: URL reachability via Playwright ───────────────────────────────────

def _network_is_available() -> bool:
    """Return True only if outbound internet is reachable from this machine."""
    import socket
    try:
        socket.setdefaulttimeout(5)
        socket.create_connection(("www.indmoney.com", 443))
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _network_is_available(), reason="No outbound internet — skipping URL reachability check")
def test_all_fund_urls_reachable_via_playwright():
    with open(ROOT / "data/sources.json") as f:
        sources = json.load(f)

    failed = []

    # Use the locally cached Chromium executable
    chromium_path = "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chromium_path)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for fund in sources["funds"]:
            fund_id = fund["fund_id"]
            url = fund["url"]
            try:
                response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                status = response.status if response else None

                if status is None or status >= 400:
                    failed.append(f"{fund_id}: HTTP {status}")
                    continue

                content = page.content()
                if len(content) < 500:
                    failed.append(f"{fund_id}: Page content suspiciously small ({len(content)} chars)")

            except Exception as exc:
                failed.append(f"{fund_id}: {exc}")

        browser.close()

    assert not failed, (
        "The following fund URLs failed the Playwright reachability check:\n"
        + "\n".join(f"  • {f}" for f in failed)
    )
