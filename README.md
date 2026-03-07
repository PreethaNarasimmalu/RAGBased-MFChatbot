# RAG-Based Mutual Fund FAQ Chatbot

A facts-only chatbot that answers questions about 5 specific mutual fund schemes listed on **INDmoney**. Built with Retrieval-Augmented Generation (RAG) — it scrapes fund pages, embeds the facts, and retrieves them at query time before calling an LLM. It never gives investment advice.

---

## Funds in Scope

| # | Fund | AMC | Category |
|---|---|---|---|
| 1 | HDFC Small Cap Fund — Direct Growth | HDFC | Small Cap |
| 2 | Axis ELSS Tax Saver Fund — Direct Plan Growth | Axis | ELSS / Tax Saver |
| 3 | Axis Large & Mid Cap Fund — Direct Growth | Axis | Large & Mid Cap |
| 4 | Axis Nifty 100 Index Fund — Direct Growth | Axis | Index (Large Cap) |
| 5 | HDFC Nifty Private Bank ETF | HDFC | ETF (Sectoral) |

### What it can answer

- Expense ratio, exit load, minimum SIP amount
- Lock-in period (ELSS: 3 years; others: none)
- Riskometer (SEBI risk label)
- Benchmark index
- How to download capital-gains / ELSS tax statements on INDmoney

### What it refuses

- Investment advice ("should I invest…?", "which is better…?")
- Return predictions or past-performance comparisons
- Queries containing PAN, Aadhaar, account number, OTP, phone, or email

---

## Tech Stack

### Frontend
| Technology | Details |
|---|---|
| [Streamlit](https://streamlit.io) | Python-based web framework that renders the entire browser UI — chat bubbles, input box, example question chips, sidebar disclaimer, and chat history — all written in Python with no separate HTML/CSS/JS. Custom INDmoney green (`#00B386`) theme applied via `st.markdown` CSS injection. Session state manages conversation history across reruns. |

### Backend
| Technology | Details |
|---|---|
| Python 3.11+ | Core runtime for all phases — scraping, ingestion, chatbot logic, and UI |
| [Groq API](https://console.groq.com) — `llama-3.3-70b-versatile` | LLM used for answer generation. Called with `temperature=0.0` and `max_tokens=300` for deterministic, concise factual responses. Free tier, runs on Groq's LPU hardware for low-latency inference. |
| [sentence-transformers](https://www.sbert.net) `all-MiniLM-L6-v2` | Local embedding model (384-dimensional vectors). Runs entirely on-device — no external API call, no cost, no latency overhead. Used to embed both the stored chunks (at ingest time) and the user's query (at retrieval time). |
| Safety Gate (custom) | Three-stage input filter: (1) PII regex — blocks PAN, Aadhaar, phone, email, OTP; (2) Advice keyword check — blocks investment recommendation queries; (3) Performance keyword check — blocks return/CAGR/historical queries. Fires before the vector DB or LLM is ever touched. |
| RAG Pipeline (custom) | End-to-end Retrieval-Augmented Generation: embed query → cosine search ChromaDB → filter by relevance threshold (distance ≤ 1.2) → build context → call LLM → append citation (source URL + last updated). |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Loads `GROQ_API_KEY` from `.env` file at runtime. |

### Data Storage
| Technology | Details |
|---|---|
| [ChromaDB](https://www.trychroma.com) | Persistent on-disk vector database. Stores 30 embedded chunks (5 funds × 6 fields each). Uses cosine similarity for retrieval. Chunks are upserted by document ID (`fund_id__field`) so re-ingestion is idempotent — no duplicates. |
| JSON | Raw scraped fund data stored in `phase2/data/raw/<fund_id>.json` (one file per fund). Each file contains 6 fields: `expense_ratio`, `exit_load`, `min_sip_amount`, `lock_in_period`, `riskometer`, `benchmark`. |

### Scraping
| Technology | Details |
|---|---|
| [Playwright](https://playwright.dev/python/) + Chromium | Headless browser automation used to scrape INDmoney's React/Next.js SPA pages. Intercepts `/_next/data/` JSON network responses directly (faster and more structured than HTML parsing). Falls back to extracting `__NEXT_DATA__` from the page HTML if the network intercept misses. Runs with `--no-sandbox` for CI/CD compatibility. |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parser used in the fallback path — extracts fund field values from rendered page HTML when the Next.js JSON intercept is unavailable. |

### Deployment
| Platform | Details |
|---|---|
| [Streamlit Cloud](https://streamlit.io/cloud) | Free hosting platform where the chatbot is deployed and publicly accessible. Reads `GROQ_API_KEY` from Streamlit secrets. Auto-redeploys on every git push to the main branch. No server setup needed. |

### Automation & DevOps
| Technology | Details |
|---|---|
| GitHub Actions (cron) | Scheduled workflow (`.github/workflows/daily_scrape.yml`) runs every day at 04:30 UTC (10 AM IST). Scrapes all 5 fund pages, rebuilds ChromaDB, and commits updated JSON back to the repo only if data changed. Streamlit Cloud detects the push and auto-redeploys. |

### Testing
| Technology | Details |
|---|---|
| [pytest](https://pytest.org) | Unit and integration tests across all phases. 32+ always-passing unit tests cover the safety gate, query preprocessor, prompt templates, and pipeline refusals — no external dependencies needed. Integration tests additionally require ChromaDB populated and `GROQ_API_KEY` set. |

---

## Quick Start

### Prerequisites

- Python 3.11+
- A free [Groq API key](https://console.groq.com) (for LLM inference)

### 1 — Install dependencies

```bash
git clone <repo-url>
cd RAGBased-MFChatbot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium --with-deps
```

### 2 — Configure environment

```bash
cp .env.example .env
# Open .env and set:  GROQ_API_KEY=<your-key>
```

### 3 — Scrape fund data

```bash
python phase2/scraping/scraper.py
# Writes:  phase2/data/raw/<fund_id>.json  (one file per fund)
```

### 4 — Ingest into ChromaDB

```bash
python phase3/ingestion/ingest.py
# Chunks each fund's facts, embeds them, writes to chroma_db/
```

### 5 — Run the chatbot UI

```bash
streamlit run phase5/ui/app.py
# Opens http://localhost:8501
```

---

## Running Tests

```bash
# All always-passing tests (no external deps needed)
pytest phase4/tests/ phase5/tests/ phase6/tests/ phase7/tests/ -v -k "not integration"

# Full suite (requires ChromaDB populated + GROQ_API_KEY set)
pytest -v
```

| Phase | What is tested |
|---|---|
| `phase4/tests/` | Safety gate, preprocessor, prompt templates, pipeline refusals |
| `phase5/tests/` | Streamlit UI file existence and content |
| `phase6/tests/` | Evaluation suite — 35 factual + 11 refusal query schemas, gate coverage |
| `phase7/tests/` | GitHub Actions workflow structure and scraper file existence |

---

## Project Structure

```
RAGBased-MFChatbot/
│
├── .env.example                   ← API key template (never commit .env)
├── requirements.txt
├── pytest.ini
├── ARCHITECTURE.md                ← Full system design document
├── TECHNICAL_REFERENCE.md         ← APIs, data flows, storage, deployment
│
├── phase2/
│   ├── data/
│   │   ├── sources.json           ← 5 fund URLs with fund_id metadata
│   │   └── raw/                   ← scraped JSON per fund (gitignored)
│   └── scraping/
│       ├── scraper.py             ← Playwright headless scraper
│       └── parser.py              ← BeautifulSoup field extractor
│
├── phase3/
│   └── ingestion/
│       ├── chunker.py             ← Fact-by-fact text chunk generator
│       ├── embedder.py            ← Sentence-transformer embedding wrapper
│       ├── vector_store.py        ← ChromaDB read/write wrapper
│       └── ingest.py              ← Orchestrates chunk → embed → store
│
├── phase4/
│   └── chatbot/
│       ├── safety_gate.py         ← PII regex + advice/performance keyword filter
│       ├── query_preprocessor.py  ← Fund name normaliser
│       ├── prompt_templates.py    ← System prompt + context message builder
│       ├── llm_client.py          ← Groq API wrapper (llama-3.3-70b-versatile)
│       └── pipeline.py            ← End-to-end RAG orchestration (answer())
│
├── phase5/
│   └── ui/
│       └── app.py                 ← Streamlit chat interface
│
├── phase6/
│   └── eval/
│       ├── test_queries.json      ← 35 factual + 11 refusal test cases
│       └── expected_answers.md    ← Pass criteria and expected responses
│
├── phase7/
│   └── tests/
│       └── test_phase7.py         ← GitHub Actions workflow validation tests
│
├── .github/
│   └── workflows/
│       └── daily_scrape.yml       ← GitHub Actions cron (daily at midnight IST)
│
└── chroma_db/                     ← ChromaDB storage (gitignored; rebuilt on ingest)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for LLM inference |

Set these in a `.env` file at the project root (see `.env.example`).

---

## Deployment

### Local development
Follow the Quick Start above.

### Streamlit Cloud
1. Fork this repo
2. Add `GROQ_API_KEY` as a Streamlit Cloud secret
3. Set the main file path to `phase5/ui/app.py`
4. The app reads `phase2/data/raw/*.json` on startup and rebuilds ChromaDB

### Automated data refresh (GitHub Actions)
The workflow `.github/workflows/daily_scrape.yml` runs every day at midnight IST:
- Scrapes all 5 INDmoney fund pages
- Commits updated `phase2/data/raw/*.json` back to the repo only if data changed
- Streamlit Cloud re-deploys automatically on push

---

## Disclaimer

⚠️ **DISCLAIMER:** This chat assistant provides factual information from publicly available INDmoney mutual fund pages. It does not provide investment advice, recommendations, or return projections. Mutual fund investments are subject to market risks. Please read all scheme-related documents carefully before investing.
