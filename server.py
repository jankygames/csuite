"""
server.py — C-Suite parent web server.

Hosts the whole owner-facing surface from one process:

    /              Owner Dashboard   (multi-company landing — static React page)
    /memory.html   Institutional memory browser (per company)
    /settings.html Company settings editor (per company)
    /api/...       Dashboard data + memory + settings (reads/writes real files)
    /enter/<id>    Hand-off route   (records the picked company, redirects to chat)
    /chat          The Chainlit app (your existing app.py, mounted unchanged)

Run with:

    uvicorn server:app --port 8000

(Replaces `chainlit run app.py`. Chainlit still owns the deliberation UI — it
just lives under /chat now, with the dashboard in front.)

Why a parent FastAPI app instead of Chainlit custom endpoints?
    `mount_chainlit` is Chainlit's supported embedding path, and it lets the
    dashboard, the JSON API, and the chat share one origin (so links and cookies
    just work). Company hand-off is done server-side via a tiny pending-selection
    file rather than Chainlit's URL-param internals, which differ across versions.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from chainlit.utils import mount_chainlit

from core.config import COMPANY_ROOT, DEFAULTS, database_path

ROOT = pathlib.Path(__file__).parent
PUBLIC = ROOT / "public"
DASHBOARD = PUBLIC / "dashboard"

# Repo-bundled sample companies — seeded into COMPANY_ROOT on startup so a
# fresh clone has at least one company to click. Edits land in COMPANY_ROOT;
# the bundled originals stay pristine for re-distribution.
BUNDLED_COMPANIES = ROOT / "companies"
PROMPT_TEMPLATES = ROOT / "templates" / "prompts"

# Single-owner, local tool: a file is a perfectly good hand-off channel.
SESSION_DIR = ROOT / ".session"
SESSION_DIR.mkdir(exist_ok=True)
PENDING_FILE = SESSION_DIR / "pending_company.json"

app = FastAPI(title="C-Suite")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _company_dir(company_id: str) -> pathlib.Path | None:
    """Return the company dir iff it exists and has a config.json (path-safe)."""
    d = (COMPANY_ROOT / company_id)
    if d.is_dir() and (d / "config.json").exists() and d.parent == COMPANY_ROOT:
        return d
    return None


def _load_config(company_id: str) -> dict:
    d = _company_dir(company_id)
    if not d:
        return {}
    try:
        return json.loads((d / "config.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _db_path(company_id: str) -> pathlib.Path:
    return database_path(company_id)


# ── Dashboard data ───────────────────────────────────────────────────────────

def _read_company(d: pathlib.Path) -> dict | None:
    """Map a company's config.json (+ optional state.json) to a dashboard card."""
    config_file = d / "config.json"
    if not (d.is_dir() and config_file.exists()):
        return None
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    state = {}
    state_file = d / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}

    return {
        "id": d.name,
        "name": cfg.get("company_name", d.name),
        "mission": cfg.get("mission", ""),
        "stage": cfg.get("stage", "—"),
        "sector": cfg.get("industry", "—"),
        "employees": cfg.get("team_size"),
        "runway": cfg.get("runway", "—"),
        "priorities": cfg.get("strategic_priorities", []),
        "status": state.get("status", "idle"),
        "statusLabel": state.get("status_label", "Idle"),
        "lastSession": state.get("last_session"),
        "decisionsThisQuarter": state.get("decisions_quarter"),
        "href": f"/enter/{d.name}",
    }


def _company_index() -> list[dict]:
    """Lightweight [{id, name}] list used by the page switchers."""
    if not COMPANY_ROOT.exists():
        return []
    out = []
    for d in sorted(COMPANY_ROOT.iterdir()):
        if d.is_dir() and (d / "config.json").exists():
            cfg = _load_config(d.name)
            out.append({"id": d.name, "name": cfg.get("company_name", d.name)})
    return out


@app.get("/api/companies")
def api_companies():
    if not COMPANY_ROOT.exists():
        return JSONResponse({"companies": []})
    companies = [c for c in (_read_company(d) for d in sorted(COMPANY_ROOT.iterdir())) if c]
    return JSONResponse({"companies": companies})


# ── Institutional memory ─────────────────────────────────────────────────────

def _read_memory(company_id: str) -> dict:
    """
    Assemble the institutional-memory view for one company from the same
    sources the agents read at session start:
      • knowledge.md          — distilled institutional memory (indexer output)
      • SQLite decisions      — task / outcome / reasoning / escalation / override
      • SQLite agent_votes    — each exec's recommendation + confidence + concerns
      • SQLite sessions       — session summaries
    """
    from core.memory.indexer import load_knowledge, _load_meta

    cfg = _load_config(company_id)
    knowledge_text = load_knowledge(company_id)
    meta = _load_meta(company_id)

    decisions, sessions = [], []
    db = _db_path(company_id)
    if db.exists():
        try:
            with sqlite3.connect(str(db)) as conn:
                conn.row_factory = sqlite3.Row

                rows = conn.execute(
                    """
                    SELECT decision_id, task, outcome, reasoning, escalated,
                           human_override, decided_at
                    FROM decisions
                    ORDER BY decided_at DESC
                    """
                ).fetchall()
                for r in rows:
                    votes = conn.execute(
                        """
                        SELECT agent, recommendation, analysis, concerns, confidence
                        FROM agent_votes
                        WHERE decision_id = ?
                        """,
                        (r["decision_id"],),
                    ).fetchall()
                    decisions.append({
                        "id": r["decision_id"],
                        "task": r["task"],
                        "outcome": r["outcome"] or "",
                        "reasoning": r["reasoning"] or "",
                        "escalated": bool(r["escalated"]),
                        "humanOverride": r["human_override"] or "",
                        "decidedAt": r["decided_at"] or "",
                        "votes": [{
                            "agent": v["agent"],
                            "recommendation": (v["recommendation"] or "").upper(),
                            "analysis": v["analysis"] or "",
                            "concerns": _loads_list(v["concerns"]),
                            "confidence": v["confidence"],
                        } for v in votes],
                    })

                sessions = [dict(r) for r in conn.execute(
                    """
                    SELECT session_id, started_at, ended_at, task_count,
                           outcome_summary
                    FROM sessions
                    ORDER BY started_at DESC
                    LIMIT 25
                    """
                ).fetchall()]
        except sqlite3.Error:
            pass

    stats = {
        "decisions": len(decisions),
        "escalations": sum(1 for d in decisions if d["escalated"]),
        "overrides": sum(1 for d in decisions if d["humanOverride"]),
        "sessions": len(sessions),
    }

    return {
        "companyId": company_id,
        "companyName": cfg.get("company_name", company_id),
        "knowledge": {
            "text": knowledge_text,
            "exists": bool(knowledge_text),
            "lastIndexedAt": meta.get("last_indexed_at", ""),
            "indexedCount": meta.get("last_indexed_decision_count", 0),
        },
        "decisions": decisions,
        "sessions": sessions,
        "stats": stats,
    }


def _loads_list(raw) -> list:
    try:
        v = json.loads(raw) if raw else []
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


@app.get("/api/memory/{company_id}")
def api_memory(company_id: str):
    if not _company_dir(company_id):
        return JSONResponse({"error": "unknown company"}, status_code=404)
    return JSONResponse(_read_memory(company_id))


@app.post("/api/reindex/{company_id}")
async def api_reindex(company_id: str):
    """Force a fresh knowledge.md distillation off the event loop."""
    if not _company_dir(company_id):
        return JSONResponse({"error": "unknown company"}, status_code=404)
    try:
        from core.memory.indexer import run_indexer
        generated = await run_in_threadpool(run_indexer, company_id, True)
        return JSONResponse({"ok": True, "generated": bool(generated)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Settings ─────────────────────────────────────────────────────────────────

_EDITABLE_KEYS = {
    "company_name", "industry", "stage", "founded", "team_size", "runway",
    "mission", "strategic_priorities", "constraints",
    "risk_profile", "decision_style", "escalation_rules", "agent_personalities",
    # Paths the owner picks per company:
    "codebase_path", "documents_path", "database_path", "log_path",
    # Inference backend per company (defaults live in core/agents/base.py):
    "model_provider", "model_name", "context_length",
}
_TUNABLE_KEYS = set(DEFAULTS.keys())

# Roles whose behavioral prompts live in companies/<id>/prompts/<role>.md and
# whose runtime resolution (core.config.load_agent_prompt) prefers the .md file
# over the config.json fallback. The UI edits these directly.
_PROMPT_ROLES = ("ceo", "cfo", "coo", "cmo", "cto")


def _load_prompts(company_id: str, cfg: dict) -> dict:
    """
    Return per-role prompt content matching what runtime would load.

    For each role, prefer the .md file (what load_agent_prompt actually
    reads at session start). Fall back to config.json's agent_personalities
    one-liner if no .md exists. Tag the source so the UI can show whether
    the user is editing a real file or just the fallback.
    """
    d = _company_dir(company_id)
    if not d:
        return {}
    prompts_dir = d / "prompts"
    fallbacks = cfg.get("agent_personalities", {}) or {}
    out = {}
    for role in _PROMPT_ROLES:
        md_file = prompts_dir / f"{role}.md"
        if md_file.exists():
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                text = ""
            out[role] = {
                "content": text,
                "source": "file",
                "path": f"prompts/{role}.md",
                "size": len(text),
            }
        else:
            text = str(fallbacks.get(role, "") or "")
            out[role] = {
                "content": text,
                "source": "config_fallback" if text else "empty",
                "path": None,
                "size": len(text),
            }
    return out


@app.get("/api/settings/{company_id}")
def api_settings(company_id: str):
    if not _company_dir(company_id):
        return JSONResponse({"error": "unknown company"}, status_code=404)
    cfg = _load_config(company_id)
    tunables = {
        k: {"value": cfg.get(k, DEFAULTS[k]), "default": DEFAULTS[k],
            "overridden": k in cfg}
        for k in sorted(_TUNABLE_KEYS)
    }
    return JSONResponse({
        "companyId": company_id,
        "config": cfg,
        "tunables": tunables,
        "defaults": DEFAULTS,
        "prompts": _load_prompts(company_id, cfg),
    })


@app.put("/api/settings/{company_id}")
async def api_settings_save(company_id: str, request: Request):
    d = _company_dir(company_id)
    if not d:
        return JSONResponse({"error": "unknown company"}, status_code=404)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    cfg = _load_config(company_id)
    incoming = body.get("config", body) or {}

    for key, val in incoming.items():
        if key in _EDITABLE_KEYS or key in _TUNABLE_KEYS:
            cfg[key] = val

    try:
        (d / "config.json").write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    # Optional: write prompt .md files. The client sends only roles whose
    # text changed since load — we trust that diff and write what we get.
    # This is the path the UI uses to actually edit the behavioral prompts
    # the agents read at session start.
    incoming_prompts = body.get("prompts") or {}
    if isinstance(incoming_prompts, dict) and incoming_prompts:
        prompts_dir = d / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        for role, content in incoming_prompts.items():
            if role not in _PROMPT_ROLES:
                continue
            if not isinstance(content, str):
                continue
            try:
                (prompts_dir / f"{role}.md").write_text(content, encoding="utf-8")
            except OSError as exc:
                return JSONResponse(
                    {"ok": False, "error": f"prompts/{role}.md: {exc}"},
                    status_code=500,
                )

    return JSONResponse({
        "ok": True,
        "config": cfg,
        "prompts": _load_prompts(company_id, cfg),
    })


# ── Company hand-off ─────────────────────────────────────────────────────────

@app.get("/enter/{company_id}")
def enter_company(company_id: str):
    """Record the picked company, then drop the owner into the chat.

    The URL param is now the primary handoff — it survives reload, supports
    bookmarking, and (when the dashboard cards open with target=_blank) lets
    multiple companies run in parallel tabs without racing on a shared file.
    The pending-file write is kept as a fallback for clients that arrive at
    /chat/ without the param (manual URL typing, old bookmarks)."""
    if not _company_dir(company_id):
        return RedirectResponse(url="/", status_code=303)
    PENDING_FILE.write_text(json.dumps({"company_id": company_id}), encoding="utf-8")
    return RedirectResponse(url=f"/chat/?company={company_id}", status_code=303)


# ── Company index (for the memory/settings switchers) ─────────────────────────

@app.get("/api/company-index")
def api_company_index():
    return JSONResponse({"companies": _company_index()})


# ── Seed bundled sample companies on first boot ───────────────────────────────

_COMPANY_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    task_count      INTEGER DEFAULT 0,
    outcome_summary TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    task            TEXT NOT NULL,
    outcome         TEXT,
    reasoning       TEXT,
    escalated       INTEGER DEFAULT 0,
    human_override  TEXT,
    decided_at      TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE TABLE IF NOT EXISTS agent_votes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL,
    agent           TEXT NOT NULL,
    recommendation  TEXT NOT NULL,
    analysis        TEXT,
    concerns        TEXT,
    confidence      REAL,
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
);
CREATE TABLE IF NOT EXISTS knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    category    TEXT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT,
    added_at    TEXT,
    chroma_id   TEXT
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS worker_outputs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    worker      TEXT NOT NULL,
    task        TEXT NOT NULL,
    success     INTEGER NOT NULL,
    summary     TEXT,
    output      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_company
    ON decisions(company_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_votes_decision
    ON agent_votes(decision_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_company
    ON knowledge(company_id, category);
CREATE INDEX IF NOT EXISTS idx_chat_company
    ON chat_messages(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_worker_company
    ON worker_outputs(company_id, created_at DESC);
"""


def _init_company_db(db_path: pathlib.Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_COMPANY_DB_SCHEMA)


def _seed_sample_companies() -> None:
    """
    Copy each bundled sample company into COMPANY_ROOT if it isn't already
    there. Lets a fresh clone of the repo show a working sample in the
    dashboard immediately. Idempotent — existing companies are never touched.
    """
    if not BUNDLED_COMPANIES.exists():
        return
    # Skip when the user has pointed COMPANY_ROOT at the bundled dir directly —
    # there's no copy to make and we'd just loop on the same files.
    try:
        if BUNDLED_COMPANIES.resolve() == COMPANY_ROOT.resolve():
            return
    except OSError:
        return
    COMPANY_ROOT.mkdir(parents=True, exist_ok=True)

    for src in sorted(BUNDLED_COMPANIES.iterdir()):
        if not src.is_dir():
            continue
        src_cfg = src / "config.json"
        if not src_cfg.exists():
            continue
        dest = COMPANY_ROOT / src.name
        if (dest / "config.json").exists():
            continue   # already present — never clobber

        try:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "config.json").write_text(
                src_cfg.read_text(encoding="utf-8"), encoding="utf-8"
            )
            # Prompts: prefer bundled prompts/ if present, else templates/prompts/
            bundled_prompts = src / "prompts"
            prompt_src = bundled_prompts if bundled_prompts.exists() else PROMPT_TEMPLATES
            if prompt_src.exists():
                (dest / "prompts").mkdir(exist_ok=True)
                for role in _PROMPT_ROLES:
                    pf = prompt_src / f"{role}.md"
                    if pf.exists():
                        (dest / "prompts" / f"{role}.md").write_text(
                            pf.read_text(encoding="utf-8"), encoding="utf-8"
                        )
            (dest / "chroma").mkdir(exist_ok=True)
            _init_company_db(database_path(src.name))
        except OSError:
            # Don't take down the server because a sample failed to seed —
            # the user can still use any companies that did get through.
            pass


_seed_sample_companies()


# ── Static dashboard (mounted LAST so the routes above win) ───────────────────
mount_chainlit(app=app, target="app.py", path="/chat")

app.mount("/", StaticFiles(directory=str(DASHBOARD), html=True), name="dashboard")
