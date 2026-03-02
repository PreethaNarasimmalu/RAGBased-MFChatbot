"""
Phase 4 — LLM Client

Wraps the Groq API (llama-3.3-70b-versatile).

Settings from ARCHITECTURE.md:
  Temperature = 0.0   — deterministic; financial facts must be exact
  Max tokens  = 300   — enough for ≤ 3 sentences + citation line

The API key is read from GROQ_API_KEY in .env (never committed).
"""

import os
from pathlib import Path

MODEL       = "llama-3.3-70b-versatile"
TEMPERATURE = 0.0
MAX_TOKENS  = 300

_ENV_LOADED = False


def _load_env() -> None:
    """Load .env once from project root (lazy — avoids hard import of dotenv)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent.parent / ".env")
    except ImportError:
        pass  # python-dotenv not installed; rely on environment variables
    _ENV_LOADED = True


def call(system: str, user: str) -> str:
    """
    Call the Groq LLM with a system prompt and a user message.

    Args:
        system: System prompt string (SYSTEM_PROMPT from prompt_templates.py).
        user:   User-turn message (built by build_user_message).

    Returns:
        LLM response text (stripped).

    Raises:
        RuntimeError: If GROQ_API_KEY is not set in the environment.
    """
    _load_env()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your Groq API key."
        )

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content.strip()
