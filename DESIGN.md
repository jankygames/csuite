# csuite — Design System

This document describes the design language of the agentic C-suite system as
it actually exists in the repository today. It is descriptive first
(documenting what is already in the code) and prescriptive only where the
existing conventions imply a clear rule.

**Important context up front:** this is a Python/LangGraph backend with a
Chainlit chat UI and a CLI runner. There is no custom HTML, CSS, JS, or asset
pipeline in the repository. There is no logo, brand palette, or icon set.
"Design," in this codebase, governs four things:

1. The **structure of agent output** (JSON envelope + free-form analysis).
2. The **rhythm and hierarchy of messages** rendered into Chainlit and the CLI.
3. The **voice and behavioral style** of each agent, defined in markdown
   prompt files.
4. The **terminology** the system uses to describe its own workflow
   (chat / deliberate / implement, round 1 / cross-response, etc.).

Anything below labeled *gap* or *not defined* is an honest acknowledgement
that no convention currently exists.

---

## 1. Visual Layer

### 1.1 Rendering surfaces

The system has two output surfaces. Both consume the same underlying agent
outputs but format them differently.

| Surface | Driver | File | Audience |
|---|---|---|---|
| Chainlit web UI | `cl.Message`, markdown | [app.py](app.py) | Primary — the human owner |
| Terminal report | Plain-text ASCII frame | [core/agents/ceo.py](core/agents/ceo.py) — `format_presentation` | CLI runner (legacy / fallback) |

The Chainlit UI is the primary interface; the CLI runner exists for
scripting and was the original entry point.

### 1.2 Chainlit configuration

The Chainlit UI runs at its defaults. See [.chainlit/config.toml](.chainlit/config.toml).

- `name = "Assistant"` — no branded assistant name yet (*gap*)
- `default_theme` — not set; relies on Chainlit's default (light + dark)
- `layout` — not set; Chainlit default centered column
- `custom_css` — not set (*gap* — no brand stylesheet)
- `custom_js` — not set
- `logo_file_url`, `default_avatar_file_url` — empty (*gap* — no logos or
  per-agent avatars)
- `cot = "full"` — chain-of-thought is shown in full
- `alert_style = "classic"` — classic-style alerts
- `user_message_markdown = true` — user input is rendered as markdown

There is no `public/` directory and no `custom.css` file in the repo. Any
visual tightening (typography overrides, palette, agent avatars, custom
sidebar) is a clean greenfield decision.

### 1.3 Color

**Not defined in the codebase.** Color is inherited from Chainlit's default
theme.

There is no palette declared in code, config, or assets. There are no
status colors (e.g. "block" rendered red, "proceed" rendered green) — every
status is communicated by **text label only** (`PROCEED`, `BLOCK`, `MODIFY`,
`ESCALATE`).

The CEO's `_apply_escalation_rules` function distinguishes outcomes only by
keyword, not by any styling layer.

### 1.4 Typography

**Inherited from Chainlit defaults.** No custom font stack.

In-message typography is governed entirely by markdown. The conventions in
use (observed across [app.py](app.py) and [core/agents/ceo.py](core/agents/ceo.py)):

| Markdown element | Used for |
|---|---|
| `### Heading` | Phase header within a deliberation (e.g. `### Round 1 — Independent Analysis`, `### CEO Synthesis — Consensus Reached`) |
| `## Heading` | Company name on session start (`## {company_name}`) |
| `**bold**` | Recommendation badges, action labels, status words (`**PROCEED**`, `**reset**`, `**approve**`) |
| `*italic*` | Company mission line on startup, soft emphasis |
| `` `code` `` | File paths, raw tokens, tool-call surfaces (e.g. CCA `tool_use` messages) |
| Triple-backtick block | Error tracebacks |
| `---` horizontal rule | Phase boundaries within a single conversation thread |
| Bullet `- ` | Concerns, strategic priorities, response option menus |

### 1.5 Iconography

There are no SVG or image icons. The repository communicates status
purely through three channels:

1. **Unicode line-drawing characters**, used in the CLI report and as
   in-message dividers:
   - `=` — major divider (CLI report header / footer)
   - `─` (U+2500) — section divider (used both in CLI and in CEO synthesis
     messages as `─ * 70`)
   - `•` (U+2022) — bullet for concerns and conflicts
   - `█` (U+2588) and `░` (U+2591) — progress-bar fill / empty, used for the
     "Analyzing [██░░] 2/4 — CFO is thinking..." live indicator in
     [app.py](app.py:233-237)
2. **Capitalized status words**: `PROCEED`, `BLOCK`, `MODIFY`, `ESCALATE`.
3. **Author labels** on Chainlit messages: `CEO`, `CCA`, `CFO — Chief
   Financial Officer`, etc. (see `AGENT_FULL_NAMES` in [app.py:1124](app.py#L1124))

There is **no emoji usage** anywhere in agent-facing output. The
auto-generated `chainlit.md` welcome file contains a few emoji, but it is
a Chainlit boilerplate file and is the only one. Keep agent-facing
surfaces emoji-free.

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

---

## 3. Component Patterns

The repeating "components" in this system are conceptual rather than
visual — they are message structures, not UI widgets. The five
load-bearing ones:

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

How the system communicates state today (all text-based; no color, no
icons):

| Signal | Mechanism |
|---|---|
| Agent recommendation | Bold uppercase word: `**PROCEED**`, `**BLOCK**`, `**MODIFY**`, `**ESCALATE**` |
| Confidence | Percentage to 0 decimals after a middle dot: `· 78% confidence` |
| Consensus vs. conflict | CEO heading suffix: `— Consensus Reached` / `— Conflict Detected` |
| Progress | Live-updated unicode bar: `[██░░] 2/4 — CFO is thinking...` |
| Phase | `### Round 1 — Independent Analysis`, `### Cross-Response — Peer Debate`, `### CEO Synthesis — ...`, `### Reconsideration — Independent Analysis` |
| Worker pass/fail | Heading suffix: `— completed` / `— failed`, plus `**Error:** {message}` body for fails |
| System state | Bare prose messages: `"Session reset. You can start fresh."`, `"Deliberation in progress. Please wait..."` |
| Escalation trigger | Prepended block: `**Escalated — your decision is required.**` |

**Tone for system messages:** short, declarative, no apologies.
"Session reset." not "I've reset your session for you!" — this matches
the system's overall voice of competent operator, not assistant.

---

## 9. Gaps & Opportunities

Where no convention exists today:

1. **Brand palette.** Nothing in repo. If a palette is introduced, the
   recommendation is to use *text-as-status* primarily and reserve
   color for low-frequency emphasis (recommendation badges, error
   banners), never as the sole signal — the CLI report must stay
   intelligible.
2. **Agent avatars.** No images. `default_avatar_file_url` is empty.
   Each agent already has a stable role string (`cfo`, `cca`, etc.)
   that could be mapped to an avatar asset.
3. **Logo.** None. `logo_file_url` is empty.
4. **Custom CSS.** None. Chainlit's `custom_css` slot is available but
   no `public/` directory exists.
5. **Dashboard / multi-company surface.** Marked unbuilt in CLAUDE.md.
   No layout exists yet.
6. **Status colors.** Recommendation values render in plain bold today.
   If introduced, they should match: proceed = positive, modify =
   neutral attention, block = negative, escalate = high-attention but
   distinct from block.
7. **Per-agent visual identity.** Each agent has voice and a role label
   but no visual treatment beyond the author chip Chainlit provides.

When extending the system, the recommended order is: lock typography
and palette first, then introduce per-agent avatars (they are the
highest-bang-for-buck visual), then build out the dashboard. Don't
introduce color-as-status without keeping the existing text labels — the
CLI report must remain the source of truth.

---

## 10. Quick Reference

For anyone writing new UI strings or agent prompts:

- Use `###` headings inside messages.
- Recommendations are **bold uppercase**.
- Confidence is `XX%`, separated from rec by ` · `.
- Concerns: bulleted with `- `; omit the block entirely if empty.
- Address the user as "you" in UI, "owner" in prompts.
- No emoji.
- No color words ("red flag", "green light") — they imply visuals that
  don't exist.
- Be specific. "Some risk" / "a while" / "expensive" are the failure
  modes the prompts explicitly call out.
- One `---` rule between phases; not between every message.
- System messages: declarative, short, no apology.

That is the design system as it stands.
