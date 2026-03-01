# Complete Project Context & Phase 2 Handoff

> **Session date:** 2026-03-01
> **Branch:** `claude/mutual-fund-rag-chatbot-with-scraping-DjqzA`
> **Purpose:** Full context from project start so you can continue seamlessly on your Windows terminal

---

## 1. Project Overview

**RAG-Based Mutual Fund FAQ Chatbot**

- **Platform:** INDmoney (indmoney.com) public fund pages
- **Goal:** Answer factual questions about 5 specific mutual fund schemes scraped from INDmoney
- **Strict rule:** Facts only — no investment advice, no return predictions, no portfolio recommendations
- **Approach:** Scrape → Chunk → Embed → Retrieve → Generate (classic RAG)

---

## 2. The 5 Funds in Scope

These are defined in `phase1/data/sources.json`:

```json
{
  "funds": [
    {
      "fund_id": "hdfc_small_cap",
      "fund_name": "HDFC Small Cap Fund - Direct Growth",
      "amc": "HDFC",
      "category": "Small Cap",
      "url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580"
    },
    {
      "fund_id": "axis_elss",
      "fund_name": "Axis ELSS Tax Saver Fund - Direct Plan Growth",
      "amc": "Axis",
      "category": "ELSS / Tax Saver",
      "url": "https://www.indmoney.com/mutual-funds/axis-elss-tax-saver-fund-direct-plan-growth-option-2631"
    },
    {
      "fund_id": "axis_large_mid_cap",
      "fund_name": "Axis Large & Mid Cap Fund - Direct Growth",
      "amc": "Axis",
      "category": "Large & Mid Cap",
      "url": "https://www.indmoney.com/mutual-funds/axis-large-mid-cap-fund-direct-growth-1002028"
    },
    {
      "fund_id": "axis_nifty_100",
      "fund_name": "Axis Nifty 100 Index Fund - Direct Growth",
      "amc": "Axis",
      "category": "Index (Large Cap)",
      "url": "https://www.indmoney.com/mutual-funds/axis-nifty-100-index-fund-direct-growth-1005056"
    },
    {
      "fund_id": "hdfc_pvt_bank_etf",
      "fund_name": "HDFC Nifty Private Bank ETF",
      "amc": "HDFC",
      "category": "ETF (Sectoral)",
      "url": "https://www.indmoney.com/mutual-funds/hdfc-nifty-private-bank-etf-1042349"
    }
  ]
}
```

---

## 3. Facts the Chatbot Can Answer

| Field | Description |
|---|---|
| `expense_ratio` | Annual fee charged by the fund (direct plan %) |
| `exit_load` | Fee on early redemption + applicable window |
| `min_sip_amount` | Smallest monthly SIP amount allowed |
| `lock_in_period` | **3 years for ELSS only** (`axis_elss`); `null` for all others |
| `riskometer` | SEBI-defined risk label (e.g. "Very High") |
| `benchmark` | Index the fund is measured against |
| `statement_download` | How to get capital-gains / ELSS tax statement on INDmoney |

**The user specifically emphasized these 4 must be scraped (not assumed) for all 5 funds:**
1. Expense Ratio
2. Exit Load
3. Minimum SIP
4. Lock-in Period (exists for ELSS, null for others)

---

## 4. Technology Stack (already decided, do not change)

| Layer | Technology | Reason |
|---|---|---|
| Scraping | Playwright | INDmoney is a React SPA — `requests` alone can't render it |
| HTML Parsing | BeautifulSoup 4 + lxml | Extract structured fields from rendered HTML |
| Vector Store | ChromaDB (local) | Zero infra; sufficient for 35-chunk corpus |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Free, runs locally |
| LLM | Groq API — `llama-3.3-70b-versatile` | Fast, free tier, OpenAI-compatible SDK |
| UI | Streamlit | Fastest path to working chat interface |
| Config | python-dotenv | Keep GROQ_API_KEY out of code |
| Testing | pytest + pytest-playwright | |
| Scheduler | GitHub Actions (cron) | Daily scrape at midnight IST |

All dependencies already in `requirements.txt` — nothing new to add for Phase 2.

---

## 5. Full Phase Plan

```
Phase 1 ── Foundation & Setup          ✅ COMPLETE
            requirements.txt · .env.example · sources.json · project skeleton
            All Phase 1 gate tests pass

Phase 2 ── Web Scraping                ← YOU ARE HERE
            scraper.py  (Playwright-based JS scraper)
            parser.py   (extract structured facts from raw HTML)
            Output: phase2/data/raw/<fund_id>.json

Phase 3 ── Data Processing & Embedding
            chunker.py · embedder.py · vector_store.py · ingest.py
            Output: ChromaDB collection populated with metadata-tagged chunks

Phase 4 ── Chatbot Core (RAG Pipeline)
            safety_gate.py · query_preprocessor.py
            prompt_templates.py · llm_client.py · pipeline.py

Phase 5 ── User Interface
            ui/app.py  (Streamlit)

Phase 6 ── Evaluation & QA

Phase 7 ── Scheduler (GitHub Actions)
```

---

## 6. Current Repository Structure

```
RAGBased-MFChatbot/                   ← repo root
├── ARCHITECTURE.md                   ← full architecture (538 lines)
├── PHASE2_CONTEXT.md                 ← THIS FILE
├── requirements.txt
├── .env.example                      ← contains: GROQ_API_KEY=your_groq_api_key_here
├── .gitignore
├── chroma_db/
│   └── .gitkeep
└── phase1/                           ← Phase 1 complete
    ├── data/
    │   ├── sources.json              ← 5 funds defined
    │   ├── raw/                      ← .gitkeep only (Phase 2 fills phase2/data/raw/)
    │   └── processed/                ← .gitkeep only
    ├── scraping/
    │   └── __init__.py               ← empty
    ├── ingestion/
    │   └── __init__.py               ← empty
    ├── chatbot/
    │   └── __init__.py               ← empty
    ├── ui/
    │   └── __init__.py               ← empty
    ├── eval/
    │   └── .gitkeep
    └── tests/
        ├── __init__.py
        └── test_phase1.py            ← all tests pass ✅
```

---

## 7. Phase 1 Test File (for reference — already passing)

`phase1/tests/test_phase1.py` verifies:
- Required directory structure exists
- `sources.json` is valid with all 5 funds and required fields
- All 5 INDmoney URLs return reachable HTML via Playwright

All Phase 1 gate tests pass on the Windows machine.

---

## 8. Phase 2 — What Needs to Be Built

### Folder to create: `phase2/`

```
phase2/
├── scraping/
│   ├── __init__.py
│   ├── scraper.py     ← Playwright: renders each page, extracts raw data via parser
│   └── parser.py      ← BeautifulSoup: finds exact fields in rendered HTML
├── data/
│   └── raw/
│       ├── hdfc_small_cap.json
│       ├── axis_elss.json
│       ├── axis_large_mid_cap.json
│       ├── axis_nifty_100.json
│       └── hdfc_pvt_bank_etf.json
└── tests/
    ├── __init__.py
    └── test_phase2.py
```

### Output JSON per fund:

```json
{
  "fund_id": "axis_elss",
  "fund_name": "Axis ELSS Tax Saver Fund - Direct Plan Growth",
  "amc": "Axis",
  "category": "ELSS / Tax Saver",
  "expense_ratio": "0.55%",
  "exit_load": "Nil",
  "min_sip_amount": "₹500",
  "lock_in_period": "3 years",
  "riskometer": "Very High",
  "benchmark": "Nifty 500 TRI",
  "source_url": "https://www.indmoney.com/mutual-funds/axis-elss-tax-saver-fund-direct-plan-growth-option-2631",
  "scraped_at": "2026-03-01T10:00:00+05:30"
}
```

```json
{
  "fund_id": "hdfc_small_cap",
  "fund_name": "HDFC Small Cap Fund - Direct Growth",
  "amc": "HDFC",
  "category": "Small Cap",
  "expense_ratio": "0.55%",
  "exit_load": "1% if redeemed within 1 year",
  "min_sip_amount": "₹100",
  "lock_in_period": null,
  "riskometer": "Very High",
  "benchmark": "Nifty Small Cap 250 TRI",
  "source_url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
  "scraped_at": "2026-03-01T10:00:00+05:30"
}
```

**Key rules:**
- `lock_in_period` = `"3 years"` for `axis_elss` only; `null` for the other 4
- `min_sip_amount` = likely `null` for `hdfc_pvt_bank_etf` (ETF, no SIP) — verify from page
- Never fabricate a value — if the field is not on the page, store `null`
- `scraped_at` must be a real ISO-8601 timestamp of when the scrape ran

---

## 9. Scraper Design (from ARCHITECTURE.md)

```python
# scraper.py behaviour:
# 1. Read sources.json — get all 5 fund URLs
# 2. For each fund (with 3-second polite delay between requests):
#    a. Launch Playwright headless Chromium
#    b. Set realistic User-Agent
#    c. Navigate to fund URL, wait for networkidle
#    d. Wait extra 3s for lazy-loaded sections
#    e. Get page.content() (full rendered HTML)
#    f. Pass HTML to parser.py
#    g. Add fund_id, source_url, scraped_at to parsed result
#    h. Write to phase2/data/raw/<fund_id>.json
# 3. Print summary of what was scraped
```

```python
# parser.py behaviour:
# 1. Receive rendered HTML string
# 2. Use BeautifulSoup to find each field
# 3. Search by text labels ("Expense Ratio", "Exit Load", "Minimum SIP Amount",
#    "Lock-in Period", "Risk", "Benchmark") NOT by CSS class names
#    (class names in React apps are auto-generated and change on redeploy)
# 4. Return dict with all fields — None if field not found
```

---

## 10. Why the Server Session Could Not Complete Phase 2

The CI/server environment runs behind an egress proxy. The proxy's `allowed_hosts` list does **not** include `indmoney.com`. Every attempt to reach the site returns `403 host_not_allowed`.

This is why Phase 2 must be run from your **Windows machine**, which has unrestricted internet access.

---

## 11. Phase 2 Gate Test Requirements (`test_phase2.py`)

The test file must verify all of the following:

### Structural tests
1. `phase2/` directory exists
2. `phase2/data/raw/` directory exists
3. `phase2/scraping/scraper.py` exists
4. `phase2/scraping/parser.py` exists

### Data tests (for each of the 5 funds)
5. JSON file exists: `phase2/data/raw/<fund_id>.json`
6. File is valid JSON (can be loaded without error)
7. All required fields are present: `fund_id`, `fund_name`, `amc`, `category`, `expense_ratio`, `exit_load`, `min_sip_amount`, `lock_in_period`, `riskometer`, `benchmark`, `source_url`, `scraped_at`
8. `source_url` starts with `https://www.indmoney.com/`
9. `scraped_at` is a valid ISO-8601 datetime string
10. `expense_ratio` is non-null and contains `%`
11. `exit_load` is non-null and non-empty
12. `riskometer` is non-null and non-empty
13. `benchmark` is non-null and non-empty

### ELSS-specific test
14. `axis_elss` fund has `lock_in_period` = `"3 years"` (exact string or contains "3")

### Non-ELSS lock-in test
15. All 4 non-ELSS funds have `lock_in_period` = `null`

### ETF SIP test
16. `hdfc_pvt_bank_etf` has `min_sip_amount` = `null` (ETFs don't support SIP)

### Non-ETF SIP test
17. All 4 non-ETF funds have `min_sip_amount` non-null and starts with `₹`

---

## 12. How to Start on Your Windows Terminal

```powershell
# Step 1 — Navigate to project
cd C:\Users\Preetha\Desktop\Projects\RAG-MFChatbot\RAGBased-MFChatbot

# Step 2 — Activate your venv
.venv\Scripts\activate

# Step 3 — Ensure you're on the correct branch and it's up to date
git fetch origin
git checkout claude/mutual-fund-rag-chatbot-with-scraping-DjqzA
git pull origin claude/mutual-fund-rag-chatbot-with-scraping-DjqzA

# Step 4 — Launch Claude Code
claude
```

**Then say to Claude:**
> "Read PHASE2_CONTEXT.md and implement Phase 2 — create the phase2/ folder, scrape all 5 INDmoney pages to extract expense ratio, exit load, minimum SIP, and lock-in period, generate the JSON files, write tests, and run them."

Claude will:
1. Read this file for full context
2. Scrape one INDmoney page first to inspect actual HTML structure
3. Build `parser.py` with real selectors from that inspection
4. Run scraper on all 5 funds
5. Verify all JSON files look correct
6. Write and run `test_phase2.py`
7. Commit and push

---

## 13. Git Info

- **Active branch:** `claude/mutual-fund-rag-chatbot-with-scraping-DjqzA`
- **Remote:** `origin/claude/mutual-fund-rag-chatbot-with-scraping-DjqzA`
- **Push command:** `git push -u origin claude/mutual-fund-rag-chatbot-with-scraping-DjqzA`
- Phase 2 files go in `phase2/` at repo root (parallel to `phase1/`)
- The 5 JSON files in `phase2/data/raw/` must be **committed** (not gitignored) so CI can verify them

### Recent commits (Phase 1):
```
be15cb9 fix: add .gitkeep for workflows dir and cross-platform Chromium path
cbebeea Fix file placement: move project-level files to repo root
b502b13 Reorganise Phase 1 into phase1/ folder
8ff8bb0 Phase 1: Foundation & Setup
fc817a8 Switch LLM to Groq API (llama-3.3-70b-versatile)
```

---

## 14. Safety / Refusal Rules (for later phases — Phase 4)

The chatbot must refuse:
- "Should I invest in…?" / "Which fund is better?"
- Return predictions / past performance comparisons
- Portfolio allocation / tax optimisation advice
- Any query containing PAN, Aadhaar, account number, OTP, phone, or email

Safe refusal message (exact wording):
> "This assistant provides facts only and does not offer investment advice. For personalised guidance, consult a SEBI-registered investment adviser: https://www.sebi.gov.in/investors.html"

---

## 15. LLM Config (Phase 4 — for reference)

```
Model:       llama-3.3-70b-versatile  (via Groq API)
Base URL:    https://api.groq.com/openai/v1
API key:     GROQ_API_KEY  (set in .env — never commit)
Temperature: 0.0  (deterministic — financial facts must be exact)
Max tokens:  200
```

---

*This file was created by the Claude Code server session on 2026-03-01.*
*Continue development on your Windows terminal where indmoney.com is accessible.*
