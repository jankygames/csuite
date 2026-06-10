// memory-app.jsx — Institutional Memory browser.
// Reads /api/company-index + /api/memory/<id> (server.py); falls back to
// window.CSUITE_MOCK_MEMORY when the API isn't reachable (offline / preview).

const { useState: useS, useEffect: useE, useMemo: useM } = React;

// ── tiny markdown renderer for knowledge.md ──────────────────────────────────
// Handles the subset the indexer emits: ## / ### headings, **bold**, "- " lists,
// "---" rules, and paragraphs. Not a general parser — intentionally small.
function renderInline(text, keyBase) {
  const out = [];
  // **bold** first, then *italic* — single regex with two alternatives.
  const re = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  let last = 0, m, i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] != null) out.push(<strong key={`${keyBase}-b${i++}`}>{m[1]}</strong>);
    else out.push(<em key={`${keyBase}-i${i++}`}>{m[2]}</em>);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Markdown({ text }) {
  const lines = (text || '').split('\n');
  const blocks = [];
  let para = [];
  let list = [];
  const flushPara = () => {
    if (para.length) { blocks.push({ t: 'p', body: para.join(' ') }); para = []; }
  };
  const flushList = () => {
    if (list.length) { blocks.push({ t: 'ul', items: list.slice() }); list = []; }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^##\s+/.test(line))      { flushPara(); flushList(); blocks.push({ t: 'h2', body: line.replace(/^##\s+/, '') }); }
    else if (/^###\s+/.test(line)){ flushPara(); flushList(); blocks.push({ t: 'h3', body: line.replace(/^###\s+/, '') }); }
    else if (/^---+\s*$/.test(line)) { flushPara(); flushList(); blocks.push({ t: 'hr' }); }
    else if (/^[-*]\s+/.test(line))  { flushPara(); list.push(line.replace(/^[-*]\s+/, '')); }
    else if (line === '')         { flushPara(); flushList(); }
    else                          { flushList(); para.push(line); }
  }
  flushPara(); flushList();

  return (
    <div className="knowledge-doc">
      {blocks.map((b, i) => {
        if (b.t === 'h2') return <h2 key={i}>{b.body}</h2>;
        if (b.t === 'h3') return <h3 key={i}>{renderInline(b.body, i)}</h3>;
        if (b.t === 'hr') return <hr key={i} />;
        if (b.t === 'ul') return <ul key={i}>{b.items.map((it, j) => <li key={j}>{renderInline(it, `${i}-${j}`)}</li>)}</ul>;
        return <p key={i}>{renderInline(b.body, i)}</p>;
      })}
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

const KNOWN_STATUS = ['PROCEED', 'MODIFY', 'BLOCK', 'ESCALATE'];

function DecisionItem({ d }) {
  return (
    <details className="dlog-item" data-escalated={d.escalated}>
      <summary className="dlog-summary">
        <span className="dlog-disc">▶</span>
        <span className="dlog-task">{d.task}</span>
        <span className="dlog-meta">
          {d.escalated && <StatusChip kind="ESCALATE" />}
          {d.humanOverride && <MonoLabel dim>override</MonoLabel>}
          <span className="dlog-date">{fmtDate(d.decidedAt)}</span>
        </span>
      </summary>
      <div className="dlog-body">
        {d.outcome && (
          <div className="dlog-field dlog-outcome">
            <span className="dlog-fl">Outcome</span>
            <p>{d.outcome}</p>
          </div>
        )}
        {d.reasoning && (
          <div className="dlog-field">
            <span className="dlog-fl">CEO reasoning</span>
            <p>{d.reasoning}</p>
          </div>
        )}
        {d.humanOverride && (
          <div className="dlog-field dlog-override">
            <span className="dlog-fl">Owner override — institutional memory</span>
            <p>{d.humanOverride}</p>
          </div>
        )}
        {d.votes && d.votes.length > 0 && (
          <div className="dlog-field">
            <span className="dlog-fl">Agent votes</span>
            <div className="vote-table">
              {d.votes.map((v, i) => (
                <div className="vote-row" key={i}>
                  <span className="vote-agent">{(v.agent || '').toUpperCase()}</span>
                  <span className="vote-meta">
                    {KNOWN_STATUS.includes((v.recommendation || '').toUpperCase())
                      ? <StatusChip kind={v.recommendation.toUpperCase()} />
                      : <MonoLabel>{v.recommendation || '—'}</MonoLabel>}
                    {v.confidence != null &&
                      <span className="vote-conf">{Math.round(v.confidence * 100)}%</span>}
                  </span>
                  <span className="vote-analysis">{v.analysis}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </details>
  );
}

function MemoryApp() {
  const mock = window.CSUITE_MOCK_MEMORY || { companies: [], byCompany: {} };
  // Start empty — don't seed from mock, or useCompanyParam picks a fake id
  // and the memory-loading effect renders mock data before the live company
  // list arrives. Mock only fills in when the API call below fails.
  const [companies, setCompanies] = useS([]);
  const [companyId, chooseCompany] = useCompanyParam(companies);
  const [data, setData] = useS(null);
  const [loading, setLoading] = useS(true);
  const [reindex, setReindex] = useS(null); // null | 'running' | 'done' | 'error:<msg>'

  // Company list — live API wins, mock fills in only if API is unreachable.
  useE(() => {
    fetch('/api/company-index')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { if (d.companies && d.companies.length) setCompanies(d.companies); })
      .catch(() => {
        if ((mock.companies || []).length) setCompanies(mock.companies);
      });
  }, []);

  // Memory payload for the chosen company.
  useE(() => {
    if (!companyId) { setData(null); setLoading(false); return; }
    let alive = true;
    setLoading(true);
    fetch(`/api/memory/${encodeURIComponent(companyId)}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { if (alive) { setData(d); setLoading(false); } })
      .catch(() => {
        if (!alive) return;
        setData(mock.byCompany?.[companyId] || emptyMemory(companyId, companies));
        setLoading(false);
      });
    return () => { alive = false; };
  }, [companyId]);

  const doReindex = () => {
    setReindex('running');
    fetch(`/api/reindex/${encodeURIComponent(companyId)}`, { method: 'POST' })
      .then(r => r.json().then(j => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (ok && j.ok) { setReindex('done'); setTimeout(() => location.reload(), 600); }
        else setReindex('error:' + (j.error || 'failed'));
      })
      .catch(() => setReindex('error:API not reachable (run via server.py)'));
  };

  const right = (
    <CompanySwitcher companies={companies} value={companyId} onChange={chooseCompany} />
  );

  const k = data?.knowledge;
  const stats = data?.stats || { decisions: 0, escalations: 0, overrides: 0, sessions: 0 };

  return (
    <div className="page-root">
      <TopBar active="memory" right={right} />
      <div className="page-canvas">
        <div className="page-hero">
          <div className="hero-meta">
            <MonoLabel dim>Institutional memory</MonoLabel>
            {k && <MonoLabel dim>{k.exists ? `Indexed ${k.indexedCount} decisions · ${fmtDate(k.lastIndexedAt)}` : 'Not yet distilled'}</MonoLabel>}
          </div>
          <h1 className="page-title">{data?.companyName || 'Memory'}<em>.</em></h1>
          <p className="page-lead">What the C-suite remembers — distilled knowledge, the decision log, and every owner override.</p>
        </div>

        {loading ? (
          <div className="page-loading">Loading memory…</div>
        ) : (
          <div className="page-cols">
            <div>
              <section className="page-section">
                <div className="page-section-head">
                  <MonoLabel>Distilled knowledge</MonoLabel>
                  <span className="mono-rule-fill" />
                  <button className="btn-ghost small" onClick={doReindex} disabled={reindex === 'running'}>
                    {reindex === 'running' ? 'Re-indexing…' : reindex === 'done' ? 'Done ✓' : 'Re-index'}
                  </button>
                </div>
                {reindex && reindex.startsWith('error:') &&
                  <p className="page-loading" style={{ paddingTop: 0, color: 'oklch(0.5 0.15 25)' }}>{reindex.slice(6)}</p>}
                {k && k.exists
                  ? <Markdown text={k.text} />
                  : (
                    <div className="knowledge-empty">
                      No distilled <code>knowledge.md</code> yet. It's generated from the decision
                      history once enough decisions accumulate — or run{' '}
                      <code>python -m core.memory.indexer --company {companyId} --force</code>{' '}
                      (or hit <em>Re-index</em> above).
                    </div>
                  )}
              </section>

              <section className="page-section">
                <div className="page-section-head">
                  <MonoLabel>Decision log</MonoLabel>
                  <span className="mono-rule-fill" />
                  <MonoLabel dim>{stats.decisions} total</MonoLabel>
                </div>
                {data?.decisions && data.decisions.length
                  ? <div className="decision-log">{data.decisions.map(d => <DecisionItem key={d.id} d={d} />)}</div>
                  : <div className="page-empty">No decisions recorded yet.</div>}
              </section>
            </div>

            <aside className="mem-side">
              <div className="stat-grid">
                <div className="stat-cell"><div className="stat-num">{stats.decisions}</div><div className="stat-lbl">Decisions</div></div>
                <div className="stat-cell"><div className="stat-num">{stats.sessions}</div><div className="stat-lbl">Sessions</div></div>
                <div className="stat-cell"><div className="stat-num">{stats.escalations}</div><div className="stat-lbl">Escalations</div></div>
                <div className="stat-cell"><div className="stat-num">{stats.overrides}</div><div className="stat-lbl">Owner overrides</div></div>
              </div>

              <div>
                <div className="page-section-head"><MonoLabel>Index status</MonoLabel><span className="mono-rule-fill" /></div>
                <dl className="index-card">
                  <div className="index-row"><dt>knowledge.md</dt><dd>{k?.exists ? 'present' : 'none'}</dd></div>
                  <div className="index-row"><dt>Last indexed</dt><dd>{fmtDate(k?.lastIndexedAt)}</dd></div>
                  <div className="index-row"><dt>Decisions at index</dt><dd>{k?.indexedCount ?? 0}</dd></div>
                  <div className="index-row"><dt>Decisions now</dt><dd>{stats.decisions}</dd></div>
                </dl>
              </div>

              {data?.sessions && data.sessions.length > 0 && (
                <div>
                  <div className="page-section-head"><MonoLabel>Recent sessions</MonoLabel><span className="mono-rule-fill" /></div>
                  <ul className="activity-list">
                    {data.sessions.slice(0, 6).map((s, i) => (
                      <li key={i} className="activity-item">
                        <span className="activity-dot" />
                        <div className="activity-body">
                          <div className="activity-line">
                            <span className="activity-company">{fmtDate(s.started_at)}</span>
                            <span className="activity-time">{s.ended_at ? 'closed' : 'open'}</span>
                          </div>
                          <div className="activity-text">{s.outcome_summary || '—'}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

function emptyMemory(id, companies) {
  const name = (companies.find(c => c.id === id) || {}).name || id;
  return {
    companyId: id, companyName: name,
    knowledge: { exists: false, lastIndexedAt: '', indexedCount: 0, text: '' },
    stats: { decisions: 0, escalations: 0, overrides: 0, sessions: 0 },
    decisions: [], sessions: [],
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(<MemoryApp />);
