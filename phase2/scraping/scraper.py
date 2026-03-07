"""
Phase 2 — Web Scraper

Playwright-based headless browser scraper for 5 INDmoney mutual fund pages.
For each fund, navigates the URL and intercepts the /_next/data/ JSON response
that Next.js fetches for page props, then delegates to parser.py.

Usage (run from repo root or phase2/):
    python phase2/scraping/scraper.py

Output:
    phase2/data/raw/<fund_id>.json  — one file per fund

Design notes:
  • INDmoney is a Next.js SPA. On navigation it fetches page props via
    /_next/data/{buildId}/<slug>.json — a plain JSON endpoint.
  • We register a Playwright response listener BEFORE page.goto() to capture
    that JSON directly. This is faster than waiting for networkidle and avoids
    HTML parsing entirely.
  • Fallback: if the _next/data response is not seen within the timeout, we
    fall back to reading __NEXT_DATA__ from page.content() (the SSR embed).
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
from parser import parse_fund_json, parse_fund_html  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return json.load(f)["funds"]


def _chromium_launch_kwargs() -> dict:
    """
    Return kwargs for p.chromium.launch().
    Uses --no-sandbox on Linux/CI (required on Ubuntu GitHub Actions runners).
    """
    args = [
        "--disable-blink-features=AutomationControlled",
    ]
    if sys.platform != "win32":
        args += ["--no-sandbox", "--disable-setuid-sandbox"]
    return {"headless": True, "args": args}


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_all_funds(delay_seconds: int = 3) -> dict[str, dict]:
    """
    Scrape all 5 INDmoney fund pages and write JSON output files.

    Strategy:
      1. Before navigating, attach a response listener that watches for
         /_next/data/ API responses (the Next.js page-props JSON endpoint).
      2. Navigate with wait_until="domcontentloaded" (faster, no networkidle hang).
      3. If the listener captured a _next/data payload, parse it directly (JSON).
      4. Otherwise fall back to page.content() + __NEXT_DATA__ HTML parsing.

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
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for i, fund in enumerate(funds):
            fund_id = fund["fund_id"]
            url     = fund["url"]
            print(f"\n[{i + 1}/{len(funds)}] Scraping {fund_id} ...")
            print(f"    URL: {url}")

            # Collect any /_next/data/ response payload for this navigation
            captured: dict = {}

            def _on_response(response, _captured=captured):
                if "/_next/data/" in response.url and response.status == 200:
                    try:
                        _captured["data"] = response.json()
                        _captured["url"]  = response.url
                    except Exception:
                        pass

            page.on("response", _on_response)

            try:
                nav_response = page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                status = nav_response.status if nav_response else None

                if status is None or status >= 400:
                    print(f"    ERROR: HTTP {status} - skipping")
                    continue

                if captured.get("data"):
                    print(f"    Source: _next/data intercepted ({captured['url'].split('/')[-1]})")
                    fund_data = parse_fund_json(captured["data"], fund)
                else:
                    # Fallback: wait a bit more for the SSR __NEXT_DATA__ embed
                    print("    _next/data not seen -> falling back to __NEXT_DATA__ HTML parse")
                    page.wait_for_load_state("networkidle", timeout=30_000)
                    html      = page.content()
                    fund_data = parse_fund_html(html, fund)

                out_path = RAW_DIR / f"{fund_id}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(fund_data, f, ensure_ascii=False, indent=2)

                print(f"    OK -> {out_path}")
                _print_summary(fund_data)
                results[fund_id] = fund_data

            except Exception as exc:
                print(f"    ERROR: {exc}")

            finally:
                page.remove_listener("response", _on_response)

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
        status = "OK" if value is not None else "- (null)"
        display = value if value is not None else ""
        print(f"      {label:16s}: {status}  {display}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = scrape_all_funds()
    if not results:
        sys.exit(1)
