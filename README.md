# Agentic C-Suite System

A locally-hosted multi-agent system that simulates a full C-suite executive
team. Spin up multiple independent "company instances," each with its own
C-suite that deliberates on decisions, debates internally, and brings you
structured recommendations. You are the final decision-maker.

Built on **LangGraph** and **Ollama** — runs entirely on your local machine
with no cloud dependencies. Supports hybrid model providers (Ollama for local
inference, Anthropic API as an option) configurable per company.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Memory System](#memory-system)
4. [The Deliberation Loop](#the-deliberation-loop)
5. [Agent Roles](#agent-roles)
6. [Repository Structure](#repository-structure)
7. [Hardware Requirements](#hardware-requirements)
8. [Installation](#installation)
9. [Creating a Company](#creating-a-company)
10. [Owner Dashboard](#owner-dashboard)
11. [Running a Session](#running-a-session)
12. [Configuration Reference](#configuration-reference)
13. [Design Decisions](#design-decisions)
14. [What's Next](#whats-next)

---

## System Overview

You interact with a **CEO agent** that manages a team of executive agents
(CFO, COO, CMO, CTO — extensible). The system supports three modes:

**Chat** — Talk naturally with the CEO. Ask questions, get status updates,
discuss strategy. The CEO answers from the company's institutional knowledge
document without running a formal deliberation.

**Deliberate** — Say "should we..." to trigger a full C-suite deliberation:
1. All C-suite agents independently analyze the task
2. Agents read each other's positions and debate (cross-response round)
3. The CEO synthesizes all outputs into a recommendation
4. If deadlocked, a second round with explicit conflict framing
5. You approve, override, or provide new information for reconsideration

**Execute** — Say "implement", "draft", "build", "research", etc. to dispatch
worker agents directly. Workers execute concrete tasks: CCA writes code,
CWA drafts content, CRA produces research reports, CSA creates social posts.

Everything is written to institutional memory for future context.

The system is **repeatable** — each company is an isolated instance with its
own configuration, history, and memory. Spinning up Company B costs nothing
extra; it uses the same inference server as Company A.

---

## Architecture

```
You (final decision-maker)
        │
        ▼
   CEO Agent  ◄──── sole interface to you
        │
        ├── C-Suite Tier (deliberation)
        │   ├── CFO Agent  (financial risk)
        │   ├── COO Agent  (operational feasibility)
        │   ├── CMO Agent  (market and customer impact)
        │   └── CTO Agent  (technical risk)
        │
        └── Worker Tier (execution — runs after human approval)
            ├── CCA Agent  (Claude Code Agent — edits code, runs commands)
            ├── CWA Agent  (Content Writer — blog posts, copy, docs)
            ├── CRA Agent  (Research — competitive analysis, market research)
            └── CSA Agent  (Communications — social media, Discord, email)
                │
                ▼
        Ollama Inference Server (default, configurable per company)
                │
                ▼
        Hardware
        RTX 3090 · 24 GB VRAM  |  Ryzen 9 5950X · 64 GB RAM
        SSD (D:, E:) for models and code
        HDD (F:, G:) for logs and company data
```

**Two agent tiers:**
- **C-suite agents** deliberate on decisions. They are registered in
  `CSUITE_AGENTS` (`core/agents/__init__.py`) and run sequentially.
- **Worker agents** execute concrete tasks after human approval. They are
  registered in `WORKER_AGENTS` and auto-dispatched by keyword matching.

**Orchestration:** LangGraph — stateful agent graphs with native
human-in-the-loop interrupt support and clean multi-instance isolation.

**Inference:** Configurable per company via `model_provider` in config.json.
Default is Ollama (local). Anthropic API is also supported. All agents within
a company share the same provider.

**Embeddings:** `nomic-embed-text` via Ollama. 768-dimensional vectors.
Fast, lightweight, runs alongside the main model.

---

## Memory System

Five distinct memory layers, each with a different lifespan and purpose:

### 1. Working Memory
**What:** LangGraph `TypedDict` state object in RAM  
**Lifespan:** Current session only — cleared when session ends  
**Contains:** Current task, all agent outputs, CEO synthesis, escalation flags  
**Purpose:** The "whiteboard" during an active deliberation  

### 2. Episodic Memory
**What:** SQLite database — one file per company on HDD (`G:/csuite_data/`)  
**Lifespan:** Permanent — survives restarts and crashes  
**Contains:** Every session, decision, agent vote, and human override  
**Purpose:** Institutional history — what happened, who argued what, how you overruled  

Schema:
```sql
sessions     — one row per work session (start, end, outcome summary)
decisions    — every decision made or escalated, with CEO reasoning
agent_votes  — each agent's recommendation and full analysis per decision
knowledge    — freeform company knowledge (manually added or agent-discovered)
```

### 3. Distilled Knowledge (Primary)
**What:** `knowledge.md` — a structured document generated by an indexer LLM  
**Location:** `CSUITE_COMPANY_ROOT/<id>/knowledge.md`  
**Lifespan:** Rebuilt periodically — versioned snapshots saved every N days  
**Contains:** Decision precedents, owner profile, executive dynamics, strategic
context, lessons learned — all distilled from the full SQLite history  
**Purpose:** Replaces traditional RAG. The entire document is loaded into
context at session start. No retrieval step, no chunking, no missed results.
Agents see the complete institutional picture.  

**How it works (Karpathy-style):**
An indexer LLM reads the full decision history from SQLite and produces a
well-organized knowledge document. This runs automatically after `memory_write`
when enough new decisions accumulate (`index_threshold` in config, default 5),
or on first session if no knowledge.md exists. It can also be triggered manually:

```powershell
python scripts/run_indexer.py --company acme_corp [--force]
```

Versioned snapshots are saved to `knowledge_versions/` every `index_version_days`
days (default 7).

### 4. Semantic Memory (Fallback)
**What:** ChromaDB vector store — one store per company (`CSUITE_COMPANY_ROOT/<id>/chroma/`)  
**Lifespan:** Permanent — grows over time  
**Contains:** Embedded decision reasoning (searchable by meaning)  
**Purpose:** Fallback for companies that haven't generated a knowledge.md yet.
Once knowledge.md exists, ChromaDB is bypassed in favor of the distilled document.  

### 5. Company DNA
**What:** `config.json` — one file per company (`CSUITE_COMPANY_ROOT/<id>/config.json`)  
**Lifespan:** Permanent — changes only when you explicitly update it  
**Contains:** Mission, goals, constraints, risk profile, escalation rules, agent personalities  
**Purpose:** The company's identity — injected into every agent's system prompt  

**Key principle:** Human overrides are first-class data. Every time you
contradict what the agents recommended, that gets written to the database
with your reasoning. Over time this teaches the system what you actually value.

---

## The Deliberation Loop

```
Task arrives
    │
    ▼
Memory retrieval (knowledge.md + SQLite gap-fill, ChromaDB fallback)
    │
    ▼
Prior decision check
    │
    ├── Already decided? ──► CEO answers from knowledge ──► Human interrupt
    │
    └── New topic ──►
    │
    ▼
Round 1 — Independent analysis
    CFO ──┐
    COO ──┤ each agent analyzes in isolation
    CMO ──┤ no agent sees any peer output yet
    CTO ──┘
    │
    ▼
Cross-response round
    CFO responds to COO, CMO, CTO positions ──┐
    COO responds to CFO, CMO, CTO positions ──┤
    CMO responds to CFO, COO, CTO positions ──┤
    CTO responds to CFO, COO, CMO positions ──┘
    │
    ▼
CEO synthesis
    Reads all 8 outputs · identifies conflicts
    │
    ├── Consensus reached? ──► Present recommendation to you
    │
    └── Conflict? ──► Round 2 (CEO frames the specific tensions)
                          │
                          ▼
                     CEO synthesis (final)
                          │
                          ├── Consensus? ──► Present to you
                          │
                          └── Still deadlocked? ──► Escalate to you with options
    │
    ▼
Human interrupt (LangGraph pauses · waits for your input)
    │
    ├── "approve" / "implement" ──► Worker dispatch (CCA, etc.)
    │                                     │
    │                                     ▼
    │                               Memory write
    │
    ├── "override <reason>" ──► Memory write (records override)
    │
    └── "more info <details>" ──► Reconsider with new info
                                      │
                                      ▼
                                 Back to Round 1 (full re-deliberation)
    │
    ▼
Next task or end session
```

**Why cross-response?**  
Round 1 gives you four independent positions. The cross-response round is
where the system earns its value — agents can agree with peers, push back
with specifics, or surface information that changes the picture. The CEO
then synthesizes eight outputs, not four. This is qualitatively different
from agents monologuing in sequence.

**Why force round 2 before escalating?**  
Many apparent deadlocks are actually positioning differences — two agents
saying the same thing in different language. The CEO's round-2 framing
explicitly names the tensions and gives agents a chance to converge. Only
genuine substantive conflicts survive to escalation.

---

## Agent Roles

### CEO — Chief Executive Officer
**Position in graph:** Synthesis layer only — does not participate in deliberation rounds  
**Inputs:** All CFO/COO/CMO/CTO outputs from both rounds  
**Output:** Structured synthesis with consensus/conflict assessment, recommendation, escalation decision  
**Special responsibilities:**
- Sole interface to you — formats and presents the full deliberation
- Enforces company DNA escalation rules (hard override — triggers regardless of consensus)
- Frames round-2 conflict explicitly to help agents converge
- Builds institutional memory by logging all decisions with full reasoning

### CFO — Chief Financial Officer
**Primary lens:** Cash flow · unit economics · risk-adjusted return  
**Most likely to recommend:** `block`  
**Behavioral trait:** Always quantifies when possible. If recommending block,
states precisely what financial condition would need to change.

### COO — Chief Operating Officer
**Primary lens:** Execution feasibility · capacity · timeline realism  
**Most likely to recommend:** `modify`  
**Behavioral trait:** Asks "how will this actually get done?" before accepting
any plan. Surfaces hidden dependencies between departments.

### CMO — Chief Marketing Officer
**Primary lens:** Customer impact · market positioning · brand coherence  
**Most likely to recommend:** `proceed`  
**Behavioral trait:** Leads with the customer. Provides competitive context.
Honest about when an argument is brand judgment vs. data.

### CTO — Chief Technology Officer
**Primary lens:** Technical feasibility · architectural coherence · technical debt  
**Most likely to recommend:** `modify`  
**Behavioral trait:** Speaks plainly — avoids jargon or explains it immediately.
Flags security and reliability concerns every time, even if the room is comfortable.

### Worker Tier

Workers sit below the C-suite. They execute concrete tasks — triggered by
keyword matching against your instruction. Interactive workers (CCA) support
multi-turn sessions; non-interactive workers return their output directly.

### CCA — Claude Code Agent
**Tier:** Worker (interactive)  
**Trigger keywords:** code, codebase, build app, frontend, backend, api, fix bug, ...  
**What it does:** Connects to a local Claude Code instance via the Python SDK,
pointed at the company's `codebase_path`. Edits files, runs commands, creates
assets — with real-time streaming. Supports multi-turn conversations: send
follow-up instructions, type **done** to end the session.  
**Requires:** `codebase_path` set in company config.json, Claude Code CLI installed  

### CWA — Content Writer Agent
**Tier:** Worker (non-interactive)  
**Trigger keywords:** write, draft, blog, post, copy, content, newsletter, article, ...  
**What it does:** Drafts written content using the company's brand voice — blog
posts, game descriptions, newsletters, press releases, documentation.  

### CRA — Research Agent
**Tier:** Worker (non-interactive)  
**Trigger keywords:** research, analyze, competitive, market, pricing, evaluate, ...  
**What it does:** Produces structured research reports — competitive analysis,
market research, pricing studies, technology evaluations.  

### CSA — Communications Agent
**Tier:** Worker (non-interactive)  
**Trigger keywords:** social media, social post, tweet, discord, post to, ...  
**What it does:** Drafts platform-appropriate communications — social posts,
Discord announcements, email campaigns, community updates.  

### Agent Prompt System

Each agent's personality and behavioral instructions are loaded from markdown
files in the company's `prompts/` directory:

```
CSUITE_COMPANY_ROOT/<company_id>/prompts/
    ├── ceo.md
    ├── cfo.md
    ├── coo.md
    ├── cmo.md
    └── cto.md
```

These are full behavioral prompts — not one-liners. They define thinking
frameworks, decision-making style, communication style, and behavioral rules.
Template prompts are included in `templates/prompts/` as a starting point.

If no `.md` file exists, the system falls back to the `agent_personalities`
field in `config.json`.

### Adding New Agents

**New C-suite agent** (e.g. CISO, Chief Art Director):
1. Create `core/agents/<role>.py` extending `BaseAgent`
2. Import and append to `CSUITE_AGENTS` in `core/agents/__init__.py`
3. Create `prompts/<role>.md` in the company's data folder
4. Optionally add a fallback one-liner to `agent_personalities` in `config.json`

**New worker agent** (e.g. art, data analysis):
1. Create `core/agents/<role>.py` extending `BaseWorker`
2. Define `role`, `title`, `keywords`, `interactive`, and `execute(task) -> dict`
3. Import and append to `WORKER_AGENTS` in `core/agents/__init__.py`

The graph picks up new agents automatically — no graph or node changes needed.

---

## Repository Structure

```
D:\csuite\
│
├── server.py                       ← Parent FastAPI app — entry point
├── app.py                          ← Chainlit chat app (mounted at /chat)
│
├── public\
│   ├── custom.css                  ← Chainlit chat theme (matches dashboard tokens)
│   ├── custom.js                   ← Status chips + monogram avatars in chat
│   └── dashboard\                  ← React SPA: companies / memory / settings
│       ├── index.html              ← Owner dashboard at /
│       ├── memory.html             ← Memory browser at /memory.html
│       ├── settings.html           ← Settings editor at /settings.html
│       ├── styles.css              ← Design tokens (OKLCH palette, font stack)
│       └── *.jsx, *.css            ← In-browser React (Babel standalone)
│
├── core\
│   ├── config.py                   ← Centralised path config (env vars)
│   ├── state.py                    ← LangGraph CompanyState TypedDict
│   │
│   ├── agents\
│   │   ├── __init__.py             ← Agent registries (CSUITE_AGENTS, WORKER_AGENTS)
│   │   ├── base.py                 ← C-suite base: LLM call, hybrid parser, retry
│   │   ├── base_worker.py          ← Worker base: execute interface, keyword matching
│   │   ├── ceo.py                  ← CEO: synthesis, presentation, escalation rules
│   │   ├── cfo.py                  ← CFO: financial risk
│   │   ├── coo.py                  ← COO: operational feasibility
│   │   ├── cmo.py                  ← CMO: market and customer impact
│   │   ├── cto.py                  ← CTO: technical risk
│   │   ├── cca.py                  ← CCA: Claude Code Agent (worker, interactive)
│   │   ├── cwa.py                  ← CWA: Content Writer Agent (worker)
│   │   ├── cra.py                  ← CRA: Research Agent (worker)
│   │   └── csa.py                  ← CSA: Communications Agent (worker)
│   │
│   ├── graph\
│   │   ├── __init__.py
│   │   ├── session_graph.py        ← Builds and compiles the LangGraph graph
│   │   ├── nodes.py                ← All node functions (task_intake, deliberation, etc.)
│   │   ├── edges.py                ← conflict_router conditional edge
│   │   └── runner.py               ← CLI entry point (legacy — use app.py instead)
│   │
│   ├── memory\
│   │   ├── __init__.py
│   │   ├── indexer.py              ← Karpathy-style knowledge distiller (SQLite → knowledge.md)
│   │   ├── retrieval.py            ← Distilled knowledge (primary) + ChromaDB (fallback)
│   │   └── writer.py               ← SQLite + ChromaDB write + re-index trigger
│   │
│   └── tools\
│       ├── __init__.py
│       └── cca_tool.py             ← Direct invocation wrapper for CCA
│
├── templates\
│   ├── example_config.json         ← Company DNA template (copy when creating)
│   └── prompts\                    ← Starter agent prompt templates
│       ├── ceo.md
│       ├── cfo.md
│       ├── coo.md
│       ├── cmo.md
│       └── cto.md
│
├── scripts\
│   ├── new_company.py              ← Scaffold a new company instance
│   └── run_indexer.py              ← Manual knowledge indexer CLI
│
├── requirements.txt
├── .chainlit\config.toml            ← Chainlit settings (loads custom.css/js)
├── .gitignore
├── README.md
├── INSTALL.md                       ← step-by-step setup guide
└── DESIGN.md                        ← design system reference

D:\models\ollama\                   ← Ollama model cache (set via OLLAMA_MODELS env var)
E:\venvs\csuite\                    ← Python virtual environment

G:\csuite_data\                     ← CSUITE_DATA_ROOT — SQLite databases (HDD)
│   └── <company_id>\
│       └── <company_id>.db
│
G:\csuite_data\companies\           ← CSUITE_COMPANY_ROOT — configs + knowledge + ChromaDB
│   └── <company_id>\
│       ├── config.json
│       ├── prompts\                ← agent personality prompts (markdown)
│       │   ├── ceo.md
│       │   ├── cfo.md
│       │   ├── coo.md
│       │   ├── cmo.md
│       │   └── cto.md
│       ├── knowledge.md            ← distilled institutional memory (auto-generated)
│       ├── index_meta.json         ← indexer state tracking
│       ├── knowledge_versions\     ← timestamped snapshots
│       ├── chroma\                 ← ChromaDB fallback store
│       └── documents\              ← CWA/CRA/CSA artifacts (write_artifact target;
│                                     override per-company via documents_path in config.json)

F:\csuite_logs\                     ← CSUITE_LOG_ROOT — Session logs (HDD)
│   └── <company_id>\sessions\
```

---

## Hardware Requirements

| Component | Minimum | This build |
|---|---|---|
| GPU VRAM | 20 GB | RTX 3090 · 24 GB |
| RAM | 32 GB | 64 GB |
| CPU cores | 8 | Ryzen 9 5950X · 16 cores |
| SSD free | 40 GB | D:\ + E:\ |
| OS | Windows 10 | Windows 10 Pro |

The **RTX 3090's 24 GB VRAM** is the critical resource. The default model
(`gpt-oss:20b`) fits comfortably with headroom for KV cache. The 64 GB RAM
provides ample CPU offload headroom and headroom for ChromaDB + SQLite
operations.

---

## Installation

See the full **[Installation & Setup Guide](INSTALL.md)** for step-by-step
instructions including troubleshooting. The summary:

**1. NVIDIA drivers**
```
Verify with: nvidia-smi
```

**2. Python 3.11**
```powershell
# After installing from python.org
python -m venv E:\venvs\csuite
E:\venvs\csuite\Scripts\Activate.ps1
pip install --upgrade pip
```

**3. Ollama — redirect model storage before installing**
```powershell
# Set this environment variable BEFORE installing Ollama
# System Properties → Advanced → Environment Variables
# Variable: OLLAMA_MODELS   Value: D:\models\ollama
```

**4. Pull models**
```bash
ollama pull gpt-oss:20b                   # primary model
ollama pull nomic-embed-text               # ~250 MB download
```

**5. Install Python packages**
```powershell
# With venv active:
pip install -r requirements.txt
```

**6. Clone this repository to D:\csuite\**

**7. Set data path environment variables**
```powershell
# System Properties → Advanced → Environment Variables
# These control where company data is stored (outside the repo)
#
# Variable: CSUITE_COMPANY_ROOT   Value: G:\csuite_data\companies
# Variable: CSUITE_DATA_ROOT      Value: G:\csuite_data
# Variable: CSUITE_LOG_ROOT       Value: F:\csuite_logs
#
# All three have sensible defaults — see core/config.py
```

---

## Creating a Company

```powershell
cd D:\csuite
python scripts/new_company.py --id acme_corp --name "Acme Corp" --industry "B2B SaaS"
```

This creates:
- `CSUITE_COMPANY_ROOT/acme_corp/config.json` — edit this to define the company
- `CSUITE_COMPANY_ROOT/acme_corp/prompts/*.md` — agent personality prompts (edit these)
- `CSUITE_COMPANY_ROOT/acme_corp/chroma/` — ChromaDB vector store (starts empty)
- `CSUITE_DATA_ROOT/acme_corp/acme_corp.db` — SQLite database with schema initialized
- `CSUITE_LOG_ROOT/acme_corp/sessions/` — log directory

**Then:**
1. Edit `config.json` to set mission, priorities, constraints, and escalation rules
2. Edit `prompts/*.md` to customize each agent's personality, thinking frameworks,
   and behavioral rules (see `templates/prompts/` for the starter format)

---

## Owner Dashboard

Beyond the chat, the system ships with a multi-company web dashboard. It's
served by a parent FastAPI app ([server.py](server.py)) that mounts the
Chainlit chat at `/chat`. One process, one origin, four surfaces:

```
http://localhost:8000/
├── /                  Companies dashboard — card grid; pick a company to enter
├── /memory.html       Institutional memory browser (per company)
├── /settings.html     Editable config.json + tunables (per company)
├── /chat              Chainlit deliberation UI (your existing app.py, mounted)
└── /api/...           JSON endpoints behind the three pages
```

**Companies dashboard** (`/`) — card grid of every company under
`CSUITE_COMPANY_ROOT`. Each card shows mission, stage, sector, strategic
priorities, and live status. Clicking a card → `/enter/<id>` → records the
pick in `.session/pending_company.json` → 303 → `/chat`, where the chat
auto-loads that company (no in-chat picker needed).

**Memory browser** (`/memory.html?company=<id>`) — read-only view over a
company's institutional memory:
- Distilled `knowledge.md` (rendered with a small bespoke markdown renderer)
- Full decision log with per-agent votes, confidence, concerns, and
  owner overrides flagged
- Re-index button (`POST /api/reindex/<id>`) that forces a fresh
  knowledge.md distillation
- Sidebar: decision / session / escalation / override counts, plus
  index-drift stats

**Settings editor** (`/settings.html?company=<id>`) — editable view of
`config.json`. Save issues `PUT /api/settings/<id>`, which merges only a
whitelist of keys (`_EDITABLE_KEYS ∪ _TUNABLE_KEYS` in server.py) back
onto the existing file. The whitelist covers identity, mission, decision
rules, agent personalities, **paths** (`codebase_path`, `documents_path`),
**model config** (`model_provider`, `model_name`, `context_length`), and
engine tunables. Anything outside that whitelist — most importantly the
`ANTHROPIC_API_KEY` (which lives in `.env`, not config.json) — is never
touched.

**Chat theme** — `.chainlit/config.toml` loads `public/custom.css` (ports
the dashboard's OKLCH palette and font stack onto Chainlit's message DOM)
and `public/custom.js` (adds status chips on `**PROCEED/MODIFY/BLOCK/ESCALATE**`
and per-role monogram avatars). See [DESIGN.md](DESIGN.md) for the full
design system reference.

**Optional:** `companies/<id>/state.json` is read by the dashboard to show
live card status (Idle / Deliberating / Pending). Without it every card
shows "Idle" — an honest default. To light cards up, write to that file
from `app.py` when a session changes phase.

---

## Running a Session

### Web UI — recommended

```powershell
# Activate the virtual environment first
E:\venvs\csuite\Scripts\Activate.ps1

cd D:\csuite
uvicorn server:app --port 8000
```

Open `http://localhost:8000/` — the **owner dashboard**. Click a company
card and you land in its deliberation session at `/chat`. From there you
can interact in three modes:

**Chat mode** (default) — talk naturally with the CEO:
- "What did we decide about the dice roller?"
- "How are things going?"
- "Remind me about our monetization plan"

The CEO answers from the company's distilled knowledge document with
streaming output — responses appear word by word as they generate.

**Deliberation mode** — triggered by decision-oriented phrases:
- "Should we launch a mobile app?"
- "Let's decide on pricing"

The full C-suite deliberates. After the recommendation, respond with:
- **approve** — accept and write to memory
- **implement** — approve and dispatch workers to execute
- **override** *reason* — override with your decision
- **more info** *details* — re-deliberate with new context

**Execute mode** — triggered by action phrases or "implement":
- "Draft a blog post about the dice roller"
- "Research competitive pricing for tabletop RPGs"
- "Build a landing page" → starts interactive CCA session
- Or say "do it" / "go ahead" after discussing a task in chat

Workers are dispatched automatically by keyword matching. Non-interactive
workers (CWA, CRA, CSA) stream their output in real time. Interactive
workers (CCA) start a multi-turn session — type **done** to end it.

The system uses LLM-powered intent classification with conversation context,
so it understands "sounds good, make it happen" after discussing a feature.

### CLI (legacy)

The original terminal runner still works if you prefer:

```powershell
E:\venvs\csuite\Scripts\Activate.ps1

cd D:\csuite
python -m core.graph.runner --company acme_corp --task "Should we raise our prices by 10%?"

# With additional context
python -m core.graph.runner `
    --company acme_corp `
    --task "Should we raise our prices by 10%?" `
    --context "Q3 revenue missed target by 8%. Churn rate is 4.2%, above our 3% goal."
```

---

## Configuration Reference

`config.json` fields:

| Field | Type | Description |
|---|---|---|
| `company_id` | string | Snake_case identifier. Must match folder name. |
| `company_name` | string | Display name used in agent prompts and reports. |
| `industry` | string | Industry context injected into every agent's system prompt. |
| `stage` | string | `"early"` / `"growth"` / `"mature"` — affects agent risk calibration. |
| `mission` | string | One sentence. Injected into CEO system prompt. |
| `strategic_priorities` | list | Current top priorities. Agents reference these when assessing proposals. |
| `constraints` | list | Hard limits. Agents treat these as non-negotiable. |
| `risk_profile` | string | `"conservative"` / `"moderate"` / `"aggressive"` |
| `decision_style` | string | Free-form description of how the company makes decisions. |
| `escalation_rules.always_escalate` | list | Any task matching these patterns triggers escalation regardless of consensus. |
| `escalation_rules.escalate_if_deadlock` | bool | Escalate after round 2 if still deadlocked. |
| `escalation_rules.ceo_can_decide_alone` | list | Topics the CEO may resolve without escalating. |
| `model_provider` | string | `"ollama"` (default) or `"anthropic"` — which LLM backend to use. |
| `model_name` | string | Override default model for the chosen provider. Default: `gpt-oss:20b` (ollama). |
| `context_length` | int | Context window size for Ollama. Default: 32768. Model supports up to 131072. |
| `indexer_model` | string | Model for the knowledge indexer. Empty = use company's `model_name`. |
| `index_threshold` | int | Re-index after this many new decisions. Default: 5. |
| `index_version_days` | int | Save versioned knowledge snapshot every N days. Default: 7. |
| `codebase_path` | string | Absolute path to the codebase this company manages. Required for CCA worker. |
| `documents_path` | string | Absolute path where CWA/CRA/CSA write their artifacts. Defaults to `<COMPANY_ROOT>/<id>/documents/`. Auto-created on first write. |
| `chat_history_length` | int | Max messages kept in conversation history. Default: 20. |
| `chat_message_cap` | int | Max chars per message included in context. Default: 10000. |
| `cca_max_turns` | int | Max Claude Code SDK turns per CCA session. Default: 50. |
| `worker_max_tokens` | int | Max output tokens for non-interactive workers. Default: 4096. |
| `ceo_chat_max_tokens` | int | Max output tokens for CEO chat replies. Default: 2048. |
| `knowledge_max_pct` | int | Max % of context_length for knowledge.md. Default: 50. |
| `agent_personalities.*` | string | Per-agent fallback personality. Used only if no `prompts/<role>.md` file exists. |

---

## Design Decisions

**Why LangGraph over CrewAI or AutoGen?**  
LangGraph's native `interrupt_before` support is the key feature. The
human-in-the-loop pause is a first-class primitive — not something bolted
on. Multi-instance state isolation (one graph + checkpointer per company)
also maps cleanly onto the repeatable-company requirement.

**Why sequential agent execution?**  
The default Ollama backend serves one request at a time on the RTX 3090, so
"parallel" execution would just queue at the server anyway. Sequential is
honest, simpler to debug, and produces the same output. Companies that opt
into `model_provider: "anthropic"` could in principle fan out, but the
deliberation loop stays sequential to keep state, logging, and reasoning
order identical across backends.

**Why does the CEO not deliberate?**  
The CEO is the arbitration layer, not a participant. If the CEO argued a
position in round 1, its round-3 synthesis would be biased by its own
earlier commitment. The CEO sees everything fresh and synthesizes without
prior stake in any position.

**Why is `agent_outputs` accumulated with `operator.add`?**  
LangGraph state fields are replaced by default. The `operator.add`
annotation means new outputs append to the list rather than overwriting
it. By the time the CEO synthesizes after round 2, it sees all 16 outputs
(4 + 4 + 4 + 4) in one state field.

**Why store full reasoning, not just outcomes?**  
"We approved vendor A" is useless six months later. "We chose vendor A
because the CFO flagged vendor B's payment terms as a Q3 cash flow risk,
and the CEO weighted that above the CMO's brand preference" — that is
memory that actually informs future decisions.

**Why are human overrides first-class data?**  
Every time you contradict the agents, the system records what you decided
and implicitly what you value. Over time this is the highest-signal data
in the system — it encodes your actual judgment, not the agents' defaults.

**Why distilled knowledge over RAG?**  
Traditional RAG (embed → vector search → retrieve chunks) misses connections
between related decisions, suffers from chunking artifacts, and only shows
agents a few fragments. The Karpathy-style approach distills the full decision
history into a structured knowledge document offline, then loads it entirely
into context at session start. Agents see the complete institutional picture —
patterns, precedents, owner preferences — not just the top 5 search results.
Company histories are bounded (hundreds of decisions, not millions of documents),
so the distilled document fits comfortably in the 131K context window.

---

## What's Next

The foundation is complete. Planned additions in order:

### Near-term

1. ~~**Chainlit UI**~~ — **done** (`app.py`)
2. ~~**Owner Dashboard**~~ — **done** (`server.py` + `public/dashboard/`,
   mounts Chainlit at `/chat`)
3. ~~**Memory browser**~~ — **done** (`/memory.html` reads `knowledge.md`
   + SQLite decisions/votes/sessions; force-reindex from UI)
4. ~~**Settings editor**~~ — **done** (`/settings.html` edits whitelisted
   `config.json` keys + engine tunables)
5. **Live end-to-end test** — first real deliberation session through the UI
6. **Per-agent streaming in UI** — break deliberation nodes into individual
   agent nodes so the UI shows each agent's output the moment it finishes,
   not after the whole round completes
7. **Task context input in UI** — let users provide background context
   alongside the task (the CLI `--context` flag has no UI equivalent yet)
8. **Live card status** — wire `companies/<id>/state.json` writes into
   `app.py` so dashboard cards reflect Idle / Deliberating / Pending in
   real time (the dashboard already reads the file; the writer is the gap)
9. ~~**Non-code worker artifacts on disk**~~ — **done** (CWA/CRA/CSA
   results land under `documents_path`; dispatcher routes doc-shaped
   requests to CWA instead of falling through to CCA)

### Medium-term

1. **Dynamic escalation thresholds** — tie spend-based escalation rules to
   actual financial data (e.g. "escalate if proposed spend exceeds 10% of
   trailing monthly free cash flow") instead of a static dollar amount.
   Requires a financials data source — see Financial Data Integration below.
2. **Financial data integration** — add a `financials` table to the per-company
   SQLite database (cash on hand, monthly revenue, monthly expenses, FCF).
   Agents can query this during deliberation for data-grounded recommendations.
   Could be updated manually, via CSV import, or eventually via accounting
   API integration (QuickBooks, Wave, etc.). Scaffolding exists in
   `scripts/financials.py` + `core/memory/financials.py`.
3. **Knowledge ingestion pipeline** — load external company documents, market
   data, and competitor information into the distilled knowledge system.
   Scaffolding exists in `scripts/ingest.py` + `core/memory/ingest.py`.
4. **Multi-task agenda** — handle a queue of tasks in one session rather
   than one task per session

### Longer-term

1. **Agent memory review** — a tool/dashboard to inspect what the system has
   learned about your decision-making patterns over time (which agents you
   agree with most, how often you override, recurring themes in overrides).
   Scaffolding exists in `scripts/audit.py`.
2. **Decision audit trail** — exportable history of all decisions, agent
   reasoning, and human overrides for a company, useful for retrospectives
   or onboarding a co-founder/partner into the system
3. **Agent personality tuning from feedback** — automatically adjust agent
   personality prompts based on accumulated human override data (e.g. if
   you consistently override the CFO's conservative blocks, nudge its
   risk calibration). Scaffolding exists in `scripts/tune_prompts.py`.
4. **Scheduled sessions** — recurring deliberation sessions triggered on a
   schedule (e.g. weekly strategy review) with auto-generated agenda items
   pulled from company knowledge and recent decisions. Scaffolding exists in
   `scripts/scheduled_session.py`.
5. **External data hooks** — let agents pull live data during deliberation
   (market data APIs, analytics dashboards, CRM stats) rather than relying
   only on what's in the prompt or memory
