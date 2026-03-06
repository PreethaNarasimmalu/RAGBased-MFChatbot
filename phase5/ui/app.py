"""
Phase 5 — Streamlit Chat UI

INDmoney-inspired design:
  Primary green : #00B386
  Background    : #FFFFFF
  Card bg       : #F8F9FA
  Text          : #1A1A1A

Run locally:
    streamlit run phase5/ui/app.py

Same file works on Streamlit Cloud — no changes needed.
"""

import re
import sys
from pathlib import Path

# ── Path setup (works from any cwd) ───────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "phase4" / "chatbot"))
sys.path.insert(0, str(_ROOT / "phase3" / "ingestion"))

import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MF FAQ Assistant",
    page_icon="💹",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS — INDmoney color palette ───────────────────────────────────────────────
st.markdown("""
<style>
/* Base */
.stApp { background-color: #FFFFFF; }

/* Header */
.mf-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1A1A1A;
    margin-bottom: 2px;
}
.mf-subtitle {
    font-size: 0.85rem;
    color: #666666;
    margin-bottom: 20px;
}

/* Example chips — outlined green pill buttons */
div[data-testid="column"] .stButton > button {
    background-color: #F0FAF7;
    border: 1.5px solid #00B386;
    color: #00B386;
    border-radius: 20px;
    font-size: 0.78rem;
    padding: 6px 14px;
    height: auto;
    white-space: normal;
    text-align: left;
    width: 100%;
    line-height: 1.4;
}
div[data-testid="column"] .stButton > button:hover {
    background-color: #00B386;
    color: #FFFFFF;
    border-color: #00B386;
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    margin-bottom: 4px;
}

/* Source links */
a { color: #00B386 !important; text-decoration: underline; }

/* Disclaimer */
.mf-disclaimer {
    background-color: #FFFBF5;
    border-left: 4px solid #FF9500;
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 0.78rem;
    color: #555555;
    margin-top: 24px;
    line-height: 1.6;
}

/* Divider line under header */
.mf-divider {
    border: none;
    border-top: 1px solid #E8E8E8;
    margin: 8px 0 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="mf-title">💹 Mutual Fund FAQ Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mf-subtitle">Facts-only &nbsp;·&nbsp; No investment advice &nbsp;·&nbsp; '
    'Data sourced from <a href="https://www.indmoney.com" target="_blank">INDmoney</a> public pages</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="mf-divider">', unsafe_allow_html=True)

# ── Example questions ──────────────────────────────────────────────────────────
EXAMPLES = [
    "What is the expense ratio of HDFC Small Cap Fund?",
    "What is the lock-in period for Axis ELSS fund?",
    "What is the minimum SIP for Axis Nifty 100 Index Fund?",
]

st.markdown("**Try asking:**")
cols = st.columns(3)
for i, (col, ex) in enumerate(zip(cols, EXAMPLES)):
    if col.button(ex, key=f"ex_{i}"):
        st.session_state["pending_query"] = ex

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ── Render chat history ────────────────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _linkify(text: str) -> str:
    """Convert bare https:// URLs in text to clickable markdown links."""
    return re.sub(
        r'(https?://[^\s\)\"]+)',
        r'[\1](\1)',
        text,
    )


def _process(query: str) -> None:
    """Add user message → call pipeline → add assistant message."""
    # User bubble
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Assistant bubble
    with st.chat_message("assistant"):
        with st.spinner("Looking up…"):
            try:
                from pipeline import answer
                response = answer(query, chat_history=st.session_state["messages"])
            except Exception as exc:
                response = (
                    f"Something went wrong: {exc}. "
                    "Please ensure the database is populated and your API key is set."
                )
        formatted = _linkify(response)
        st.markdown(formatted, unsafe_allow_html=False)

    st.session_state["messages"].append({"role": "assistant", "content": formatted})


# ── Handle example button clicks ───────────────────────────────────────────────
if "pending_query" in st.session_state:
    q = st.session_state.pop("pending_query")
    _process(q)
    st.rerun()

# ── Chat input ─────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about expense ratio, exit load, SIP, lock-in, riskometer…"):
    _process(prompt)

# ── Persistent disclaimer footer ───────────────────────────────────────────────
st.markdown("""
<div class="mf-disclaimer">
⚠️ <strong>DISCLAIMER:</strong> This chat assistant provides factual information from publicly
available INDmoney mutual fund pages. It does <strong>not</strong> provide investment advice,
recommendations, or return projections. Mutual fund investments are subject to market risks.
Please read all scheme-related documents carefully before investing.
</div>
""", unsafe_allow_html=True)
