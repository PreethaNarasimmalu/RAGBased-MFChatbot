# RAG-Based Mutual Fund Chatbot — Resources

## Setup Steps

### Prerequisites
- Python 3.10+
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### 1 — Clone and install
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
# Open .env and set: GROQ_API_KEY=<your-key>
```

### 3 — Scrape fund data
```bash
python phase2/scraping/scraper.py
```

### 4 — Build vector database
```bash
python phase3/ingestion/ingest.py
```

### 5 — Run the chatbot
```bash
streamlit run phase5/ui/app.py
```

---

## Scope

### Mutual Funds Covered
| AMC | Schemes |
|-----|---------|
| HDFC | HDFC Small Cap Fund — Direct Growth |
| HDFC | HDFC Nifty Private Bank ETF |
| Axis | Axis ELSS Tax Saver Fund — Direct Plan Growth |
| Axis | Axis Large & Mid Cap Fund — Direct Growth |
| Axis | Axis Nifty 100 Index Fund — Direct Growth |

### Data Fields per Fund (6 fields × 5 funds = 30 chunks)
| Field | Description |
|-------|-------------|
| `expense_ratio` | Annual fee charged by the fund |
| `exit_load` | Fee charged on early redemption |
| `min_sip_amount` | Minimum monthly SIP investment |
| `lock_in_period` | Mandatory holding period (if any) |
| `riskometer` | SEBI-defined risk level |
| `benchmark` | Index the fund is benchmarked against |

### Data Source
All data is scraped from publicly available INDmoney fund pages.  
Full URL list: [`sources.csv`](./sources.csv)

---

## Known Limits

- **5 funds only** — Questions about any other fund will be redirected to [indmoney.com/mutual-funds/all](https://www.indmoney.com/mutual-funds/all).
- **No performance data** — Returns, CAGR, and historical comparisons are not supported.
- **No investment advice** — The chatbot answers facts only; it does not recommend buying or selling.
- **No NAV history** — Only current static fields (expense ratio, exit load, etc.) are scraped.
- **ETF note** — HDFC Nifty Private Bank ETF does not support SIP; the chatbot handles this gracefully.
- **Data freshness** — Data reflects the scrape date shown in each answer's "Last updated" line. Re-run the scraper to refresh.
- **PII blocked** — The chatbot will not accept or process PAN, Aadhaar, account numbers, OTPs, or phone numbers.
