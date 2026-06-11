# Installation & Setup Guide

Step-by-step instructions for setting up the Agentic C-Suite System on a
Windows machine with an NVIDIA GPU.

Throughout this guide, replace these placeholders with your actual paths:

| Placeholder | Description | Single-drive default | Multi-drive example |
|---|---|---|---|
| `{PROJECT}` | Project repo | `C:\Users\<you>\csuite` | `D:\csuite` |
| `{MODELS}` | Ollama model cache | `C:\Users\<you>\.ollama\models` (Ollama default) | `D:\models\ollama` |
| `{VENV}` | Python virtual environment | `C:\Users\<you>\.venvs\csuite` | `E:\venvs\csuite` |
| `{COMPANIES}` | Per-company state (configs, prompts, knowledge, **DB**, **logs**, documents — all collocated) | `C:\Users\<you>\.csuite\companies` (default; no env var needed) | `G:\csuite_data\companies` |

**Single-drive install:** ignore the multi-drive column. Put everything
on your C: drive (or whichever drive your home dir lives on). The defaults
take care of themselves.

**Multi-drive install (optional performance tuning):** use SSDs for
`{PROJECT}`, `{MODELS}`, `{VENV}` (fast read/write). To put the heavy
sequential writes (SQLite DBs, session logs) on a separate HDD, set the
optional `CSUITE_DATA_ROOT` and `CSUITE_LOG_ROOT` env vars — see Step 9.
Per-company `database_path` / `log_path` overrides in `config.json` win
over both.

---

## Prerequisites

| Component | Requirement |
|---|---|
| OS | Windows 10/11 |
| GPU | NVIDIA with 20+ GB VRAM (RTX 3090 recommended) |
| RAM | 32 GB minimum, 64 GB recommended |
| Storage | 40+ GB free on SSD for models and code |
| Python | **3.11.x** (not 3.12, not 3.13, not 3.14) |
| Node.js | Required for Claude Code CLI (CCA worker) |

---

## Step 1: NVIDIA Drivers

Make sure your NVIDIA drivers are installed and working:

```
nvidia-smi
```

You should see your GPU listed with driver version and VRAM. If this
command fails, install drivers from [nvidia.com/drivers](https://www.nvidia.com/drivers).

---

## Step 2: Install Python 3.11

Download Python 3.11 from [python.org](https://www.python.org/downloads/release/python-31111/).

During installation:
- Check "Add Python to PATH"
- Use the default install location or note where you install it

Verify:
```powershell
python --version
# Should show: Python 3.11.x
```

**Important:** The system requires Python 3.11 specifically. Python 3.14
has compatibility issues with the async stack (anyio, uvicorn, chainlit).
Python 3.12+ may work but is untested.

---

## Step 3: Create the Virtual Environment

```powershell
python -m venv {VENV}
{VENV}\Scripts\Activate.ps1
pip install --upgrade pip
```

---

## Step 4: Install Ollama

**Before installing Ollama**, set the model storage location so models
are stored on your SSD, not the default location:

1. Open **System Properties** → **Advanced** → **Environment Variables**
2. Add a new **System variable**:
   - Variable: `OLLAMA_MODELS`
   - Value: `{MODELS}`

Then install Ollama from [ollama.com](https://ollama.com).

Verify:
```bash
ollama --version
```

---

## Step 5: Pull Models

```bash
ollama pull gpt-oss:20b               # primary model (~12 GB)
ollama pull nomic-embed-text           # embedding model (~250 MB)
```

Verify both are available:
```bash
ollama list
```

You should see both models listed.

---

## Step 6: Clone the Repository

```powershell
git clone <your-repo-url> {PROJECT}
cd {PROJECT}
```

---

## Step 7: Install Python Dependencies

```powershell
# Make sure the venv is active
{VENV}\Scripts\Activate.ps1

cd {PROJECT}
pip install -r requirements.txt
```

This installs LangGraph, Chainlit, ChromaDB, and all other dependencies.

---

## Step 8: Install Claude Code CLI (for CCA Worker)

The Claude Code Agent (CCA) requires the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:
```bash
claude --version
```

**Note:** CCA is optional. The system works without it — you just won't be
able to dispatch code implementation tasks via the `implement` command.

---

## Step 9: (Optional) Override Data Path Environment Variables

**Skip this step on a single-drive install.** The defaults put everything
under `~/.csuite/companies/<id>/` — configs, SQLite DBs, knowledge, logs,
documents, all collocated. Nothing to configure.

If you want to override (e.g. put company configs somewhere other than
your home dir, or split heavy writes onto a separate HDD):

1. Open **System Properties** → **Advanced** → **Environment Variables**
2. Add any of these **System variables** — all three are optional:

| Variable | When to set it | What it does |
|---|---|---|
| `CSUITE_COMPANY_ROOT` | You want company configs somewhere other than `~/.csuite/companies` | Changes the discovery directory the dashboard scans. Everything else (DBs, logs, knowledge) collocates here by default. |
| `CSUITE_DATA_ROOT` | Multi-drive setup: SQLite DBs on a different volume | Global override: DBs land at `<DATA_ROOT>/<id>/<id>.db` instead of collocated. Companies can still override individually via `database_path` in `config.json`. |
| `CSUITE_LOG_ROOT` | Multi-drive setup: session logs on a different volume | Same shape as `CSUITE_DATA_ROOT`, but for logs. Companies can override via `log_path`. |

Per-company overrides (`database_path`, `log_path`, `codebase_path`,
`documents_path`) live in each company's `config.json` and are editable
in the Settings tab.

**Note:** You may need to restart your terminal or IDE after setting
environment variables.

---

## Step 10: Create Your First Company

```powershell
# Make sure venv is active
{VENV}\Scripts\Activate.ps1

cd {PROJECT}
python scripts/new_company.py --id my_company --name "My Company" --industry "Your Industry"
```

This creates (paths shown for a default single-drive install — DB and
logs land elsewhere if `CSUITE_DATA_ROOT` / `CSUITE_LOG_ROOT` are set):

- `{COMPANIES}/my_company/config.json` — company configuration
- `{COMPANIES}/my_company/prompts/*.md` — agent personality prompts
- `{COMPANIES}/my_company/chroma/` — vector store (starts empty)
- `{COMPANIES}/my_company/my_company.db` — SQLite database (collocated default)
- `{COMPANIES}/my_company/logs/` — log directory (collocated default)

---

## Step 11: Configure Your Company

### Edit config.json

Open `{COMPANIES}/my_company/config.json` and set:

- `mission` — one sentence describing the company's purpose
- `strategic_priorities` — current top priorities (list)
- `constraints` — hard limits the agents must respect (list)
- `risk_profile` — "conservative", "moderate", or "aggressive"
- `escalation_rules.always_escalate` — topics that always require your approval
- `codebase_path` — absolute path to your codebase (required for CCA worker; leave empty if not applicable)
- `documents_path` — *(optional)* where the non-code workers save artifacts. Default: `{COMPANIES}/my_company/documents/`.
- `database_path` — *(optional)* absolute path to this company's SQLite file. Default: collocated under `{COMPANIES}/my_company/` (or under `CSUITE_DATA_ROOT` if that env var is set).
- `log_path` — *(optional)* absolute path to this company's log directory. Default: collocated under `{COMPANIES}/my_company/` (or under `CSUITE_LOG_ROOT` if that env var is set).

You can also edit all of these later through the in-app **Settings** page —
the paths, the model config (`model_provider` / `model_name` / `context_length`),
escalation rules, and engine tunables all round-trip through `/api/settings/<id>`.

### Edit Agent Prompts

Each agent's personality is defined in a markdown file:

```
{COMPANIES}/my_company/prompts/
    ├── ceo.md
    ├── cfo.md
    ├── coo.md
    ├── cmo.md
    └── cto.md
```

The default prompts are functional but generic. For best results, customize
each prompt with:
- The agent's thinking frameworks and decision-making style
- Company-specific context and priorities
- Behavioral rules and communication style

See the `templates/prompts/` directory in the repo for the starter format.

---

## Step 12: Run the Application

```powershell
# Make sure venv is active
{VENV}\Scripts\Activate.ps1

cd {PROJECT}
uvicorn server:app --port 8000
```

`server.py` is a parent FastAPI app that serves the Owner Dashboard at `/`
and mounts the Chainlit chat at `/chat`. Open your browser to
`http://localhost:8000/`.

1. **Dashboard** — pick your company from the card grid
2. Click the card → you land in `/chat` with that company already loaded
3. Start chatting — the CEO responds conversationally
4. Say "should we..." to trigger a full C-suite deliberation
5. Say "draft...", "build...", "research..." to dispatch workers
6. Use the top nav (`Companies` / `Memory` / `Settings`) to switch surfaces.
   Memory is a read-only browse of `knowledge.md` + decision log; Settings
   is an editable view of the company's `config.json`.

**Legacy entry point:** `chainlit run app.py` still works for chat-only
use — but it skips the dashboard and shows the in-chat company picker
instead. `uvicorn server:app --port 8000` is the recommended command.

---

## Optional: Configure the .env File

If you plan to use the Anthropic API (Claude) instead of Ollama for
any company, add your API key to `{PROJECT}\.env`:

```
ANTHROPIC_API_KEY=your-key-here
```

Then set `"model_provider": "anthropic"` in that company's `config.json`.

---

## Verifying the Installation

Run these commands to verify everything is working:

```powershell
# 1. Check Python version
python --version
# Expected: Python 3.11.x

# 2. Check Ollama is running
ollama list
# Expected: gpt-oss:20b and nomic-embed-text listed

# 3. Check GPU
nvidia-smi
# Expected: GPU listed with driver info

# 4. Check core imports
cd {PROJECT}
python -c "from core.graph.session_graph import build_session_graph; print('OK')"
# Expected: OK

# 5. Check the server (dashboard + chat host) imports
python -c "import server; print('OK')"
# Expected: OK
# A failure here usually means missing FastAPI/uvicorn/chainlit — re-run:
#   pip install -r requirements.txt

# 6. Check Claude Code CLI (optional)
claude --version
# Expected: version number
```

---

## Troubleshooting

### "No module named 'core'"
Make sure you're running from the project root (`{PROJECT}`) with the
virtual environment activated.

### "ModuleNotFoundError: langgraph.checkpoint.sqlite"
Run: `pip install langgraph-checkpoint-sqlite`

### Chainlit crashes with "NoEventLoopError" or "AsyncLibraryNotFoundError"
You're likely running Python 3.14. Downgrade to Python 3.11 and rebuild
the venv.

### "Claude Code CLI not found"
Install it: `npm install -g @anthropic-ai/claude-code`
If installed but not found, CCA resolves the path from
`%APPDATA%\npm\claude.cmd` automatically.

### CCA errors with "Missing required field 'signature'"
This is a known compatibility issue between the Claude Code SDK and Ollama.
The system handles it gracefully — work completed before the error is
preserved, and the session remains usable.

### "No companies found" on startup
Make sure `CSUITE_COMPANY_ROOT` points to the right directory and you've
run `new_company.py` to create at least one company.

---

## Directory Reference

```
{PROJECT}\              ← project root (this repo)
{MODELS}\               ← Ollama model cache (OLLAMA_MODELS env var)
{VENV}\                 ← Python virtual environment

{COMPANIES}\            ← CSUITE_COMPANY_ROOT — per-company state, all collocated by default
    └── <company_id>\
        ├── config.json             ← company DNA
        ├── prompts\                ← agent personality prompts
        ├── knowledge.md            ← distilled memory (auto-generated)
        ├── knowledge_versions\     ← timestamped snapshots
        ├── chroma\                 ← ChromaDB fallback store
        ├── documents\              ← CWA/CRA/CSA artifacts (auto-created on first write)
        ├── <company_id>.db         ← SQLite database (override via database_path)
        └── logs\                   ← session logs (override via log_path)

# Optional global overrides — only used if the env vars are set:
<CSUITE_DATA_ROOT>\<id>\<id>.db     ← if CSUITE_DATA_ROOT is set
<CSUITE_LOG_ROOT>\<id>\sessions\    ← if CSUITE_LOG_ROOT is set

The `documents\` directory is created on first non-code worker run; you
don't need to make it manually.
```
