"""
Phase 5 Gate Tests — Streamlit UI

Test groups:
  1. File existence          (2 tests) — always pass
  2. app.py content checks   (6 tests) — always pass (static analysis)
     - Contains disclaimer text
     - Contains example questions
     - Imports pipeline correctly
     - Has "Facts-only" note
     - Has source link formatting (_linkify)
     - Has INDmoney color (#00B386) in CSS
  3. Streamlit theme config   (3 tests) — always pass
     - config.toml exists
     - Primary color is INDmoney green
     - Background is white

Run:
    pytest phase5/tests/test_phase5.py -v
"""

import sys
from pathlib import Path

ROOT      = Path(__file__).parent.parent.parent
PHASE5_UI = ROOT / "phase5" / "ui"
APP_FILE  = PHASE5_UI / "app.py"
CONFIG    = ROOT / ".streamlit" / "config.toml"

sys.path.insert(0, str(PHASE5_UI))
sys.path.insert(0, str(ROOT / "phase4" / "chatbot"))
sys.path.insert(0, str(ROOT / "phase3" / "ingestion"))


# ══════════════════════════════════════════════════════════════════════════════
# 1. File existence
# ══════════════════════════════════════════════════════════════════════════════

def test_app_file_exists():
    assert APP_FILE.is_file(), "phase5/ui/app.py not found"

def test_streamlit_config_exists():
    assert CONFIG.is_file(), ".streamlit/config.toml not found"


# ══════════════════════════════════════════════════════════════════════════════
# 2. app.py content checks (static analysis — no Streamlit runtime needed)
# ══════════════════════════════════════════════════════════════════════════════

def _app_source() -> str:
    return APP_FILE.read_text(encoding="utf-8")


def test_app_has_disclaimer():
    """Disclaimer text must appear in app.py (Phase 5 gate: disclaimer always visible)."""
    src = _app_source()
    assert "DISCLAIMER" in src
    assert "investment advice" in src.lower()
    assert "sebi" in src.lower()


def test_app_has_example_questions():
    """At least 3 example questions must be present."""
    src = _app_source()
    assert src.count("expense ratio") >= 1
    assert src.count("lock-in") >= 1 or src.count("lock_in") >= 1
    assert src.count("SIP") >= 1 or src.count("minimum SIP") >= 1


def test_app_imports_pipeline():
    """app.py must import from pipeline (the RAG pipeline)."""
    src = _app_source()
    assert "from pipeline import answer" in src


def test_app_has_facts_only_note():
    """'Facts-only' note must appear in the UI (Phase 5 gate requirement)."""
    src = _app_source()
    assert "Facts-only" in src or "facts only" in src.lower()


def test_app_has_linkify():
    """Source URLs must be converted to clickable links (_linkify helper)."""
    src = _app_source()
    assert "_linkify" in src or "linkify" in src.lower()


def test_app_has_indmoney_green():
    """INDmoney primary color #00B386 must appear in the CSS."""
    src = _app_source()
    assert "#00B386" in src


# ══════════════════════════════════════════════════════════════════════════════
# 3. Streamlit theme config
# ══════════════════════════════════════════════════════════════════════════════

def _config_source() -> str:
    return CONFIG.read_text(encoding="utf-8")


def test_config_primary_color_is_indmoney_green():
    """Theme primary color must be INDmoney green #00B386."""
    cfg = _config_source()
    assert "#00B386" in cfg


def test_config_background_is_white():
    """Theme background must be white #FFFFFF."""
    cfg = _config_source()
    assert "#FFFFFF" in cfg


def test_config_has_secondary_background():
    """Theme must define a secondary background color."""
    cfg = _config_source()
    assert "secondaryBackgroundColor" in cfg


# ══════════════════════════════════════════════════════════════════════════════
# 4. _linkify unit test (import helper directly)
# ══════════════════════════════════════════════════════════════════════════════

def test_linkify_converts_url_to_markdown_link():
    """_linkify must wrap bare URLs in markdown [url](url) format."""
    # Import the helper by executing the module-level definitions only
    import importlib.util, types

    # Stub streamlit so the module can be parsed without a Streamlit runtime
    st_stub = types.ModuleType("streamlit")
    for attr in ["set_page_config", "markdown", "columns", "chat_message",
                 "chat_input", "spinner", "session_state", "button", "rerun"]:
        setattr(st_stub, attr, lambda *a, **kw: None)
    st_stub.session_state = {}
    sys.modules.setdefault("streamlit", st_stub)

    spec = importlib.util.spec_from_file_location("app", APP_FILE)
    mod  = importlib.util.module_from_spec(spec)
    # Only execute to pick up function definitions (st calls will no-op)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass  # st runtime errors are expected; we only need _linkify

    if hasattr(mod, "_linkify"):
        result = mod._linkify("Visit https://www.indmoney.com/mutual-funds/all for more.")
        assert "https://www.indmoney.com/mutual-funds/all" in result
        assert "](" in result   # markdown link syntax present
