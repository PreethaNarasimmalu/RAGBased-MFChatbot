"""
Phase 3 — Chunker

Converts raw fund JSON files (from Phase 2) into natural-language text chunks.
One chunk per (fund, fact_field) pair → 30 chunks total (5 funds × 6 fields).

Each chunk is a dict with:
    text        — natural-language sentence ready for embedding
    fund_id     — machine-readable fund identifier (e.g. "hdfc_small_cap")
    fund_name   — human-readable fund name
    field       — which fact field (expense_ratio, exit_load, etc.)
    source_url  — indmoney.com page the data was scraped from
    scraped_at  — ISO-8601 timestamp from Phase 2

Design: fact-by-fact chunking (not sliding window) because:
  - Corpus is tiny (30 facts total)
  - Each fact is self-contained; no context bleed between facts
  - Precise retrieval: one chunk answers exactly one type of question
"""

import json
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

PHASE2_RAW_DIR = Path(__file__).parent.parent.parent / "phase2" / "data" / "raw"

# ── Natural language templates ─────────────────────────────────────────────────

# Used when the field has a non-null value
FIELD_TEMPLATES: dict[str, str] = {
    "expense_ratio":  "The expense ratio of {fund_name} is {value}.",
    "exit_load":      "The exit load of {fund_name} is {value}.",
    "min_sip_amount": "The minimum SIP amount for {fund_name} is {value}.",
    "lock_in_period": "The lock-in period for {fund_name} is {value}.",
    "riskometer":     "The riskometer (risk level) of {fund_name} is {value}.",
    "benchmark":      "The benchmark index for {fund_name} is {value}.",
}

# Used when the field is null (or the placeholder "--")
NULL_TEMPLATES: dict[str, str] = {
    "lock_in_period": "{fund_name} has no lock-in period.",
    "min_sip_amount": (
        "{fund_name} does not offer SIP "
        "(it is an ETF traded on the exchange; minimum SIP is not applicable)."
    ),
}

FIELDS = list(FIELD_TEMPLATES.keys())


# ── Core logic ─────────────────────────────────────────────────────────────────

def _fund_to_chunks(fund_data: dict) -> list[dict]:
    """
    Convert one fund's raw JSON dict into a list of text chunks.

    Null lock_in_period → templated "no lock-in" chunk (not skipped).
    "--" min_sip_amount (ETF) → templated "no SIP" chunk (not skipped).
    Any other null field with no null template → skipped.
    """
    chunks = []
    fund_name = fund_data["fund_name"]

    for field in FIELDS:
        value = fund_data.get(field)

        # Treat "--" (INDmoney placeholder for ETF with no SIP) as null
        if value == "--":
            value = None

        if value is not None:
            text = FIELD_TEMPLATES[field].format(fund_name=fund_name, value=value)
        elif field in NULL_TEMPLATES:
            text = NULL_TEMPLATES[field].format(fund_name=fund_name)
        else:
            # Null field with no null template — skip
            continue

        chunks.append({
            "text":       text,
            "fund_id":    fund_data["fund_id"],
            "fund_name":  fund_name,
            "field":      field,
            "source_url": fund_data["source_url"],
            "scraped_at": fund_data["scraped_at"],
        })

    return chunks


def load_raw_funds(raw_dir: Path = PHASE2_RAW_DIR) -> list[dict]:
    """Load all fund JSON files from the raw data directory."""
    fund_files = sorted(raw_dir.glob("*.json"))
    # Filter out .gitkeep and non-fund files
    fund_files = [f for f in fund_files if f.suffix == ".json" and f.stem != ".gitkeep"]
    if not fund_files:
        raise FileNotFoundError(
            f"No fund JSON files found in {raw_dir}. "
            "Run `python phase2/scraping/scraper.py` first."
        )
    funds = []
    for path in fund_files:
        with open(path, encoding="utf-8") as f:
            funds.append(json.load(f))
    return funds


def build_chunks(raw_dir: Path = PHASE2_RAW_DIR) -> list[dict]:
    """
    Load all raw fund JSON files and convert to text chunks.

    Returns:
        List of chunk dicts, each with keys:
        text, fund_id, fund_name, field, source_url, scraped_at.
    """
    funds = load_raw_funds(raw_dir)
    chunks = []
    for fund in funds:
        chunks.extend(_fund_to_chunks(fund))
    return chunks


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = build_chunks()
    print(f"Generated {len(chunks)} chunks from {PHASE2_RAW_DIR}")
    for c in chunks[:6]:
        print(f"  [{c['fund_id']:20s} / {c['field']:15s}]  {c['text']}")
