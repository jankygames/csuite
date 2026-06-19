# csuite — Design System

This document describes the design language of the agentic C-suite system as
it actually exists in the repository today. It is descriptive first
(documenting what is already in the code) and prescriptive only where the
existing conventions imply a clear rule.

**Important context up front:** this is a Python/LangGraph backend with two
rendering surfaces — a Chainlit chat at `/chat` and a React owner dashboard
at `/`, both served by a parent FastAPI app ([server.py](server.py)). A
legacy CLI runner ([core/graph/runner.py](core/graph/runner.py)) also exists.

The design system has six load-bearing pieces:

1. The **structure of agent output** (JSON envelope + free-form analysis) —
   constrains what every visual surface can ever display.
2. The **rhythm and hierarchy of messages** rendered into Chainlit and the CLI.
3. The **voice and behavioral style** of each agent, defined in markdown
   prompt files.
4. The **terminology** the system uses to describe its own workflow
   (chat / deliberate / implement, round 1 / cross-response, etc.).
5. The **dashboard token system** in [public/dashboard/styles.css](public/dashboard/styles.css)
   `:root` — OKLCH palette, font stack (Instrument Serif / IBM Plex Sans /
   JetBrains Mono), spacing scale. Reuse the variables; never hard-code values.
6. The **chat-side enhancements** in [public/custom.css](public/custom.css) and
   [public/custom.js](public/custom.js) — port the dashboard tokens onto
   Chainlit's message DOM, wrap status words in colored chips, and stamp
   per-role monogram avatars.

Anything below labeled *gap* is an honest acknowledgement that no convention
currently exists.

---

## 1. Visual Layer

### 1.1 Rendering surfaces

The system has three output surfaces. They consume the same underlying agent
outputs but format them differently.

| Surface | Driver | File | Audience |
|---|---|---|---|
| Owner dashboard | React (Babel standalone) | [public/dashboard/](public/dashboard/) | Primary — companies list, memory browser, settings editor |
| Chainlit chat | `cl.Message`, markdown | [app.py](app.py) | Primary — the deliberation conversation |
| Terminal report | Plain-text ASCII frame | [core/agents/ceo.py](core/agents/ceo.py) — `format_presentation` | CLI runner (legacy / fallback) |

The dashboard is the front door (mounted at `/`); Chainlit is mounted at
`/chat`. A click on a dashboard card writes `.session/pending_company.json`
and 303-redirects to `/chat`, where the chat auto-loads that company.

### 1.2 Chainlit configuration

See [.chainlit/config.toml](.chainlit/config.toml).

- `name = "Assistant"` — no branded assistant name yet (*gap*)
- `default_theme` — not set; relies on Chainlit's default (light + dark)
- `layout` — not set; Chainlit default centered column
- `custom_css = "/public/custom.css"` — **set**. Ports the dashboard's
  OKLCH palette and font stack onto Chainlit's message DOM. See §1.3 / §1.4.
- `custom_js = "/public/custom.js"` — **set**. Adds two progressive
  enhancements at runtime: status chips on `**PROCEED/MODIFY/BLOCK/ESCALATE**`
  and per-role monogram avatars. See §1.5.
- `logo_file_url`, `default_avatar_file_url` — empty. Monograms in custom.js
  cover per-agent identity without raster assets (closing the avatar gap).
- `cot = "full"` — chain-of-thought is shown in full
- `alert_style = "classic"` — classic-style alerts
- `user_message_markdown = true` — user input is rendered as markdown
- `unsafe_allow_html = false` — Python emits markdown only; the chat-side
  chip and avatar HTML is added by custom.js after Chainlit renders.

Because Chainlit is mounted at `/chat`, it auto-rewrites the `custom_css` /
`custom_js` URLs in its own HTML head to `/chat/public/custom.css` and
`/chat/public/custom.js` — both files are visible to the browser at those
paths. (Probing `/public/custom.css` from the root will 404; that's not a
path the chat ever actually requests.)

### 1.3 Color

Defined as CSS custom properties in [public/dashboard/styles.css](public/dashboard/styles.css)
`:root` (full palette) and partially mirrored in [public/custom.css](public/custom.css)
(chat side). **All colors are OKLCH** — perceptually uniform, theme-able by
overriding a single hue value. **Never hard-code hex.**

**Warm-neutral light theme (default):**

| Token | Value | Used for |
|---|---|---|
| `--bg` | `oklch(0.985 0.005 80)` | Page background, composer |
| `--surface` | `oklch(0.995 0.004 80)` | Cards, rail, headers |
| `--surface-2` | `oklch(0.97 0.006 80)` | Worker stream block, code, ref chips |
| `--rule` | `oklch(0.88 0.008 80)` | Borders, dividers |
| `--rule-soft` | `oklch(0.93 0.006 80)` | Inner card borders |
| `--ink-1` | `oklch(0.18 0.008 60)` | Primary text, headings |
| `--ink-2` | `oklch(0.38 0.008 60)` | Secondary text, agent concerns |
| `--ink-3` | `oklch(0.58 0.008 60)` | Tertiary text, metadata |
| `--ink-4` | `oklch(0.72 0.006 60)` | Faintest text, separators |
| `--accent` | `oklch(0.42 0.10 270)` | Task block border, focus rings, progress bar |
| `--accent-soft` | `oklch(0.92 0.04 270)` | Focus glow, accent backgrounds |

**Dark theme** — same tokens, inverted lightness, activated by
`:root[data-theme="dark"]`.

**Accent presets** — `data-accent="indigo|graphite|olive|rust"` swaps a
single `--accent` value without touching the rest of the palette. The
attribute is read by the tweaks panel.

**Status colors** — three pairs, applied to status chips by custom.css.
All OKLCH, tuned at L≈0.40 for the text and L≈0.96 for the chip background:

| Status | Hue | Used at |
|---|---|---|
| `PROCEED` | `145` (green) | `.cs-chip[data-kind="PROCEED"]` |
| `MODIFY` | `70-75` (amber) | `.cs-chip[data-kind="MODIFY"]` |
| `BLOCK` | `25` (red) | `.cs-chip[data-kind="BLOCK"]` |
| `ESCALATE` | `290` (violet) | `.cs-chip[data-kind="ESCALATE"]` + `.escalate-banner` |

**Per-role monogram colors** — six pairs, applied to `.cs-avatar` by hue:

| Role | Hue | Tone |
|---|---|---|
| CEO | `270` | violet |
| CFO | `145` | green |
| COO | `60` | amber |
| CMO | `350` | rose |
| CTO | `220` | blue |
| CCA | `200` | teal |

**Rule for new color:** if you need a new state color, pick a hue at the
nearest free 30° step on the OKLCH wheel and reuse the L/C values from the
status table. Don't introduce hex.

**Rule for status-by-color:** color is *augmentation* of the existing text
labels (`**PROCEED**` etc.), not a replacement for them. The CLI report has
no color layer and must remain intelligible — every chip's hue is matched
by a word.

### 1.4 Typography

**Three-family stack**, loaded from Google Fonts. Used identically by the
dashboard and the chat (custom.css imports the same families).

| Family | Token | Role | Used at |
|---|---|---|---|
| **Instrument Serif** | `--serif` | Display, editorial moments | Company name (56px on dashboard, 40px on chat), CEO synthesis text (19px), company mission |
| **IBM Plex Sans** | `--sans` | Body, UI | Default body (15px / 1.55), agent titles, agent analysis, decision lead |
| **JetBrains Mono** | `--mono` | Labels, structure, code | Phase headers, progress bars, status chips, monogram avatars, ref chips, author labels |

**Type scale** (px):

| Size | Used for |
|---|---|
| 56 / 42 | Company name (dashboard / compact) |
| 40 | Company name (chat `## heading`) |
| 22 | Rail company label |
| 19 / 17 | Synthesis prose, company mission |
| 17 | Owner task text |
| 15 / 14 | Body, agent analysis |
| 14 | Agent title |
| 13.5 | Concerns, synthesis reasoning |
| 12 | Mono labels, progress row, agent recommendation row |
| 11 | Phase header tracking (`### ROUND 1 — INDEPENDENT ANALYSIS`), priority pills |
| 10 | Monogram avatars, ref chips |

**Font features:** `font-feature-settings: "ss01", "cv11"` is set on body.
Don't override unless you know why.

**Letter-spacing convention:** serif display is tightened (`-0.015em` on
company names); mono labels are loosened (`0.04em` to `0.14em` depending
on prominence). Sans body stays at `0em`.

**Density modes:** `data-density="compact"` on the root reduces padding
and several type sizes (e.g. 56→42 on company name). Same tokens, smaller.

**Markdown-to-type mapping** (in Chainlit messages, governed by custom.css):

| Markdown element | Renders as |
|---|---|
| `## Heading` | Serif 40px, company name on session start |
| `### Heading` | Sans 14px / 600 weight, phase / agent block titles |
| `**bold**` | Default bold — **except** for `PROCEED/MODIFY/BLOCK/ESCALATE`, which custom.js rewrites into `.cs-chip` (see §1.5) |
| `*italic*` | Default italic, used for the company mission line on startup |
| `` `code` `` | Mono 12px on `--surface-2`, used for file paths, tool calls |
| Triple-backtick | Default code block, used for error tracebacks |
| `---` hr | 1px `--rule` line, 1.2em vertical margin — phase boundary marker |
| `- ` bullet | Default markdown bullet — agent concerns, response options |

### 1.5 Iconography

No raster assets. No SVG file assets. Identity and status are communicated
through five channels:

1. **Unicode line-drawing characters** — used in the CLI report and as
   in-message dividers:
   - `=` — major divider (CLI report header / footer)
   - `─` (U+2500) — section divider (CLI and CEO synthesis messages)
   - `•` (U+2022) — bullet for concerns and conflicts
   - `█` (U+2588) and `░` (U+2591) — progress-bar fill / empty, used for
     "Analyzing [██░░] 2/4 — CFO is thinking..." in [app.py:233-237](app.py#L233-L237)
   - `▸` — collapsed disclosure marker (`.past-decisions summary::before`),
     rotates 90° on `[open]`

2. **Capitalized status words** — `PROCEED`, `BLOCK`, `MODIFY`, `ESCALATE`.
   In the chat these are upgraded by custom.js into colored chips (see §1.5.4).

3. **Author labels** — `CEO`, `CFO — Chief Financial Officer`, etc.
   (`AGENT_FULL_NAMES` in [app.py:1124](app.py#L1124)). Rendered by
   custom.css as mono 11px uppercase with 0.08em tracking.

4. **Status chips** (chat side only — added by [public/custom.js](public/custom.js)):
   custom.js scans for `<strong>PROCEED</strong>` etc. and rewrites them
   into `<span class="cs-chip" data-kind="PROCEED">`. Color comes from
   §1.3's status palette. Idempotent (guarded by `data-cs="1"` flag), so
   re-running is safe — important because Chainlit streams messages in.

5. **Monogram avatars** (chat side only — added by custom.js): a
   `<span class="cs-avatar" data-role="CFO">CFO</span>` is prepended to
   each agent's author label. Mono 10px, 26×26px square, OKLCH-tinted by
   role. The avatar text *is* the role abbreviation — no separate icon set.

   The dashboard has its own equivalent: `.owner-mark` for the owner's
   task block (28×28px square, mono 10px, `--accent` background, white
   text reading "OWNER"). Same pattern: text as iconography.

**No emoji** in agent-facing output. Keep every surface — chat, dashboard,
terminal, and the docs the workers write — emoji-free.

---

## 2. Layout Conventions

### 2.1 Chainlit message hierarchy

A deliberation session produces a sequence of messages in this order:

```
1.  Company header           ## {company_name} + mission + priorities
2.  Status / progress        "Analyzing [██░░] 2/4 — CFO is thinking..."  (updated in place)
3.  Phase header             ### Round 1 — Independent Analysis
4.  Agent output block       ### CFO — Chief Financial Officer
                             **PROCEED** · 78% confidence
                             {analysis}
                             **Concerns:**
                             - {concern}
                             - {concern}
5.  (more agent blocks)
6.  Phase header             ### Cross-Response — Peer Debate
7.  (cross-response blocks)
8.  CEO synthesis            ### CEO Synthesis — Consensus Reached
                             {synthesis text}
9.  Decision prompt          ---
                             **Your response:**
                             - **approve** — ...
                             - **implement** — ...
                             - **override** *reason* — ...
                             - **more info** *details* — ...
```

Each block is its own `cl.Message`. Messages have an `author` set to the
agent role (`"CEO"`, `"CFO"`, `"CCA"`, etc.), which Chainlit surfaces as a
labeled chip.

### 2.2 Agent output block — the core component

This is the single most-repeated visual unit in the system. Definition in
[app.py:1132-1150](app.py#L1132-L1150):

```
### {Full Agent Title}{ phase suffix if cross-response }

**{RECOMMENDATION}** · {confidence as percent}

{analysis paragraph}

**Concerns:**
- {concern 1}
- {concern 2}
```

Rules:
- The recommendation is uppercase and bold.
- Confidence is shown as a percentage with no decimals (`78%`, not `0.78` or `78.0%`).
- The separator between recommendation and confidence is `·` (U+00B7
  middle dot), not a hyphen or pipe.
- Concerns are omitted entirely when the list is empty — no "None" placeholder.
- The cross-response variant appends ` (cross-response)` to the heading
  rather than creating a different block layout.

### 2.3 CEO synthesis block

```
### CEO Synthesis — {Consensus Reached | Conflict Detected}

{synthesis paragraph}
```

The label after the em dash (`—`, U+2014) is a binary state, not free
text. Use exactly one of: `Consensus Reached` or `Conflict Detected`. The
synthesis itself is free-form prose; it must name specific executives
when describing agreement or disagreement (this is enforced by the CEO
prompt at [core/agents/ceo.py:371-381](core/agents/ceo.py#L371-L381)).

### 2.4 Decision prompt block

Always preceded by a `---` horizontal rule. The non-escalated form (app.py:366-373):

```
---

**Your response:**
- **approve** — accept the recommendation (no implementation)
- **implement** — approve and dispatch workers to execute (e.g. CCA writes code)
- **override** *reason* — override with your decision
- **more info** *details* — provide new information for reconsideration
```

The escalated form drops the four-option menu and asks for a free-form
decision + reasoning + instructions. Reasoning is explicitly framed as
"this becomes institutional memory" — that exact phrase is part of the
voice; it tells the user their override has weight.

### 2.5 Worker output block

Workers (CWA, CRA, CSA) stream their full output as the message body.
There is no JSON envelope and no concern list. After streaming completes,
non-streamed workers fall back to a short status block:

```
### {WORKER_NAME} — {completed | failed}

{summary}

**Files changed:**
- `path/to/file.py`
- `path/to/other.py`
```

CCA is special — it is an *interactive* worker. Its messages arrive in
three message types, each rendered differently
([app.py:1006-1025](app.py#L1006-L1025)):

| `msg.type` | Render |
|---|---|
| `text` | Plain message body, author `CCA` |
| `tool_use` | Wrapped in inline backticks: `` `{content}` `` |
| `result` | Plain text, or `**Error:** {content}` if `is_error` |

### 2.6 CLI report layout

The CLI variant in `CEOAgent.format_presentation`
([core/agents/ceo.py:139-246](core/agents/ceo.py#L139-L246)) is fixed-width
plain text, framed as a "report":

```
======================================================================
  C-SUITE DELIBERATION REPORT
  {company name}
======================================================================

TASK: {task}

──────────────────────────────────────────────────────────────────────
RELEVANT PAST DECISIONS
──────────────────────────────────────────────────────────────────────
  • {prior task}
    → {outcome}

──────────────────────────────────────────────────────────────────────
ROUND 1 — INDEPENDENT ANALYSIS
──────────────────────────────────────────────────────────────────────
[ CFO · PROCEED · 78% confidence ]
{analysis}
Concerns raised:
  • {concern}

(... cross-response section ...)

──────────────────────────────────────────────────────────────────────
CEO SYNTHESIS
──────────────────────────────────────────────────────────────────────
{synthesis}

──────────────────────────────────────────────────────────────────────
CEO RECOMMENDATION: PROCEED
──────────────────────────────────────────────────────────────────────
```

Conventions:
- Outer frame: `=` repeated 70 times.
- Section divider: `─` (U+2500) repeated 70 times.
- Section labels are UPPERCASE.
- The agent header is bracketed: `[ {AGENT} · {REC} · {CONF}% confidence ]`,
  using middle dot as separator, same as Chainlit.
- Indentation: 2 spaces for the report frame, 2 spaces + `•` for bullets,
  4 spaces for sub-content (the `→` outcome line).

### 2.7 Dividers and rhythm

The single horizontal rule (`---`) inside Chainlit messages serves as a
**phase boundary** within an otherwise continuous conversation. It is
used at three specific points:

1. Between the company-startup message and the rest of the session.
2. Before the decision prompt (`---\n\n**Your response:**`).
3. Before reconsideration messages after `more info`.

It is **not** used between every agent's output — agents are separated by
their `### heading` and the natural break of a new `cl.Message`.

### 2.8 Dashboard layout

The three dashboard pages (`/`, `/memory.html`, `/settings.html`) share
the same shell. Defined in [public/dashboard/styles.css](public/dashboard/styles.css).

**Shared shell:**

```
┌─────────────────────────────────────────────────────────┐
│  TOPBAR  · brand left · nav center · switcher right     │  ← topbar.jsx
├─────────────────────────────────────────────────────────┤
│                                                         │
│       Main column — max-width: var(--col-w) (720px)     │
│       padding: var(--pad-x) (28px) · centered           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Tokens that govern layout:**

| Token | Default | Purpose |
|---|---|---|
| `--col-w` | `720px` | Max content width on every page |
| `--rail-w` | `248px` | Session rail width (chat shell variant) |
| `--pad-x` | `28px` | Horizontal padding (18px in compact mode) |
| `--pad-y` | `24px` | Vertical padding (14px in compact mode) |
| `--radius` | `3px` | Card / chip / input corner radius |

**Page-specific bodies** ([public/dashboard/pages.css](public/dashboard/pages.css)):

- **`/` Companies dashboard** — responsive card grid; each card has serif
  display name, sans mission, mono priority pills, status chip in
  top-right, deep-link to `/enter/<id>`.
- **`/memory.html`** — main column = distilled `knowledge.md` (rendered)
  + decision log (`<details>` rows with vote tables); right rail = 2×2
  stat grid + index-status card + recent sessions list. Per-company
  `<select>` switcher in the topbar writes `?company=<id>` via
  `history.replaceState`.
- **`/settings.html`** — fieldsets (Identity, Mission & Strategy,
  Decision-making, Escalation rules, Executive personalities, Engine
  tunables). Sticky save bar at the bottom; status badge tracks
  `clean | dirty | saving | saved | error`.

**Responsive cutoff:** the session rail collapses below 920px; the main
column stays at full width.

**State persistence:** the only persisted client state is the `?company=<id>`
query param. No localStorage, no cookies, no service worker.

---

## 3. Component Patterns

Two layers of components:

- **Chat-side patterns** (sections 3.1–3.5) — message structures, not
  UI widgets. Anything an agent or the system says is wrapped in one of
  these patterns.
- **Dashboard-side patterns** (section 3.6) — real UI widgets defined in
  [public/dashboard/](public/dashboard/) and reused across the three pages.

### 3.1 Agent output card
Defined in §2.2. The single most-used pattern. Anything an executive
says about a decision is wrapped in this format.

### 3.2 Progress indicator
A single `cl.Message` that is updated in-place
([app.py:225-244](app.py#L225-L244)):
```
**{Analyzing | Cross-response | Synthesizing}** [██░░] 2/4 — {Agent Title} is thinking...
```
The text label tracks the phase. The bar has fixed total = 4 (four
deliberating agents — CEO is not in the bar). After each agent output
arrives, a *fresh* progress message is created below it rather than
mutating the original — this preserves a visible audit trail.

### 3.3 CEO synthesis card
Defined in §2.3.

### 3.4 Decision prompt
Defined in §2.4. The two variants (escalated / non-escalated) share a
preceding `---` and the bolded `**Your response:**` opener, but have
different bodies. Both end with an actionable verb list, never a question.

### 3.5 Worker output card
Defined in §2.5. Two flavors: streamed body (CWA-style) and
status-summary (CCA / fallback).

### 3.6 Dashboard widgets

| Component | Selector | Lives in | Used on |
|---|---|---|---|
| Topbar | `.topbar` | [topbar.jsx](public/dashboard/topbar.jsx) | All three pages |
| Company switcher | `.company-switcher` | [topbar.jsx](public/dashboard/topbar.jsx) | Memory + Settings |
| Company card | `.company-card` | [components.jsx](public/dashboard/components.jsx) | `/` |
| Status chip | `.status-chip[data-status=…]` | [components.jsx](public/dashboard/components.jsx) | Cards, decision log |
| Mono label | `.mono-label` | [components.jsx](public/dashboard/components.jsx) | Field labels, metadata rows |
| Priority pill | `.priority-pill` | [styles.css:341](public/dashboard/styles.css#L341) | Cards, settings (priorities list) |
| Vote table | `.vote-table` | [memory-app.jsx](public/dashboard/memory-app.jsx) | Memory decision-log rows |
| Editable string list | `.string-list-editor` | [settings-app.jsx](public/dashboard/settings-app.jsx) | Settings (priorities, constraints, escalation lists) |
| Tweaks panel | `.tweaks-panel` | [tweaks-panel.jsx](public/dashboard/tweaks-panel.jsx) | All pages — theme/accent/density toggles |
| Sticky save bar | `.save-bar[data-status=…]` | [settings-app.jsx](public/dashboard/settings-app.jsx) | Settings only |

**API-with-mock-fallback** is the pattern every page uses for data:
`fetch('/api/…')` first; on failure fall back to a `window.CSUITE_MOCK_*`
constant defined in the page's `*-data.jsx` file. This lets each page
render when opened as a static file or in a preview context. **Live API
always wins when reachable.**

**Markdown rendering** (Memory page): the distilled `knowledge.md` is
rendered by a small bespoke renderer (handles `## `, `### ` headings,
`**bold**`, `*italic*`, `- ` lists, `---`). Not a full markdown library —
intentionally minimal to keep the in-browser React bundle small.

---

## 4. Tone & Voice

The voice of this system is defined in two places:

1. **Per-agent personality** — short paragraphs in
   `templates/example_config.json` under `agent_personalities`.
2. **Per-agent behavioral style** — full markdown prompt files in
   [templates/prompts/](templates/prompts/).

The `.md` prompt is loaded if it exists; the `config.json` line is the
fallback. See CLAUDE.md decision #13.

### 4.1 Cross-agent voice principles

These appear, almost verbatim, across every agent prompt:

1. **Be specific.** "There is some tension" / "this is expensive" / "this
   will take a while" are explicitly called out as **unacceptable**.
   Quantify, name names, give numbers, give timelines.
2. **No corporate jargon.** Plain language. The CEO and CTO prompts both
   name "speak plainly" as a behavioral rule.
3. **Confidence is honest, not negotiated.** Each prompt ends with a
   rule like *"Your confidence score reflects {financial / execution /
   technical / customer-impact} certainty, not strategic agreement."*
   Confidence ≠ agreement. The system relies on this distinction.
4. **Own your position.** Especially the CEO: *"Do not hide behind 'the
   team decided.'"*
5. **Default to action.** "Champion shipping over perfecting" appears in
   COO and CTO. "Default to action over analysis paralysis" appears in
   CEO. Blocks are reserved for genuine harm.

### 4.2 Per-agent voice

| Role | Lens | Tonal hallmark | Default recommendation |
|---|---|---|---|
| CEO | Synthesis & decision | Decisive, direct, names disagreements specifically | Synthesizes; doesn't have a default |
| CFO | Cash flow & unit economics | Quantitative ("cash flow is reality. revenue is vanity"); skeptical of growth-at-all-costs | No default — leads with data |
| COO | Execution & capacity | Specific about timelines; "every yes is an implicit no" | **modify** (find the version that fits bandwidth) |
| CMO | Customer & brand | Advocate voice ("how does this look to a customer who just found us?") | **proceed** on initiatives that create customer value |
| CTO | Feasibility & reliability | Pragmatic, anti-hype, "choose boring technology" | **proceed** when straightforward; **modify** when scope > capacity |

### 4.3 CEO voice — special rules

The CEO is the only agent the human owner ever talks to directly. Two
rules apply uniquely to CEO output
([core/agents/ceo.py:371-385](core/agents/ceo.py#L371-L385)):

- When escalating, **never disguise a preference as objectivity.** If
  the CEO has a lean, label it as a lean.
- **Distinguish substantive conflict from positioning differences.**
  Two executives phrasing the same concern differently is not
  conflict. This is explicit because, without the rule, the system
  loops on rephrasings.

### 4.4 Conversational vs. deliberation voice

The CEO has two distinct modes:

| Mode | Trigger | Voice |
|---|---|---|
| **Deliberation synthesis** | "should we...", `deliberate` keywords | Structured JSON; names executives; arbitrates conflicts |
| **Chat** | Default | Natural conversation; no JSON, no `proceed/block/modify`. Explicitly instructed: *"Just talk like a knowledgeable executive having a conversation."* ([app.py:725](app.py#L725)) |

The chat-mode CEO is loaded with the full distilled knowledge document
and recent conversation history. It is meant to feel like a one-on-one
catch-up with a competent operator, not a chatbot.

---

## 5. Data Structures as Design

Two output schemas govern every agent message in the system. They are
described here because they constrain what the visual layer can ever
display.

### 5.1 Standard agent envelope ([core/agents/base.py:42-63](core/agents/base.py#L42-L63))

```json
{
  "analysis":       "<free-form natural language>",
  "recommendation": "proceed | block | modify",
  "concerns":       ["specific concern"],
  "confidence":     0.0
}
```

- `analysis` — unstructured. The only soft rule: be specific.
- `recommendation` — strict three-value enum.
- `concerns` — empty list is valid and renders as nothing in the UI.
- `confidence` — 0.0–1.0 float, displayed as `XX%`.

### 5.2 CEO envelope ([core/agents/ceo.py:39-69](core/agents/ceo.py#L39-L69))

```json
{
  "synthesis":      "<free-form>",
  "consensus":      true | false,
  "conflicts":      ["..."],
  "recommendation": "proceed | block | modify | escalate",
  "escalate":       true | false,
  "reasoning":      "<1-3 sentences>"
}
```

The CEO has a fourth recommendation value (`escalate`) and two boolean
flags. `consensus` and `escalate` are independent: a decision can have
consensus but still escalate (e.g. spending over $5k).

---

## 6. Naming & Terminology

The system uses a small, deliberate vocabulary. These terms have
specific meanings and should be used consistently in UI copy, prompts,
and documentation.

| Term | Meaning |
|---|---|
| **Chat** | The default conversational mode with the CEO. No deliberation. |
| **Deliberate** | The C-suite formally evaluates a decision. Triggered by "should we...". |
| **Implement** | Direct worker dispatch, no deliberation. Triggered by "implement / build / draft / do it". |
| **Round 1** | Independent analysis — agents have not seen each other's positions. |
| **Cross-response** | Agents read peers and respond to them by name. Not a full second round. |
| **Round 2** | A full second deliberation, only triggered when CEO finds unresolved conflict after cross-response. |
| **Consensus** | C-suite agrees on direction. Differences in *emphasis* are not conflict. |
| **Conflict** | Genuinely incompatible positions between named executives. |
| **Escalate** | Decision must go to the human. Triggered by deadlock OR by company escalation rules (always-escalate list). |
| **Override** | Human disagrees with CEO recommendation. Stored with reasoning as highest-signal memory. |
| **More info** | Human provides new context; deliberation reruns. |
| **C-suite** | The deliberation tier — CEO, CFO, COO, CMO, CTO. |
| **Worker** | The execution tier — CCA, CWA, CRA, CSA. |
| **Owner** | The human user. Always referred to as "owner" in agent prompts, not "user". |
| **Company DNA** | The `config.json` file. Set once, edited rarely. |
| **Institutional knowledge** | The distilled `knowledge.md` document — primary memory source. |

A small stylistic note: agent prompts address the human as **"owner"**
(e.g. CEO chat prompt: *"You are having a normal conversation with the
owner."*). UI strings address them as **"you"** (decision prompts say
*"Your response:"*, never *"Owner response:"*). Don't mix these.

---

## 7. Markdown Conventions

When generating new agent-facing or UI-facing messages, follow these
rules to stay consistent with what's already in the codebase:

- **`### heading`** for any in-message section (phase header, agent
  block heading, CEO synthesis label, worker output title). Do not use
  `##` inside a message — that level is reserved for the company name
  on session start.
- **`**bold**`** for: recommendations (`**PROCEED**`), action keywords
  in instructions (`**approve**`, `**reset**`, `**done**`), the leading
  label of a list section (`**Concerns:**`, `**Files changed:**`,
  `**Your response:**`).
- **`*italic*`** for: company mission (one-line context), soft emphasis
  inside a help string (`**override** *reason*`).
- **`` `code` ``** for: file paths in change lists, raw tool-call
  surfaces from CCA, the `gpt-oss:20b` model name and similar
  identifiers when they appear in user-facing text.
- **Triple-backtick fences** for: error tracebacks
  ([app.py:276](app.py#L276)). Not for normal output.
- **`---`** horizontal rule for phase boundaries inside a single thread,
  not between every message. See §2.7.
- **Bullets**: prefer `- ` over `* `. Single-space after the dash.
- **Em dash `—`** (U+2014) for "label — value" pairs in headings:
  `### CFO — Chief Financial Officer`, `### CEO Synthesis — Consensus Reached`.
- **Middle dot `·`** (U+00B7) for inline metadata separators:
  `**PROCEED** · 78% confidence`, `Acme Corp · 2h ago`.

Never use `>` blockquotes — they aren't used anywhere currently and
would read as inconsistent. Never use HTML —
`unsafe_allow_html = false` in Chainlit config.

---

## 8. Status & Signal

How the system communicates state. The Python side emits text only; chips
and avatars are added by custom.js after render. The CLI stays text-only
end-to-end.

| Signal | Mechanism (Python emits) | Chat enhancement (custom.js / custom.css) |
|---|---|---|
| Agent recommendation | `**PROCEED**` / `**BLOCK**` / `**MODIFY**` / `**ESCALATE**` | Rewritten into `.cs-chip[data-kind=…]` with status hue |
| Author label | `author="CFO"` on the message | Mono uppercase, prepended with `.cs-avatar[data-role="CFO"]` monogram |
| Confidence | `· 78% confidence` (middle dot, no decimals) | — |
| Consensus vs. conflict | Heading suffix: `— Consensus Reached` / `— Conflict Detected` | — |
| Progress | Live-updated unicode bar: `[██░░] 2/4 — CFO is thinking...` | — |
| Phase | `### Round 1 — Independent Analysis`, `### Cross-Response — Peer Debate`, `### CEO Synthesis — …`, `### Reconsideration — …` | — |
| Worker pass/fail | Heading suffix: `— completed` / `— failed`, plus `**Error:** {message}` body for fails | — |
| System state | Bare prose: `"Session reset. You can start fresh."`, `"Deliberation in progress…"` | — |
| Escalation trigger | Prepended block: `**Escalated — your decision is required.**` | (dashboard equivalent: `.escalate-banner` in violet hue 290) |

**Invariant:** every chip's hue must be matched by an existing text label.
If the chat-side enhancement fails to load, the chat still reads correctly
in plain markdown — chips are augmentation, not replacement.

**Tone for system messages:** short, declarative, no apologies.
"Session reset." not "I've reset your session for you!" — this matches
the system's overall voice of competent operator, not assistant.

---

## 9. Gaps & Opportunities

**Closed since the previous revision** (the dashboard install):

- ~~Brand palette~~ — OKLCH palette in [public/dashboard/styles.css](public/dashboard/styles.css) `:root`, mirrored in [public/custom.css](public/custom.css).
- ~~Status colors~~ — green/amber/red/violet chips for PROCEED/MODIFY/BLOCK/ESCALATE, applied via custom.js.
- ~~Per-agent visual identity~~ — monogram avatars per role, hue-tinted, applied via custom.js.
- ~~Custom CSS~~ — `public/custom.css` themes Chainlit's chat to match the dashboard.
- ~~Dashboard / multi-company surface~~ — `/` lists every company under `CSUITE_COMPANY_ROOT` as a card, with status, mission, priorities, and a deep-link into its chat session.

**Still open:**

1. **Logo / wordmark.** `logo_file_url` is empty in Chainlit config; the
   dashboard topbar uses a text mark. Neither is wrong, but there's no
   shared brand mark across both surfaces. Lowest-effort fix: a single
   monochrome SVG mounted at `/public/brand/mark.svg`, referenced from
   both `logo_file_url` and the dashboard topbar.
2. **Live card status writer.** The dashboard reads
   `companies/<id>/state.json` for card status (`idle` / `deliberating` /
   `pending`). The reader is wired up in [server.py:80-116](server.py#L80-L116);
   the *writer* — app.py emitting state.json on phase transitions — is
   not. Without it every card shows "Idle." See INTEGRATION-style snippet
   in [README.md](README.md#owner-dashboard).
3. **Dashboard dark mode toggle.** Tokens exist (`[data-theme="dark"]`),
   the tweaks panel can flip the attribute, but there's no persisted
   user preference yet — flipping refreshes back to light.
4. **Per-company brand overrides.** Each company has DNA in `config.json`;
   there's no `accent_hue` or `brand_mark` field that would let the
   dashboard tint a card to its company's color. Could be added cheaply
   since the palette is already hue-keyed.
5. **CCA result rendering.** Worker output for CCA is plain `.worker-stream`;
   tool calls render as inline code. A more structured rendering (file
   tree diff, per-tool collapsibles) would scale better for long sessions.

When extending the visual layer, the rule of thumb stays: **augment
text-as-status, never replace it.** The CLI report has no color layer and
must remain the source of truth.

---

## 10. Quick Reference

For anyone writing new UI strings or agent prompts:

- Use `###` headings inside messages.
- Recommendations are **bold uppercase** (`**PROCEED**` etc.) — the chat
  layer will upgrade them into chips automatically.
- Confidence is `XX%`, separated from rec by ` · ` (middle dot, not hyphen).
- Concerns: bulleted with `- `; omit the block entirely if empty.
- Address the user as "you" in UI, "owner" in prompts.
- No emoji.
- No color words in *prose* ("red flag", "green light") — even though
  chips exist, agent text should stand on its own. The chip is
  augmentation, not the channel.
- Be specific. "Some risk" / "a while" / "expensive" are the failure
  modes the prompts explicitly call out.
- One `---` rule between phases; not between every message.
- System messages: declarative, short, no apology.
- In CSS, always reuse `:root` tokens (`--ink-1`, `--accent`, etc.) — never
  hex. New status colors come from the OKLCH wheel at 30° hue steps.
- In custom.js, every DOM mutation must be idempotent (guard with
  `data-cs="1"`) because Chainlit streams messages in and the observer
  re-fires on every chunk.

That is the design system as it stands.
