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

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Runtime |
| **UI** | [Streamlit](https://streamlit.io) | Chat interface (browser) |
| **Web scraping** | [Playwright](https://playwright.dev/python/) + Chromium | Headless JS execution on React SPA |
| **HTML parsing** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | Extract fund fields from rendered HTML |
| **Embedding model** | [sentence-transformers](https://www.sbert.net) `all-MiniLM-L6-v2` | Local 384-dim embeddings (no API call) |
| **Vector database** | [ChromaDB](https://www.trychroma.com) | Persistent cosine-similarity vector store |
| **LLM** | [Groq API](https://console.groq.com) — `llama-3.3-70b-versatile` | Answer generation (free tier, LPU-fast) |
| **Config** | [python-dotenv](https://pypi.org/project/python-dotenv/) | Load `GROQ_API_KEY` from `.env` |
| **Testing** | [pytest](https://pytest.org) | Unit + integration tests across all phases |
| **Scheduler** | GitHub Actions cron | Daily scrape + auto-commit at midnight IST |
| **Data format** | JSON | Raw fund data (`phase2/data/raw/`) |

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

This tool provides **factual information only**, scraped from publicly available INDmoney fund pages. It does **not** provide investment advice, recommendations, or return projections. Mutual fund investments are subject to market risks. Please read all scheme-related documents carefully before investing. For personalised advice, consult a SEBI-registered investment adviser.
