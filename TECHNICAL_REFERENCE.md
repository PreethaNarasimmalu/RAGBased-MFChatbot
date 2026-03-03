# Technical Reference — RAG-Based Mutual Fund FAQ Chatbot

> Deep documentation covering APIs, data flows, storage schemas, architecture
> decisions, deployment, and future improvements.

---

## Table of Contents

1. [Tech Stack at a Glance](#1-tech-stack-at-a-glance)
2. [How the Architecture Was Designed](#2-how-the-architecture-was-designed)
3. [System Overview](#3-system-overview)
4. [External APIs](#4-external-apis)
5. [Internal Module APIs](#5-internal-module-apis)
6. [End-to-End Data Flow](#6-end-to-end-data-flow)
7. [Data Storage Schemas](#7-data-storage-schemas)
8. [Safety & Compliance Layer](#8-safety--compliance-layer)
9. [Deployment Guide](#9-deployment-guide)
10. [Future Improvements](#10-future-improvements)

---

## 1. Tech Stack at a Glance

| Layer | Library / Service | Version pin | Why this choice |
|---|---|---|---|
| **Language** | Python | 3.11+ | Type hints, `match` syntax, latest stdlib |
| **UI framework** | Streamlit | `>=1.32` | Zero-boilerplate chat UI; deploys to Streamlit Cloud for free |
| **Web scraping** | Playwright (Chromium) | `>=1.42` | Only tool that executes JS on React SPAs; native async, GitHub Actions support |
| **HTML parsing** | BeautifulSoup4 | `>=4.12` | Concise CSS-selector API; works on already-rendered HTML from Playwright |
| **Embedding model** | sentence-transformers `all-MiniLM-L6-v2` | `>=2.7` | 384-dim, runs on CPU, no API call, no cost, sufficient for 35 chunks |
| **Vector database** | ChromaDB | `>=0.4` | Embedded (no server), persists to disk, cosine metric, free |
| **LLM inference** | Groq API — `llama-3.3-70b-versatile` | N/A | Free tier, LPU hardware (fast), OpenAI-compatible SDK |
| **LLM SDK** | `groq` Python package | `>=0.9` | Official Groq client; thin wrapper over `httpx` |
| **Config management** | python-dotenv | `>=1.0` | Loads `GROQ_API_KEY` from `.env`; silently skipped if absent |
| **Testing** | pytest | `>=8.0` | Industry standard; parametrised tests for eval suite |
| **Scheduler** | GitHub Actions cron | N/A | Runs independently of sleeping Streamlit Cloud app |
| **Data format** | JSON (stdlib) | built-in | Human-readable, easy to diff, no schema migration needed |

### Dependency interaction diagram

```
Playwright ──scrapes──► BeautifulSoup ──parses──► JSON files
                                                       │
                                              sentence-transformers
                                                       │ embeds
                                                       ▼
                                                  ChromaDB
                                                       │ retrieves
                                                       ▼
User query ──► safety_gate ──► preprocessor ──► pipeline ──► Groq LLM ──► Answer
                                                   ▲
                                          sentence-transformers
                                          (query embedding)
```

---

## 2. How the Architecture Was Designed

### The Problem

INDmoney is a **React single-page application (SPA)**. Fund detail pages render entirely via client-side JavaScript — a plain `requests.get()` only retrieves an empty HTML shell with no fund data. This ruled out any scraping approach that doesn't execute JavaScript.

### Core Constraints That Shaped Every Decision

| Constraint | Impact |
|---|---|
| **No investment advice** | Requires a dual-layer safety gate (fast regex + keyword before LLM ever sees the query) |
| **No PII** | Regex blocklist must fire *before* any data is stored or logged |
| **No performance claims** | Blocked at both safety gate AND encoded in LLM system prompt |
| **Every answer must cite source** | Citation injected by pipeline even if LLM omits it |
| **Only 5 funds** | Queries about other funds must redirect, never fabricate |

### Why Playwright (not Selenium / requests)?

Playwright supports async, headless Chromium out of the box on Ubuntu (including GitHub Actions `ubuntu-latest` runners). It waits for network idle after page load, which is exactly what React SPAs require. Selenium needs separate WebDriver management; `requests` can't execute JS at all.

### Why Fact-by-Fact Chunking (not Sliding Window)?

The corpus is 5 funds × 6–7 facts = **30–35 discrete facts**. Sliding-window chunking is designed for long documents (books, PDFs). Here:
- Each fact is completely self-contained (expense ratio has nothing to do with exit load)
- One chunk per fact = zero risk of cross-fact contamination in retrieved context
- 35 total chunks fits entirely in ChromaDB's in-memory layer — no performance concern

### Why ChromaDB (not Pinecone / Weaviate)?

- Zero infrastructure — runs as a local file on disk (`chroma_db/`)
- 35 chunks is tiny; any vector DB works at this scale
- Persistent across restarts without a server process
- Free; no API key needed; works on Streamlit Cloud

### Why Groq + llama-3.3-70b (not OpenAI / Gemini)?

- Groq offers **free tier** with very high token limits
- llama-3.3-70b inference on Groq is faster than GPT-4o (Groq's LPU hardware)
- OpenAI-compatible SDK — the client is a 3-line swap if you want to switch
- `Temperature = 0.0` is non-negotiable (financial facts must be deterministic)

### Why `all-MiniLM-L6-v2` for Embeddings?

- Runs locally — no API call, no key, no cost, no latency spike
- 384-dimensional embeddings; fast on CPU
- Sufficient for 35 chunks — semantic similarity at this scale is easy

### Why GitHub Actions (not APScheduler / cron)?

Streamlit Cloud **sleeps inactive apps**. Any in-process scheduler (APScheduler, `schedule` library) dies when the app process sleeps. GitHub Actions runs on a separate Ubuntu VM independent of the app — it scrapes, commits, and the app reads fresh data on the next startup.

---

## 3. System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER QUERY                                     │
│              (Streamlit browser or direct pipeline call)              │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    LAYER 1 — SAFETY GATE                              │
│  Stage 1: PII regex (PAN / Aadhaar / phone / email / account / OTP)  │
│  Stage 2: Advice keyword check (should i, recommend, portfolio…)     │
│  Stage 3: Performance keyword check (CAGR, past performance…)        │
│                                                                       │
│   BLOCKED → return refusal message immediately (no LLM / DB call)   │
│   PASSED  → continue to Layer 2                                       │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  LAYER 2 — QUERY PREPROCESSOR                         │
│  • Detect which of the 5 funds the query mentions (alias matching)   │
│  • If MF keyword present but no fund matched → OUT OF SCOPE redirect  │
│  • Clean / strip whitespace                                           │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  LAYER 3 — RETRIEVAL (ChromaDB)                       │
│  • Embed query with all-MiniLM-L6-v2 (384-dim)                       │
│  • Cosine similarity search → top-3 chunks                           │
│  • Optional metadata filter: fund_id (if detected)                   │
│  • Relevance threshold: cosine distance ≤ 1.2                        │
│  • No relevant chunk → return "not found" redirect                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  LAYER 4 — GENERATION (Groq LLM)                     │
│  • Assemble context: [CONTEXT]...[END CONTEXT] + Question            │
│  • Call llama-3.3-70b-versatile via Groq API                         │
│  • Temperature=0.0, max_tokens=300                                    │
│  • Pipeline enforces citation format if LLM omits it                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. External APIs

### 3.1 Groq API (LLM Inference)

| Property | Value |
|---|---|
| Base URL | `https://api.groq.com/openai/v1` |
| Authentication | Bearer token — `GROQ_API_KEY` environment variable |
| SDK | `groq` Python package (OpenAI-compatible) |
| Endpoint used | `POST /chat/completions` |
| Model | `llama-3.3-70b-versatile` |
| Temperature | `0.0` — deterministic (financial facts must not vary) |
| Max tokens | `300` — enough for ≤ 3 sentences + citation line |

**Request structure:**
```json
{
  "model": "llama-3.3-70b-versatile",
  "temperature": 0.0,
  "max_tokens": 300,
  "messages": [
    { "role": "system", "content": "<SYSTEM_PROMPT>" },
    { "role": "user",   "content": "[CONTEXT]\n...\n[END CONTEXT]\n\nQuestion: <query>" }
  ]
}
```

**Response:** `response.choices[0].message.content` (stripped string).

**Error handling:** `RuntimeError` raised if `GROQ_API_KEY` is unset. Network errors bubble up to `pipeline.answer()` which catches `Exception` and returns a user-friendly error string.

---

### 3.2 Playwright (Web Scraping)

| Property | Value |
|---|---|
| Type | Headless browser automation (not an HTTP REST API) |
| Browser | Chromium (installed via `playwright install chromium`) |
| Mode | Headless (no visible browser window) |
| Reason | INDmoney is a React SPA; JavaScript must execute to populate fund data |

**Scraping behaviour:**
- Loads each of the 5 fund URLs
- Waits for `networkidle` state (all JS requests complete)
- Passes rendered HTML to BeautifulSoup for field extraction
- Polite crawl: 3-second delay between each page
- Realistic `User-Agent` header to reduce bot-detection risk

**Retry logic:** Single attempt per page; if the scraper fails, the previous `data/raw/*.json` files remain unchanged.

---

### 3.3 sentence-transformers (Embedding Model — Local)

| Property | Value |
|---|---|
| Model | `all-MiniLM-L6-v2` |
| Library | `sentence-transformers` |
| Execution | Local CPU (no API call, no key) |
| Output | 384-dimensional float vector |
| Used for | Embedding both chunks (at ingest) and queries (at query time) |

---

### 3.4 ChromaDB (Vector Store — Local)

| Property | Value |
|---|---|
| Type | Embedded vector database (runs in-process, no server) |
| Persistence | `chroma_db/` directory at project root |
| Collection | `mf_faq` |
| Distance metric | Cosine (configured via `hnsw:space: cosine`) |
| SDK | `chromadb` Python package |

---

## 5. Internal Module APIs

### 4.1 `phase4/chatbot/safety_gate.py`

**Constants:**
```python
PASS          = "PASS"
REFUSE_PII    = "REFUSE_PII"
REFUSE_ADVICE = "REFUSE_ADVICE"
REFUSE_PERF   = "REFUSE_PERF"
```

**Functions:**

```python
def check(query: str) -> str:
    """
    Run 3-stage safety gate on raw query string.

    Stage 1: Regex blocklist — PAN, Aadhaar, phone, email, account, OTP
    Stage 2: Advice keyword check — 'should i', 'recommend', 'portfolio'…
    Stage 3: Performance keyword check — 'cagr', 'past performance'…

    Returns: PASS | REFUSE_PII | REFUSE_ADVICE | REFUSE_PERF
    Cost: O(n) string scan — no LLM call, no DB call.
    """

def get_refusal_message(gate_result: str) -> str:
    """
    Return the human-readable refusal message for a given gate result.
    Returns empty string for unknown results.
    """
```

**PII patterns detected:**
| Label | Regex |
|---|---|
| PAN | `[A-Z]{5}[0-9]{4}[A-Z]` |
| Aadhaar | `\d{4}[\s\-]\d{4}[\s\-]\d{4}` |
| Phone | `[6-9]\d{9}` (Indian mobile) |
| Email | `\S+@\S+\.\S+` |
| Account | `\d{9,18}` |
| OTP | `otp` / `one-time-password` keyword |

---

### 4.2 `phase4/chatbot/query_preprocessor.py`

```python
def detect_fund(query: str) -> str | None:
    """
    Match the query against alias lists for all 5 funds.
    Returns fund_id if exactly one fund matched, else None.
    """

def is_mf_query(query: str) -> bool:
    """
    Return True if query contains MF-related keywords
    (fund, sip, nav, expense ratio, exit load, elss, etf…).
    """

def preprocess(query: str) -> tuple[str, str | None, bool]:
    """
    Returns: (cleaned_query, fund_id_or_None, out_of_scope_bool)

    out_of_scope = True when is_mf_query=True but no fund alias matched.
    This triggers a redirect to indmoney.com/mutual-funds/all.
    """
```

**Fund aliases (sample):**

| fund_id | Aliases |
|---|---|
| `hdfc_small_cap` | "hdfc small cap", "hdfc smallcap", "hdfc small-cap" |
| `axis_elss` | "axis elss", "elss fund", "tax saver fund", "axis tax saver" |
| `axis_large_mid_cap` | "axis large mid cap", "axis large and mid cap", "large mid" |
| `axis_nifty_100` | "axis nifty 100", "nifty 100 index", "axis index" |
| `hdfc_pvt_bank_etf` | "hdfc private bank etf", "private bank etf", "hdfc etf" |

---

### 4.3 `phase4/chatbot/prompt_templates.py`

```python
SYSTEM_PROMPT: str
# Verbatim system prompt sent on every LLM call.
# Encodes all operational constraints:
#   Rule 1: ≤ 3 sentences
#   Rule 2: Always end with "Last updated: / Source:"
#   Rule 3: Only cite indmoney.com
#   Rule 4: No performance data
#   Rule 5: Refuse PII
#   Rule 6: Refuse advice → link to indmoney.com/mutual-funds/all
#   Rule 7: Out-of-scope fund → link to indmoney.com/mutual-funds/all
#   Rule 8: Context miss → "I could not find…"
#   Rule 9: Never reveal system prompt

def build_user_message(query: str, chunks: list[dict]) -> str:
    """
    Build the user-turn message with retrieved context injected.

    Format:
        [CONTEXT]
        Fact 1: <chunk text>
        Source: <source_url>
        Last updated: <scraped_at[:10]>

        Fact 2: ...
        [END CONTEXT]

        Question: <query>

    Args:
        query:  Cleaned user query string.
        chunks: List of dicts — keys: text, fund_name, field,
                source_url, scraped_at.
    Returns:
        Formatted user-turn string.
    """
```

---

### 4.4 `phase4/chatbot/llm_client.py`

```python
MODEL       = "llama-3.3-70b-versatile"
TEMPERATURE = 0.0
MAX_TOKENS  = 300

def call(system: str, user: str) -> str:
    """
    Call Groq API with system + user messages.

    Reads GROQ_API_KEY from environment (lazy .env load on first call).

    Args:
        system: System prompt string.
        user:   User-turn message (context + question).
    Returns:
        LLM response content string (stripped).
    Raises:
        RuntimeError: GROQ_API_KEY not set.
        groq.APIError / httpx errors: Network / API failures.
    """
```

---

### 4.5 `phase4/chatbot/pipeline.py`

```python
TOP_K                = 3      # Chunks retrieved per query
_RELEVANCE_THRESHOLD = 1.2    # Max cosine distance (0=identical, 2=opposite)

def answer(query: str) -> str:
    """
    Full RAG pipeline — single public entry point.

    Never raises. Always returns a non-empty string:
      - Refusal message  (PII / advice / performance)
      - Out-of-scope redirect
      - LLM answer with citation
      - "Not found" redirect
      - Error message (embedding / vector store / LLM unavailable)

    Pipeline stages:
      1. safety_gate.check()       — fast, no external calls
      2. query_preprocessor.preprocess()
      3. embedder.embed_query()    — local model
      4. vector_store.query_chunks() — ChromaDB cosine search
      5. prompt_templates.build_user_message()
      6. llm_client.call()         — Groq API
      7. Citation enforcement      — regex ensures "Last updated:" present
    """
```

---

### 4.6 `phase3/ingestion/chunker.py`

```python
def build_chunks(raw_dir: Path = PHASE2_RAW_DIR) -> list[dict]:
    """
    Load all phase2/data/raw/*.json and convert to text chunks.

    One chunk per (fund × field) pair. Fields with null values use
    NULL_TEMPLATES to produce "no lock-in" / "no SIP" chunks.

    Returns:
        List of dicts — keys: text, fund_id, fund_name, field,
                        source_url, scraped_at.
    """

def load_raw_funds(raw_dir: Path) -> list[dict]:
    """Load raw JSON files, sorted by filename."""
```

**Chunk templates:**
```python
FIELD_TEMPLATES = {
    "expense_ratio":  "The expense ratio of {fund_name} is {value}.",
    "exit_load":      "The exit load of {fund_name} is {value}.",
    "min_sip_amount": "The minimum SIP amount for {fund_name} is {value}.",
    "lock_in_period": "The lock-in period for {fund_name} is {value}.",
    "riskometer":     "The riskometer (risk level) of {fund_name} is {value}.",
    "benchmark":      "The benchmark index for {fund_name} is {value}.",
}
NULL_TEMPLATES = {
    "lock_in_period": "{fund_name} has no lock-in period.",
    "min_sip_amount": "{fund_name} does not offer SIP (ETF; traded on exchange).",
}
```

---

### 4.7 `phase3/ingestion/vector_store.py`

```python
COLLECTION_NAME = "mf_faq"

def get_collection(persist_dir: Path = CHROMA_DIR) -> chromadb.Collection:
    """Get or create the mf_faq ChromaDB collection with cosine metric."""

def upsert_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    persist_dir: Path = CHROMA_DIR,
) -> None:
    """
    Upsert chunks into ChromaDB. Idempotent — document IDs are
    "{fund_id}__{field}" so re-running replaces stale chunks.

    Args:
        chunks:     List of chunk dicts.
        embeddings: Pre-computed embedding vectors (same order).
    """

def query_chunks(
    query_embedding: list[float],
    n_results: int = 5,
    fund_id: str | None = None,
    field: str | None = None,
    persist_dir: Path = CHROMA_DIR,
) -> dict:
    """
    Top-n cosine similarity search.

    Returns ChromaDB result dict:
        { ids, documents, metadatas, distances }
    Each inner list indexed by query (we send one query → index [0]).

    Metadata filter behaviour:
        fund_id only  → WHERE fund_id = ?
        field only    → WHERE field = ?
        both          → WHERE fund_id = ? AND field = ?
        neither       → no filter (broad retrieval)
    """
```

---

## 6. End-to-End Data Flow

### 5.1 Scrape → Store (offline / scheduled)

```
INDmoney fund page (URL from sources.json)
        │
        │  Playwright launches Chromium
        │  Page.goto(url) → waits for networkidle
        │
        ▼
    Rendered HTML
        │
        │  BeautifulSoup selectors target fund-detail card
        │
        ▼
  Raw fund dict (per fund):
    {
      fund_id, fund_name, amc, category,
      expense_ratio, exit_load, min_sip_amount,
      lock_in_period, riskometer, benchmark,
      source_url, scraped_at (ISO-8601)
    }
        │
        │  json.dump() → phase2/data/raw/<fund_id>.json
        │
        ▼
  Chunker (build_chunks)
    One NL sentence per (fund × field) pair
    Null fields → null templates ("no lock-in", "no SIP")
        │
        ▼
  Embedder (embed_chunks)
    all-MiniLM-L6-v2 → 384-dim float list per chunk
        │
        ▼
  ChromaDB upsert
    ID:       "{fund_id}__{field}"
    document: chunk text
    embedding: 384-dim vector
    metadata: fund_id, fund_name, field, source_url, scraped_at
```

### 5.2 Query → Answer (real-time)

```
User types query
        │
        ▼
  safety_gate.check(query)
    ├─ PII regex match?  → REFUSE_PII   → return refusal message
    ├─ Advice keyword?   → REFUSE_ADVICE → return refusal message
    ├─ Perf keyword?     → REFUSE_PERF  → return refusal message
    └─ Clean             → PASS → continue
        │
        ▼
  query_preprocessor.preprocess(query)
    ├─ detect_fund()    → fund_id or None
    ├─ is_mf_query()    → True/False
    └─ out_of_scope?    → redirect to indmoney.com/mutual-funds/all
        │
        ▼
  embedder.embed_query(cleaned)
    → 384-dim vector
        │
        ▼
  vector_store.query_chunks(embedding, n=3, fund_id=fund_id)
    → top-3 chunks by cosine similarity
    → filter chunks with distance > 1.2 (not relevant)
    → 0 relevant chunks? → "not found" redirect
        │
        ▼
  prompt_templates.build_user_message(query, chunks)
    → "[CONTEXT]\nFact 1: ...\nSource: ...\n[END CONTEXT]\nQuestion: ..."
        │
        ▼
  llm_client.call(SYSTEM_PROMPT, user_message)
    POST https://api.groq.com/openai/v1/chat/completions
    model=llama-3.3-70b-versatile, temperature=0.0, max_tokens=300
        │
        ▼
  Citation enforcement (pipeline.py)
    If "Last updated:" absent → append from top chunk metadata
    Regex normalise: "Last updated: DATE  \nSource: URL"
        │
        ▼
  Final answer string → Streamlit UI → User
```

---

## 7. Data Storage Schemas

### 6.1 `phase2/data/sources.json` — Fund Registry

```json
{
  "funds": [
    {
      "fund_id":   "hdfc_small_cap",
      "fund_name": "HDFC Small Cap Fund - Direct Growth",
      "amc":       "HDFC",
      "category":  "Small Cap",
      "url":       "https://www.indmoney.com/mutual-funds/<slug>"
    }
  ]
}
```

Used by the scraper to know which URLs to visit.

---

### 6.2 `phase2/data/raw/<fund_id>.json` — Scraped Fund Data

```json
{
  "fund_id":        "hdfc_small_cap",
  "fund_name":      "HDFC Small Cap Fund - Direct Growth",
  "amc":            "HDFC",
  "category":       "Small Cap",
  "expense_ratio":  "0.55%",
  "exit_load":      "1% if redeemed within 1 year of allotment",
  "min_sip_amount": "₹500",
  "lock_in_period": null,
  "riskometer":     "Very High",
  "benchmark":      "Nifty Smallcap 250 TRI",
  "source_url":     "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
  "scraped_at":     "2026-03-01T10:00:00+05:30"
}
```

**Field rules:**
- `lock_in_period`: `null` for non-ELSS funds; `"3 years"` for ELSS
- `min_sip_amount`: `"--"` for ETFs (no SIP facility); replaced with `null` in chunker
- All string fields are stored exactly as shown on the INDmoney page
- `scraped_at`: ISO-8601 with timezone offset

---

### 6.3 ChromaDB `mf_faq` Collection — Chunk Schema

| Field | Type | Example |
|---|---|---|
| **id** (document ID) | `string` | `"hdfc_small_cap__expense_ratio"` |
| **document** (chunk text) | `string` | `"The expense ratio of HDFC Small Cap Fund is 0.55%."` |
| **embedding** | `list[float]` (384-dim) | `[0.023, -0.141, ...]` |
| **metadata.fund_id** | `string` | `"hdfc_small_cap"` |
| **metadata.fund_name** | `string` | `"HDFC Small Cap Fund - Direct Growth"` |
| **metadata.field** | `string` | `"expense_ratio"` |
| **metadata.source_url** | `string` | `"https://www.indmoney.com/mutual-funds/..."` |
| **metadata.scraped_at** | `string` (ISO-8601) | `"2026-03-01T10:00:00+05:30"` |

**Document ID pattern:** `"{fund_id}__{field}"`
- Makes upserts idempotent — re-running `ingest.py` after a new scrape replaces stale chunks, never duplicates them
- Total documents: 30–35 (some null fields skip if no null template)

**Distance metric:** Cosine (configured at collection creation via `hnsw:space: cosine`)
- 0.0 = identical vectors
- 1.0 = orthogonal (unrelated)
- 2.0 = opposite
- Relevance threshold in pipeline: `≤ 1.2`

---

### 6.4 `phase6/eval/test_queries.json` — Evaluation Suite Schema

```json
{
  "version": "1.0",
  "factual_queries": [
    {
      "id":      "q001",
      "fund_id": "hdfc_small_cap",
      "field":   "expense_ratio",
      "query":   "What is the expense ratio of HDFC Small Cap Fund?",
      "checks":  {
        "has_citation":     true,
        "has_indmoney_url": true,
        "contains_any":     ["%"]
      }
    }
  ],
  "refusal_queries": [
    {
      "id":                "r001",
      "type":              "advice",
      "query":             "Should I invest in HDFC Small Cap Fund?",
      "expected_contains": ["facts only", "investment advice"],
      "expected_url":      "https://www.indmoney.com/mutual-funds/all"
    }
  ]
}
```

---

## 8. Safety & Compliance Layer

### Three-Stage Gate (runs on every query, zero external calls)

```
Query string
    │
    ├─ Stage 1: PII regex (O(n), instant)
    │     6 patterns: PAN, Aadhaar, phone, email, account number, OTP keyword
    │     MATCH → REFUSE_PII → drop query, return refusal (nothing logged)
    │
    ├─ Stage 2: Advice keywords
    │     "should i", "recommend", "better fund", "which fund", "invest in",
    │     "worth investing", "portfolio", "outperform", "best fund", …
    │     MATCH → REFUSE_ADVICE
    │
    └─ Stage 3: Performance keywords
          "past performance", "cagr", "annualised return", "annualized return",
          "how much will i get", "historical return", "better return", …
          MATCH → REFUSE_PERF
```

### LLM System Prompt (second layer for advice/PII)

The system prompt explicitly instructs the LLM to refuse if advice or PII appears — providing a second safety net in case a malformed query slips through the keyword gate.

### Pipeline Guarantees

| Guarantee | Mechanism |
|---|---|
| PII never stored | Gate fires before ChromaDB or LLM is called |
| All answers cite source | Pipeline appends citation if LLM omits it |
| Only indmoney.com URLs | System prompt + citation injection both enforce this |
| Out-of-scope funds redirect | `OUT_OF_SCOPE_MESSAGE` returned from pipeline before retrieval |
| No hallucinated facts | `[CONTEXT]...[END CONTEXT]` + "only use context" instruction |

---

## 9. Deployment Guide

### Local Development

```bash
# 1. Clone and set up
git clone <repo> && cd RAGBased-MFChatbot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium --with-deps

# 2. Configure
cp .env.example .env
echo "GROQ_API_KEY=your_key_here" >> .env

# 3. Scrape + ingest (one-time or on demand)
python phase2/scraping/scraper.py
python phase3/ingestion/ingest.py

# 4. Run UI
streamlit run phase5/ui/app.py
```

---

### Streamlit Cloud Deployment

1. Push code to GitHub (ensure `phase2/data/raw/*.json` files are committed — they are *not* gitignored in deployment; only `chroma_db/` is gitignored)
2. Connect repo to [Streamlit Cloud](https://streamlit.io/cloud)
3. Set **Main file path**: `phase5/ui/app.py`
4. Add **Secret**: `GROQ_API_KEY = <your key>`
5. The app calls `ingest.py` on first run if `chroma_db/` is empty

**Important:** Streamlit Cloud does not persist files between restarts. The app rebuilds ChromaDB from `phase2/data/raw/*.json` on each cold start. Those JSON files must be committed to the repo.

---

### GitHub Actions — Daily Scrape Scheduler

**File:** `.github/workflows/daily_scrape.yml`

| Property | Value |
|---|---|
| Trigger | Cron `30 18 * * *` (18:30 UTC = midnight IST) |
| Also | `workflow_dispatch` (manual run from GitHub UI) |
| Runner | `ubuntu-latest` |
| Permission | `contents: write` (to push updated JSON back) |

**Workflow steps:**
1. `actions/checkout@v4` with `GITHUB_TOKEN`
2. `actions/setup-python@v5` → Python 3.11
3. `pip install -r requirements.txt`
4. `playwright install chromium --with-deps`
5. `python phase2/scraping/scraper.py` → writes `phase2/data/raw/*.json`
6. `git diff --quiet phase2/data/raw/` → sets `changed=true` output if data changed
7. **Conditional** `git add / commit / push` — only runs when `changed == 'true'`

**Failure behaviour:**
- If scraper fails → workflow fails visibly in GitHub Actions log
- Previous JSON files remain unchanged
- Streamlit app continues serving last-good data with correct `scraped_at` timestamps
- No silent failures

---

## 10. Future Improvements

### Data & Coverage

| Improvement | Effort | Impact |
|---|---|---|
| Add more funds (configurable via `sources.json`) | Low | High — only scraper + preprocessor aliases need updating |
| Add more fact fields (NAV, AUM, fund manager) | Medium | Medium — new scraper selectors + chunk templates |
| Multi-language support (Hindi queries) | Medium | High for Indian user base |
| Cache scraped data with TTL (skip scrape if fresh) | Low | Reduces INDmoney server load |

### Retrieval

| Improvement | Effort | Impact |
|---|---|---|
| Re-ranker (cross-encoder) on top-3 chunks | Medium | Improves precision when multiple funds return similar chunks |
| Hybrid search (BM25 + dense) | High | Better keyword-exact matches (e.g., "0.55%") |
| Query expansion (add synonyms before embedding) | Low | Catches more user phrasings |

### Safety

| Improvement | Effort | Impact |
|---|---|---|
| LLM intent classifier as Stage 3 (after keyword check) | Medium | Catches edge cases that keyword matching misses |
| Rate limiting per IP | Low | Prevents API cost abuse |
| Audit log (non-PII) — query type + outcome | Low | Useful for monitoring refusal rates |

### UI & UX

| Improvement | Effort | Impact |
|---|---|---|
| Example query buttons (clickable chips) | Low | Reduces zero-state friction |
| Fund selector dropdown | Low | Faster fund-specific queries |
| Dark mode | Low | Streamlit supports it natively |
| Export chat as PDF | Medium | Useful for reference |

### Infrastructure

| Improvement | Effort | Impact |
|---|---|---|
| Notify on scrape failure (GitHub Actions → email/Slack) | Low | Operational visibility |
| Dockerfile for portable deployment | Low | Removes "works on my machine" issues |
| Versioned snapshots of `data/raw/` (date-stamped) | Low | Historical comparison; rollback capability |
| Switch to OpenAI `text-embedding-3-small` for embeddings | Low | Slightly better semantic accuracy; requires API key |

---

*Technical Reference version: 1.0 · Date: 2026-03-03*
*Covers: Phases 1–7 of the RAG-Based MF Chatbot project*
