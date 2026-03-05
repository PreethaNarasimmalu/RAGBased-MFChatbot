"""
Phase 2 — Web Scraper

Playwright-based headless browser scraper for 5 INDmoney mutual fund pages.
For each fund, navigates the URL, waits for full JS render, extracts HTML,
then delegates to parser.py to produce a structured JSON file.

Usage (run from repo root or phase2/):
    python phase2/scraping/scraper.py

Output:
    phase2/data/raw/<fund_id>.json  — one file per fund

Design notes:
  • INDmoney is a React SPA — requests alone cannot get rendered content.
  • Playwright renders the full page (including JS), then we read page.content().
  • wait_until="networkidle" ensures dynamic data sections are populated.
  • Polite crawl: 3-second delay between pages, realistic User-Agent header.
  • Scraper is fully re-runnable; scraped_at timestamp refreshes each run.
"""

import json
import sys
import time
from pathlib import Path

# Allow running from any directory
PHASE2_DIR   = Path(__file__).parent.parent
SOURCES_FILE = PHASE2_DIR / "data" / "sources.json"
RAW_DIR      = PHASE2_DIR / "data" / "raw"

# Make sure parser.py is importable when script is run directly
sys.path.insert(0, str(Path(__file__).parent))
from parser import parse_fund_html  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return json.load(f)["funds"]


def _chromium_launch_kwargs() -> dict:
    """
    Return kwargs for p.chromium.launch().
    Uses --no-sandbox on Linux/CI (required on Ubuntu GitHub Actions runners).
    Lets Playwright resolve the Chromium binary from its own cache.
    """
    kwargs: dict = {"headless": True}
    if sys.platform != "win32":
        # --no-sandbox is required on Ubuntu CI environments (no user namespace support)
        kwargs["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]
    return kwargs


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_all_funds(delay_seconds: int = 3) -> dict[str, dict]:
    """
    Scrape all 5 INDmoney fund pages and write JSON output files.

    Args:
        delay_seconds: Polite delay between consecutive page loads.

    Returns:
        Dict mapping fund_id → parsed fund data (for testing / inspection).
    """
    from playwright.sync_api import sync_playwright

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    funds   = _load_sources()
    results = {}

    launch_kwargs = _chromium_launch_kwargs()

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for i, fund in enumerate(funds):
            fund_id = fund["fund_id"]
            url     = fund["url"]
            print(f"\n[{i + 1}/{len(funds)}] Scraping {fund_id} ...")
            print(f"    URL: {url}")

            try:
                response = page.goto(url, timeout=60_000, wait_until="networkidle")
                status   = response.status if response else None

                if status is None or status >= 400:
                    print(f"    ERROR: HTTP {status} — skipping")
                    continue

                html      = page.content()
                fund_data = parse_fund_html(html, fund)

                out_path = RAW_DIR / f"{fund_id}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(fund_data, f, ensure_ascii=False, indent=2)

                print(f"    OK → {out_path}")
                _print_summary(fund_data)
                results[fund_id] = fund_data

            except Exception as exc:
                print(f"    ERROR: {exc}")

            # Polite delay — skip after the last fund
            if i < len(funds) - 1:
                print(f"    Waiting {delay_seconds}s before next request ...")
                time.sleep(delay_seconds)

        browser.close()

    print(f"\nDone. {len(results)}/{len(funds)} funds scraped successfully.")
    return results


def _print_summary(fund_data: dict) -> None:
    """Print a compact summary of scraped fields for quick visual verification."""
    fields = [
        ("expense_ratio",  "Expense Ratio"),
        ("exit_load",      "Exit Load"),
        ("min_sip_amount", "Min SIP"),
        ("lock_in_period", "Lock-in"),
        ("riskometer",     "Riskometer"),
        ("benchmark",      "Benchmark"),
    ]
    for key, label in fields:
        value = fund_data.get(key)
        status = "OK" if value is not None else "— (null)"
        display = value if value is not None else ""
        print(f"      {label:16s}: {status}  {display}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = scrape_all_funds()
    if not results:
        sys.exit(1)
