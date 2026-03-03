"""
Phase 7 Gate Tests — GitHub Actions Scheduler

Test groups:
  1.  File existence          (5 tests)  — always pass
  2.  YAML validity           (1 test)   — always pass
  3.  Workflow triggers       (3 tests)  — always pass
  4.  Workflow job config     (3 tests)  — always pass
  5.  Workflow steps          (8 tests)  — always pass
  6.  Scraper source files    (4 tests)  — always pass
  7.  Data paths              (3 tests)  — always pass

Total: 27 always-passing tests, 0 skipped.

Run:
    pytest phase7/tests/test_phase7.py -v
"""

import sys
import pytest
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent.parent
PHASE7_DIR    = ROOT / "phase7"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "daily_scrape.yml"
PHASE2_DIR    = ROOT / "phase2"
SCRAPER_FILE  = PHASE2_DIR / "scraping" / "scraper.py"
PARSER_FILE   = PHASE2_DIR / "scraping" / "parser.py"
SOURCES_JSON  = PHASE2_DIR / "data" / "sources.json"
RAW_DATA_DIR  = PHASE2_DIR / "data" / "raw"

EXPECTED_CRON     = "30 18 * * *"     # 18:30 UTC = midnight IST
EXPECTED_PYTHON   = "3.11"
EXPECTED_CHECKOUT = "actions/checkout"
EXPECTED_SETUP_PY = "actions/setup-python"


# ── YAML loader (PyYAML is a transitive dep of chromadb / langchain) ──────────

def _load_workflow() -> dict:
    import yaml
    with open(WORKFLOW_FILE) as f:
        return yaml.safe_load(f)


def _get_triggers(workflow: dict) -> dict:
    """
    Return the 'on:' triggers block.

    PyYAML parses the bare YAML keyword 'on' as the Python boolean True,
    so the triggers block is stored under key True, not the string "on".
    We check both to be safe.
    """
    return workflow.get("on") or workflow.get(True, {}) or {}


def _get_steps(workflow: dict) -> list[dict]:
    """Return the flat list of steps for the first job."""
    jobs = workflow.get("jobs", {})
    first_job = next(iter(jobs.values()))
    return first_job.get("steps", [])


def _step_run_text(workflow: dict) -> str:
    """Concatenate all 'run' fields across all steps for content checks."""
    return "\n".join(
        s.get("run", "") for s in _get_steps(workflow) if "run" in s
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. File existence
# ══════════════════════════════════════════════════════════════════════════════

def test_phase7_directory_exists():
    assert PHASE7_DIR.is_dir(), "phase7/ directory missing"

def test_phase7_tests_directory_exists():
    assert (PHASE7_DIR / "tests").is_dir(), "phase7/tests/ directory missing"

def test_github_workflows_directory_exists():
    assert (ROOT / ".github" / "workflows").is_dir(), ".github/workflows/ missing"

def test_daily_scrape_yml_exists():
    assert WORKFLOW_FILE.is_file(), (
        f"Workflow file missing: {WORKFLOW_FILE}"
    )

def test_phase7_test_file_exists():
    assert (PHASE7_DIR / "tests" / "test_phase7.py").is_file()


# ══════════════════════════════════════════════════════════════════════════════
# 2. YAML validity
# ══════════════════════════════════════════════════════════════════════════════

def test_workflow_yaml_parses_without_error():
    """The workflow file must be valid YAML with no syntax errors."""
    data = _load_workflow()
    assert isinstance(data, dict), "Workflow YAML did not parse to a dict"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Workflow triggers
# ══════════════════════════════════════════════════════════════════════════════

def test_workflow_has_cron_schedule_trigger():
    """Workflow must have a 'schedule' trigger (runs automatically)."""
    data = _load_workflow()
    triggers = _get_triggers(data)
    assert "schedule" in triggers, (
        f"Workflow 'on' block missing 'schedule' trigger. Keys: {list(triggers)}"
    )

def test_workflow_cron_is_midnight_ist():
    """Cron expression must be '30 18 * * *' (18:30 UTC = midnight IST)."""
    data = _load_workflow()
    triggers = _get_triggers(data)
    schedules = triggers["schedule"]
    cron_values = [s["cron"] for s in schedules]
    assert EXPECTED_CRON in cron_values, (
        f"Expected cron '{EXPECTED_CRON}' not found in {cron_values}"
    )

def test_workflow_has_manual_dispatch_trigger():
    """Workflow must support manual trigger via workflow_dispatch."""
    data = _load_workflow()
    triggers = _get_triggers(data)
    assert "workflow_dispatch" in triggers, (
        f"Workflow 'on' block missing 'workflow_dispatch' trigger. Keys: {list(triggers)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Workflow job configuration
# ══════════════════════════════════════════════════════════════════════════════

def test_workflow_runs_on_ubuntu():
    """Job runner must be ubuntu-latest."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    assert jobs, "No jobs defined in workflow"
    first_job = next(iter(jobs.values()))
    assert first_job.get("runs-on") == "ubuntu-latest", (
        f"Expected 'ubuntu-latest', got {first_job.get('runs-on')!r}"
    )

def test_workflow_has_contents_write_permission():
    """Job needs 'contents: write' permission to push data back to repo."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    first_job = next(iter(jobs.values()))
    permissions = first_job.get("permissions", {})
    assert permissions.get("contents") == "write", (
        f"Expected 'contents: write', got {permissions!r}"
    )

def test_workflow_has_at_least_one_job():
    data = _load_workflow()
    assert len(data.get("jobs", {})) >= 1, "Workflow has no jobs"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Workflow steps
# ══════════════════════════════════════════════════════════════════════════════

def test_workflow_has_checkout_step():
    """Workflow must checkout the repo (actions/checkout)."""
    data = _load_workflow()
    steps = _get_steps(data)
    uses_list = [s.get("uses", "") for s in steps]
    assert any(EXPECTED_CHECKOUT in u for u in uses_list), (
        f"No 'actions/checkout' step found. Steps: {uses_list}"
    )

def test_workflow_has_setup_python_step():
    """Workflow must set up Python (actions/setup-python)."""
    data = _load_workflow()
    steps = _get_steps(data)
    uses_list = [s.get("uses", "") for s in steps]
    assert any(EXPECTED_SETUP_PY in u for u in uses_list), (
        f"No 'actions/setup-python' step found. Steps: {uses_list}"
    )

def test_workflow_python_version_is_311():
    """Python version must be 3.11 (matches local dev environment)."""
    data = _load_workflow()
    steps = _get_steps(data)
    for step in steps:
        if EXPECTED_SETUP_PY in step.get("uses", ""):
            version = step.get("with", {}).get("python-version", "")
            assert str(version) == EXPECTED_PYTHON, (
                f"Expected python-version '{EXPECTED_PYTHON}', got {version!r}"
            )
            return
    pytest.fail("setup-python step not found")

def test_workflow_installs_requirements():
    """Workflow must install Python dependencies from requirements.txt."""
    data = _load_workflow()
    run_text = _step_run_text(data)
    assert "requirements.txt" in run_text, (
        "No step installs requirements.txt"
    )

def test_workflow_installs_playwright_chromium():
    """Workflow must install Playwright's Chromium browser."""
    data = _load_workflow()
    run_text = _step_run_text(data)
    assert "playwright" in run_text.lower() and "chromium" in run_text.lower(), (
        "No step installs Playwright Chromium"
    )

def test_workflow_runs_scraper_script():
    """Workflow must run phase2/scraping/scraper.py."""
    data = _load_workflow()
    run_text = _step_run_text(data)
    assert "scraper.py" in run_text, (
        "No step runs scraper.py"
    )

def test_workflow_checks_git_diff_on_raw_data():
    """Workflow must diff phase2/data/raw/ to detect scrape changes."""
    data = _load_workflow()
    run_text = _step_run_text(data)
    assert "phase2/data/raw" in run_text, (
        "No step checks git diff on phase2/data/raw/"
    )

def test_workflow_commit_step_is_conditional():
    """Commit step must be guarded by 'if:' so it only runs when data changed."""
    data = _load_workflow()
    steps = _get_steps(data)
    commit_steps = [
        s for s in steps
        if "run" in s and "git commit" in s.get("run", "")
    ]
    assert commit_steps, "No step with 'git commit' found"
    for step in commit_steps:
        assert "if" in step, (
            f"Commit step is not conditional (missing 'if:'): {step.get('name')!r}"
        )

def test_workflow_commit_step_adds_raw_data_path():
    """Commit step must `git add` the phase2/data/raw/ path."""
    data = _load_workflow()
    run_text = _step_run_text(data)
    assert "git add" in run_text and "phase2/data/raw" in run_text, (
        "Commit step does not git-add phase2/data/raw/"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6. Scraper source files
# ══════════════════════════════════════════════════════════════════════════════

def test_scraper_py_exists():
    assert SCRAPER_FILE.is_file(), f"Scraper missing: {SCRAPER_FILE}"

def test_parser_py_exists():
    assert PARSER_FILE.is_file(), f"Parser missing: {PARSER_FILE}"

def test_scraper_uses_playwright():
    """scraper.py must import or reference Playwright (not plain requests)."""
    content = SCRAPER_FILE.read_text()
    assert "playwright" in content.lower(), (
        "scraper.py does not reference Playwright — INDmoney is a React SPA"
    )

def test_parser_extracts_expense_ratio():
    """parser.py must handle the expense_ratio field."""
    content = PARSER_FILE.read_text()
    assert "expense_ratio" in content, (
        "parser.py does not extract expense_ratio"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 7. Data paths
# ══════════════════════════════════════════════════════════════════════════════

def test_sources_json_exists():
    assert SOURCES_JSON.is_file(), f"sources.json missing: {SOURCES_JSON}"

def test_raw_data_directory_exists():
    assert RAW_DATA_DIR.is_dir(), f"Raw data dir missing: {RAW_DATA_DIR}"

def test_sources_json_has_5_funds():
    """sources.json must list exactly 5 fund sources."""
    import json
    data = json.loads(SOURCES_JSON.read_text())
    funds = data if isinstance(data, list) else data.get("funds", data.get("sources", []))
    assert len(funds) == 5, (
        f"Expected 5 funds in sources.json, got {len(funds)}"
    )
