// Atomic UI components for the C-Suite prototype.
// Visual language: editorial/terminal hybrid. Sans for prose, mono for structure.

const { useState, useEffect, useRef } = React;

// ---------- primitives ----------

function MonoLabel({ children, dim = false, style = {} }) {
  return (
    <span style={{
      fontFamily: 'var(--mono)',
      fontSize: '11px',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: dim ? 'var(--ink-3)' : 'var(--ink-2)',
      ...style,
    }}>{children}</span>
  );
}

function MonoRule({ char = '─', length = 70, color, style = {} }) {
  return (
    <div style={{
      fontFamily: 'var(--mono)',
      fontSize: '11px',
      color: color || 'var(--rule)',
      letterSpacing: 0,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      lineHeight: 1,
      ...style,
    }}>{char.repeat(length)}</div>
  );
}

// Status chip — small mono badge with hue. Body type stays neutral (DESIGN.md §9.6).
function StatusChip({ kind }) {
  const styles = {
    PROCEED:  { fg: 'oklch(0.38 0.10 145)', bg: 'oklch(0.96 0.04 145)', bd: 'oklch(0.85 0.07 145)' },
    MODIFY:   { fg: 'oklch(0.40 0.10 70)',  bg: 'oklch(0.96 0.05 75)',  bd: 'oklch(0.85 0.08 70)'  },
    BLOCK:    { fg: 'oklch(0.42 0.13 25)',  bg: 'oklch(0.96 0.04 25)',  bd: 'oklch(0.85 0.08 25)'  },
    ESCALATE: { fg: 'oklch(0.40 0.13 290)', bg: 'oklch(0.96 0.04 290)', bd: 'oklch(0.85 0.07 290)' },
  };
  const s = styles[kind] || styles.MODIFY;
  // Dark-mode shift: chips read on dark surface via lower-lightness bg.
  return (
    <span className="status-chip" data-kind={kind} style={{
      fontFamily: 'var(--mono)',
      fontSize: '11px',
      fontWeight: 600,
      letterSpacing: '0.1em',
      color: s.fg,
      background: s.bg,
      border: `1px solid ${s.bd}`,
      padding: '3px 8px 2px',
      borderRadius: '2px',
      textTransform: 'uppercase',
      lineHeight: 1.2,
      verticalAlign: '2px',
    }}>{kind}</span>
  );
}

// Agent monogram — initials + thin hue rule. Low chroma per DESIGN.md §9 (status > identity).
function AgentMonogram({ agent, size = 32 }) {
  const A = window.CSUITE_DATA.AGENTS[agent];
  const hue = A?.hue ?? 240;
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: '2px',
      background: `oklch(0.96 0.02 ${hue})`,
      border: `1px solid oklch(0.85 0.04 ${hue})`,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'var(--mono)',
      fontSize: size > 28 ? '12px' : '10px',
      fontWeight: 600,
      letterSpacing: '0.04em',
      color: `oklch(0.35 0.07 ${hue})`,
      flexShrink: 0,
    }}>{agent}</div>
  );
}

// ---------- session header ----------

function CompanyHeader({ company }) {
  return (
    <header className="company-header">
      <div className="company-meta-row">
        <a className="back-link" href="C-Suite Owner Dashboard.html">
          <span className="back-arrow">←</span>
          <MonoLabel dim>All companies</MonoLabel>
        </a>
        <MonoLabel dim>Session · Q2 2026 · deliberation #117 · 14:08 PST</MonoLabel>
      </div>
      <h1 className="company-name">{company.name}</h1>
      <p className="company-mission"><em>{company.mission}</em></p>
      <div className="company-priorities">
        {company.priorities.map((p, i) => (
          <span key={i} className="priority-pill">{p}</span>
        ))}
      </div>
      <MonoRule />
    </header>
  );
}

// ---------- task block ----------

function TaskBlock({ task, pastDecisions }) {
  return (
    <section className="task-block">
      <div className="task-author">
        <div className="owner-mark">YOU</div>
        <MonoLabel>Owner · just now</MonoLabel>
      </div>
      <p className="task-text">{task}</p>
      {pastDecisions?.length > 0 && (
        <details className="past-decisions">
          <summary>
            <MonoLabel>Relevant past decisions ({pastDecisions.length})</MonoLabel>
          </summary>
          <ul>
            {pastDecisions.map((d, i) => (
              <li key={i}>
                <span className="past-task">{d.task}</span>
                <span className="past-arrow">→</span>
                <span className="past-outcome">{d.outcome}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

// ---------- progress indicator ----------

function ProgressBar({ phaseLabel, current, total, currentAgent }) {
  const filled = '█'.repeat(current);
  const empty  = '░'.repeat(total - current);
  return (
    <div className="progress-row">
      <span className="progress-phase"><strong>{phaseLabel}</strong></span>
      <span className="progress-bar">[{filled}{empty}] {current}/{total}</span>
      {currentAgent && (
        <span className="progress-agent">— {currentAgent} is thinking<span className="dots"><span/><span/><span/></span></span>
      )}
    </div>
  );
}

// ---------- phase divider ----------

function PhaseHeader({ children, suffix }) {
  return (
    <div className="phase-header">
      <MonoRule length={70} />
      <h3>
        {children}
        {suffix && <><span className="phase-em">—</span>{suffix}</>}
      </h3>
    </div>
  );
}

// ---------- agent card ----------

function AgentCard({ entry, phase = "round1" }) {
  const A = window.CSUITE_DATA.AGENTS[entry.agent];
  const pct = Math.round(entry.confidence * 100);
  const suffix = phase === 'cross' ? ' (cross-response)' : '';
  return (
    <article className="agent-card" data-agent={entry.agent} style={{ '--agent-hue': A.hue }}>
      <header className="agent-card-head">
        <AgentMonogram agent={entry.agent} />
        <div className="agent-id">
          <h3 className="agent-title">{A.role} — {A.title}{suffix}</h3>
          <div className="agent-sub">
            <MonoLabel dim>{A.short}</MonoLabel>
          </div>
        </div>
        <div className="agent-rec">
          <StatusChip kind={entry.recommendation} />
          <span className="agent-conf">
            <span className="middot">·</span>
            <span className="conf-num">{pct}%</span>
            <span className="conf-word">confidence</span>
          </span>
        </div>
      </header>

      <p className="agent-analysis">{entry.analysis}</p>

      {entry.concerns?.length > 0 && (
        <div className="agent-concerns">
          <MonoLabel>Concerns</MonoLabel>
          <ul>
            {entry.concerns.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}

      {entry.references?.length > 0 && (
        <div className="agent-refs">
          <MonoLabel dim>Responding to</MonoLabel>
          {entry.references.map(r => <span key={r} className="ref-chip">{r}</span>)}
        </div>
      )}
    </article>
  );
}

// ---------- CEO synthesis ----------

function CEOSynthesisCard({ synthesis }) {
  return (
    <article className="synthesis-card">
      <header className="synthesis-head">
        <AgentMonogram agent="CEO" size={36} />
        <div className="agent-id">
          <h3 className="agent-title">CEO Synthesis <span className="phase-em">—</span> {synthesis.state}</h3>
          <MonoLabel dim>Alex Reyes</MonoLabel>
        </div>
        <StatusChip kind={synthesis.recommendation} />
      </header>
      <p className="synthesis-text">{synthesis.text}</p>
      {synthesis.reasoning && (
        <div className="synthesis-reasoning">
          <MonoLabel>Reasoning</MonoLabel>
          <p>{synthesis.reasoning}</p>
        </div>
      )}
    </article>
  );
}

// ---------- decision prompt ----------

function DecisionPrompt({ escalated, onChoose, onSubmit }) {
  const [mode, setMode] = useState(null); // 'override' | 'more-info' | null
  const [text, setText] = useState('');
  const [escDecision, setEscDecision] = useState('');
  const [escReason, setEscReason] = useState('');

  if (escalated) {
    return (
      <section className="decision-prompt escalated">
        <MonoRule />
        <div className="escalate-banner">
          <MonoLabel>Escalated — your decision is required.</MonoLabel>
        </div>
        <p className="decision-lead"><strong>Your response:</strong></p>
        <div className="esc-form">
          <label>
            <MonoLabel>Decision</MonoLabel>
            <input
              type="text"
              placeholder="e.g. accept with portfolio firewall; carve vesting to last 12 months only"
              value={escDecision}
              onChange={e => setEscDecision(e.target.value)}
            />
          </label>
          <label>
            <MonoLabel>Reasoning — this becomes institutional memory</MonoLabel>
            <textarea
              rows={3}
              placeholder="Why you decided this. Be specific; future sessions will read this back."
              value={escReason}
              onChange={e => setEscReason(e.target.value)}
            />
          </label>
          <div className="esc-actions">
            <button className="btn-primary" disabled={!escDecision.trim() || !escReason.trim()}
              onClick={() => onSubmit({ kind: 'escalate-decision', decision: escDecision, reason: escReason })}>
              Submit decision
            </button>
            <button className="btn-ghost" onClick={() => onChoose('more-info')}>Need more info</button>
          </div>
        </div>
      </section>
    );
  }

  if (mode === 'override' || mode === 'more-info') {
    const isOverride = mode === 'override';
    return (
      <section className="decision-prompt">
        <MonoRule />
        <p className="decision-lead"><strong>{isOverride ? 'Override' : 'More info'}</strong></p>
        <textarea
          rows={3}
          autoFocus
          placeholder={isOverride ? 'Reason for override (stored as institutional memory)' : 'What additional context should the C-suite consider?'}
          value={text}
          onChange={e => setText(e.target.value)}
        />
        <div className="esc-actions">
          <button className="btn-primary" disabled={!text.trim()}
            onClick={() => { onSubmit({ kind: mode, text }); setMode(null); setText(''); }}>
            {isOverride ? 'Override' : 'Resubmit'}
          </button>
          <button className="btn-ghost" onClick={() => setMode(null)}>Cancel</button>
        </div>
      </section>
    );
  }

  return (
    <section className="decision-prompt">
      <MonoRule />
      <p className="decision-lead"><strong>Your response:</strong></p>
      <ul className="decision-list">
        <li>
          <button onClick={() => onSubmit({ kind: 'approve' })}><strong>approve</strong></button>
          <span>— accept the recommendation (no implementation)</span>
        </li>
        <li>
          <button onClick={() => onSubmit({ kind: 'implement' })}><strong>implement</strong></button>
          <span>— approve and dispatch workers to execute</span>
        </li>
        <li>
          <button onClick={() => setMode('override')}><strong>override</strong> <em>reason</em></button>
          <span>— override with your decision</span>
        </li>
        <li>
          <button onClick={() => setMode('more-info')}><strong>more info</strong> <em>details</em></button>
          <span>— provide new information for reconsideration</span>
        </li>
      </ul>
    </section>
  );
}

// ---------- worker streaming card (CCA) ----------

function WorkerCard({ stream }) {
  return (
    <article className="agent-card worker-card" data-agent="CCA" style={{ '--agent-hue': 200 }}>
      <header className="agent-card-head">
        <AgentMonogram agent="CCA" />
        <div className="agent-id">
          <h3 className="agent-title">CCA — Claude Code Agent</h3>
          <MonoLabel dim>{stream.status === 'done' ? 'completed' : 'streaming…'}</MonoLabel>
        </div>
        {stream.status === 'done' && <StatusChip kind="PROCEED" />}
      </header>
      <div className="worker-stream">
        {stream.lines.map((l, i) => {
          if (l.type === 'text')     return <p key={i}>{l.body}</p>;
          if (l.type === 'tool_use') return <code key={i} className="tool-use">{l.body}</code>;
          if (l.type === 'result')   return <p key={i} className={l.is_error ? 'tool-err' : 'tool-ok'}>{l.is_error ? <><strong>Error:</strong> </> : null}{l.body}</p>;
          return null;
        })}
        {stream.status !== 'done' && <span className="caret"/>}
      </div>
      {stream.files?.length > 0 && (
        <div className="agent-concerns">
          <MonoLabel>Files changed</MonoLabel>
          <ul>
            {stream.files.map(f => <li key={f}><code>{f}</code></li>)}
          </ul>
        </div>
      )}
    </article>
  );
}

// ---------- left rail ----------

function SessionRail({ phase, agentsDone, totalAgents, currentAgent, density, company }) {
  const phaseOrder = ['idle', 'round1', 'cross', 'synthesis', 'decision', 'implement', 'done'];
  const phaseLabels = {
    idle: 'Awaiting task',
    round1: 'Round 1 — Independent',
    cross: 'Cross-response',
    synthesis: 'CEO Synthesis',
    decision: 'Decision pending',
    implement: 'Implementation',
    done: 'Closed',
  };
  return (
    <aside className="session-rail">
      <div className="rail-block">
        <MonoLabel dim>Company DNA</MonoLabel>
        <div className="rail-company">{company.name}</div>
        <div className="rail-sub">{company.stage}</div>
      </div>

      <div className="rail-block">
        <MonoLabel dim>Phase</MonoLabel>
        <ol className="rail-phases">
          {phaseOrder.slice(1).map(p => {
            const idx = phaseOrder.indexOf(p);
            const cur = phaseOrder.indexOf(phase);
            const state = idx < cur ? 'done' : idx === cur ? 'active' : 'idle';
            return (
              <li key={p} data-state={state}>
                <span className="phase-dot"/>
                <span className="phase-name">{phaseLabels[p]}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="rail-block">
        <MonoLabel dim>C-Suite</MonoLabel>
        <ul className="rail-roster">
          {['CFO','COO','CMO','CTO'].map(a => {
            const A = window.CSUITE_DATA.AGENTS[a];
            const done = agentsDone.includes(a);
            const active = currentAgent === a;
            return (
              <li key={a} data-active={active} data-done={done}>
                <AgentMonogram agent={a} size={22} />
                <span className="roster-name">{A.short}</span>
                <span className="roster-state">
                  {done ? '✓' : active ? <span className="dots"><span/><span/><span/></span> : '·'}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="rail-block rail-foot">
        <MonoLabel dim>Mode</MonoLabel>
        <div className="rail-mode">{density === 'compact' ? 'compact' : 'comfortable'}</div>
      </div>
    </aside>
  );
}

Object.assign(window, {
  MonoLabel, MonoRule, StatusChip, AgentMonogram,
  CompanyHeader, TaskBlock, ProgressBar, PhaseHeader,
  AgentCard, CEOSynthesisCard, DecisionPrompt, WorkerCard, SessionRail,
});
