"""
core/config.py

Centralised path configuration for the C-suite system.

The only path that's truly global is CSUITE_COMPANY_ROOT — that's the
registry directory the dashboard scans to discover which companies exist.
Everything else (where a company's SQLite DB lives, where its session
logs go, where CCA writes code, where the doc-workers save artifacts)
is per-company config.json, with sensible collocated defaults under the
company's folder.

Environment variables (all optional):

    CSUITE_COMPANY_ROOT  — where company folders live (config.json, prompts/,
                           chroma/, knowledge.md, and by default everything
                           else too).
                           Default: ~/.csuite/companies

    CSUITE_DATA_ROOT     — legacy: global override for SQLite DB location.
                           If set, databases land at <DATA_ROOT>/<id>/<id>.db
                           unless a company overrides via `database_path`.
                           If unset, databases collocate under COMPANY_ROOT.

    CSUITE_LOG_ROOT      — legacy: global override for session-log location.
                           Same fallback semantics as CSUITE_DATA_ROOT.

The DATA/LOG env vars stay supported for installs that want the heavy
sequential writes on a different (e.g. HDD) volume, but they're optional —
a fresh single-drive install needs only CSUITE_COMPANY_ROOT (and even that
defaults sanely).
"""

import json
import os
from pathlib import Path

COMPANY_ROOT = Path(os.environ.get(
    "CSUITE_COMPANY_ROOT",
    str(Path.home() / ".csuite" / "companies"),
))


def _env_path(name: str) -> Path | None:
    """Return Path(env[name]) if set, else None. Used for optional roots."""
    v = os.environ.get(name)
    return Path(v) if v else None


# Optional global overrides — None means "no global override; collocate per company"
DATA_ROOT: Path | None = _env_path("CSUITE_DATA_ROOT")
LOG_ROOT:  Path | None = _env_path("CSUITE_LOG_ROOT")


# ── Default tunables (overridable per company in config.json) ────────────────

DEFAULTS = {
    "chat_history_length":    20,     # max messages kept in conversation history
    "chat_message_cap":       10000,  # max chars per message in history context
    "cca_max_turns":          50,     # max turns per session
    "worker_max_tokens":      4096,   # max output tokens for non-interactive workers
    "ceo_chat_max_tokens":    2048,   # max output tokens for CEO conversational replies
    "knowledge_max_pct":      50,     # max % of context_length for knowledge.md
    "max_debate_rounds":      2,      # max deliberation rounds before escalation
}


def get_tunable(company_config: dict, key: str):
    """
    Read a tunable setting from company config, falling back to DEFAULTS.
    Company config values override defaults.
    """
    return company_config.get(key, DEFAULTS.get(key))


# ── Internal: best-effort config loader for helpers ──────────────────────────

def _load_config(company_id: str) -> dict:
    """Read a company's config.json. Returns {} if missing or unparseable —
    callers must not rely on having found the file, only on getting a dict.
    Used by the per-company path helpers below when a caller doesn't already
    have the config in hand."""
    if not company_id:
        return {}
    f = COMPANY_ROOT / company_id / "config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ── Per-company path resolution ──────────────────────────────────────────────
#
# Each helper resolves the same way:
#   1. config[<field>] if set (per-company override from config.json or UI)
#   2. <LEGACY_ROOT>/<id>/... if the corresponding env var is set
#   3. <COMPANY_ROOT>/<id>/... (collocated default — no env vars needed)
#
# `config` is optional everywhere; if omitted, the helper loads it itself.
# Pass it in when you already have it to avoid the extra file read.


def documents_dir(company_id: str, config: dict | None = None) -> Path:
    """Where non-code worker artifacts (research reports, drafts, comms,
    goal docs, etc.) land. Defaults to <COMPANY_ROOT>/<id>/documents/.
    Override per-company via `documents_path` in config.json or the
    Settings UI. Created on first use."""
    if config is None:
        config = _load_config(company_id)
    raw = config.get("documents_path")
    p = Path(raw) if raw else (COMPANY_ROOT / company_id / "documents")
    p.mkdir(parents=True, exist_ok=True)
    return p


def database_path(company_id: str, config: dict | None = None) -> Path:
    """Absolute path to a company's SQLite database file.

    Resolution:
        1. config["database_path"] — full file path, set per-company
        2. <DATA_ROOT>/<id>/<id>.db — if CSUITE_DATA_ROOT env var is set (legacy)
        3. <COMPANY_ROOT>/<id>/<id>.db — collocated default

    Parent directory is auto-created."""
    if config is None:
        config = _load_config(company_id)
    raw = config.get("database_path")
    if raw:
        p = Path(raw)
    elif DATA_ROOT is not None:
        p = DATA_ROOT / company_id / f"{company_id}.db"
    else:
        p = COMPANY_ROOT / company_id / f"{company_id}.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def log_dir(company_id: str, config: dict | None = None) -> Path:
    """Where a company's session logs go.

    Resolution mirrors database_path:
        1. config["log_path"]
        2. <LOG_ROOT>/<id>/sessions/ — if CSUITE_LOG_ROOT env var is set (legacy)
        3. <COMPANY_ROOT>/<id>/logs/ — collocated default

    Directory is auto-created. (Currently scaffold — production code
    doesn't actively write logs here yet.)"""
    if config is None:
        config = _load_config(company_id)
    raw = config.get("log_path")
    if raw:
        p = Path(raw)
    elif LOG_ROOT is not None:
        p = LOG_ROOT / company_id / "sessions"
    else:
        p = COMPANY_ROOT / company_id / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_agent_prompt(company_id: str, role: str, config: dict) -> str:
    """
    Load an agent's personality/behavioral prompt.

    Checks for a markdown file first:
        CSUITE_COMPANY_ROOT/<company_id>/prompts/<role>.md

    Falls back to the one-liner in config.json:
        config["agent_personalities"]["<role>"]

    Returns the prompt text (may be multi-paragraph markdown from .md
    or a single sentence from config.json).
    """
    prompt_file = COMPANY_ROOT / company_id / "prompts" / f"{role}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()

    return (
        config.get("agent_personalities", {})
              .get(role, f"You are the {role.upper()} of this company.")
    )
