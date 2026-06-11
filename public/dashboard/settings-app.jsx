// settings-app.jsx — Company Settings editor.
// Reads /api/settings/<id>, edits a local draft, PUTs changes back to config.json.
// Falls back to window.CSUITE_MOCK_SETTINGS when the API isn't reachable.

const { useState: stS, useEffect: stE } = React;

const RISK_OPTIONS = ['conservative', 'moderate', 'aggressive'];
const PERSONAS = [
  ['ceo', 'CEO'], ['cfo', 'CFO'], ['coo', 'COO'], ['cmo', 'CMO'], ['cto', 'CTO'],
];
// Mirror of the runtime defaults in core/agents/base.py — used as placeholders
// so the user knows what they'd get if they leave a field blank. NOT used to
// fill the saved config; blank fields are saved as the empty string so the
// runtime keeps falling back to its own defaults if the defaults move.
const MODEL_DEFAULTS = {
  model_provider: 'ollama',
  model_name:     'gpt-oss:20b',
  context_length: 32768,
};
const PROVIDER_OPTIONS = ['ollama', 'anthropic'];
const TUNABLE_LABELS = {
  chat_history_length: 'Chat history length',
  chat_message_cap:    'Chat message cap (chars)',
  cca_max_turns:       'CCA max turns / session',
  worker_max_tokens:   'Worker max output tokens',
  ceo_chat_max_tokens: 'CEO chat max tokens',
  knowledge_max_pct:   'knowledge.md max % of context',
  max_debate_rounds:   'Max debate rounds',
};

const clone = (o) => JSON.parse(JSON.stringify(o || {}));

// ── small controls ───────────────────────────────────────────────────────────
function Field({ label, span, children }) {
  return (
    <div className={`field${span ? ' span-2' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
    </div>
  );
}

function ListEdit({ items, onChange, placeholder }) {
  const arr = items || [];
  const set = (i, v) => { const n = arr.slice(); n[i] = v; onChange(n); };
  const del = (i) => onChange(arr.filter((_, j) => j !== i));
  const add = () => onChange([...arr, '']);
  return (
    <div className="list-edit">
      {arr.map((it, i) => (
        <div className="list-row" key={i}>
          <input type="text" value={it} placeholder={placeholder}
                 onChange={e => set(i, e.target.value)} />
          <button className="list-del" type="button" title="Remove" onClick={() => del(i)}>✕</button>
        </div>
      ))}
      <button className="list-add" type="button" onClick={add}>+ Add</button>
    </div>
  );
}

function Toggle({ on, onChange, label, sub }) {
  return (
    <div className="toggle-row">
      <div>
        <div className="tr-label">{label}</div>
        {sub && <div className="tr-sub">{sub}</div>}
      </div>
      <button type="button" className="switch" data-on={!!on} aria-pressed={!!on}
              onClick={() => onChange(!on)}><i /></button>
    </div>
  );
}

// ── app ───────────────────────────────────────────────────────────────────────
function SettingsApp() {
  const mock = window.CSUITE_MOCK_SETTINGS || { companies: [], byCompany: {} };
  // IMPORTANT: do NOT seed the dropdown from mock. If we do, useCompanyParam
  // picks a mock id on first render, which then hits /api/settings/<mockId>,
  // 404s, falls back to mock byCompany[mockId], and the page renders mock
  // data before the real /api/company-index response can swap things over.
  // Live API populates this below; mock is only used if the API is unreachable.
  const [companies, setCompanies] = stS([]);
  const [companyId, chooseCompany] = useCompanyParam(companies);
  const [meta, setMeta] = stS(null);     // { config, tunables, defaults, prompts }
  const [draft, setDraft] = stS(null);   // editable config copy
  // Prompts get their own state because they don't live in config.json —
  // they're written to prompts/<role>.md files. initialPrompts is the load-time
  // snapshot (used for source badges + diff-on-save); promptDraft holds the
  // currently-edited text per role.
  const [initialPrompts, setInitialPrompts] = stS({}); // { role: {content, source, path, size} }
  const [promptDraft, setPromptDraft] = stS({});       // { role: content }
  const [status, setStatus] = stS('clean'); // clean|dirty|saving|saved|error:<msg>
  const [loading, setLoading] = stS(true);

  stE(() => {
    fetch('/api/company-index')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        if (d.companies && d.companies.length) setCompanies(d.companies);
        // If the API responds successfully with 0 companies, we leave the
        // dropdown empty — that's the honest state.
      })
      .catch(() => {
        // API unreachable (opening the file directly, server down, etc.) —
        // fall back to mock companies so the page is at least navigable.
        if ((mock.companies || []).length) setCompanies(mock.companies);
      });
  }, []);

  stE(() => {
    if (!companyId) { setLoading(false); return; }
    let alive = true;
    setLoading(true); setStatus('clean');
    fetch(`/api/settings/${encodeURIComponent(companyId)}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        if (!alive) return;
        setMeta(d);
        setDraft(clone(d.config));
        const p = d.prompts || {};
        setInitialPrompts(p);
        const pd = {};
        PERSONAS.forEach(([k]) => { pd[k] = (p[k] && p[k].content) || ''; });
        setPromptDraft(pd);
        setLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        const m = mock.byCompany?.[companyId] || mock.fallback(companyId, companies);
        setMeta(m); setDraft(clone(m.config));
        const p = m.prompts || {};
        setInitialPrompts(p);
        const pd = {};
        PERSONAS.forEach(([k]) => { pd[k] = (p[k] && p[k].content) || ''; });
        setPromptDraft(pd);
        setLoading(false);
      });
    return () => { alive = false; };
  }, [companyId]);

  const set = (key, val) => { setDraft(d => ({ ...d, [key]: val })); setStatus('dirty'); };
  const setEsc = (key, val) => {
    setDraft(d => ({ ...d, escalation_rules: { ...(d.escalation_rules || {}), [key]: val } }));
    setStatus('dirty');
  };
  const setPersona = (role, val) => {
    setPromptDraft(p => ({ ...p, [role]: val }));
    setStatus('dirty');
  };

  const save = () => {
    setStatus('saving');
    // Diff prompts against load-time snapshot — send only what actually changed
    // so we don't materialize fallback content into new .md files by accident.
    const changedPrompts = {};
    Object.keys(promptDraft).forEach(role => {
      const initial = (initialPrompts[role] && initialPrompts[role].content) || '';
      if (promptDraft[role] !== initial) changedPrompts[role] = promptDraft[role];
    });
    const body = { config: draft };
    if (Object.keys(changedPrompts).length) body.prompts = changedPrompts;

    fetch(`/api/settings/${encodeURIComponent(companyId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(r => r.json().then(j => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (ok && j.ok) {
          setMeta(m => ({ ...m, config: j.config, prompts: j.prompts || (m && m.prompts) }));
          if (j.prompts) {
            setInitialPrompts(j.prompts);
            const pd = {};
            PERSONAS.forEach(([k]) => { pd[k] = (j.prompts[k] && j.prompts[k].content) || ''; });
            setPromptDraft(pd);
          }
          setStatus('saved');
        }
        else setStatus('error:' + (j.error || 'save failed'));
      })
      .catch(() => setStatus('error:API not reachable — run via server.py to persist'));
  };

  const right = <CompanySwitcher companies={companies} value={companyId} onChange={chooseCompany} />;
  const esc = (draft && draft.escalation_rules) || {};
  const tunables = (meta && meta.tunables) || {};
  const tunableKeys = Object.keys(tunables).sort();

  const statusText = {
    clean: 'All changes saved',
    dirty: 'Unsaved changes',
    saving: 'Saving…',
    saved: 'Saved ✓',
  };

  return (
    <div className="page-root">
      <TopBar active="settings" right={right} />
      <div className="page-canvas">
        <div className="page-hero">
          <div className="hero-meta">
            <MonoLabel dim>Company settings</MonoLabel>
            <MonoLabel dim>{companyId ? `config.json · ${companyId}` : ''}</MonoLabel>
          </div>
          <h1 className="page-title">{draft?.company_name || 'Settings'}<em>.</em></h1>
          <p className="page-lead">The company DNA the C-suite runs on — mission, guardrails, exec personalities, and engine tunables.</p>
        </div>

        {loading || !draft ? (
          <div className="page-loading">Loading settings…</div>
        ) : (
          <form className="settings-form" onSubmit={e => { e.preventDefault(); save(); }}>

            <fieldset className="fset">
              <legend className="fset-legend">Identity</legend>
              <div className="field-grid">
                <Field label="Company name"><input type="text" value={draft.company_name || ''} onChange={e => set('company_name', e.target.value)} /></Field>
                <Field label="Industry"><input type="text" value={draft.industry || ''} onChange={e => set('industry', e.target.value)} /></Field>
                <Field label="Stage"><input type="text" value={draft.stage || ''} onChange={e => set('stage', e.target.value)} /></Field>
                <Field label="Founded"><input type="text" value={draft.founded || ''} onChange={e => set('founded', e.target.value)} /></Field>
                <Field label="Team size"><input type="number" value={draft.team_size ?? ''} onChange={e => set('team_size', e.target.value === '' ? null : Number(e.target.value))} /></Field>
                <Field label="Runway"><input type="text" value={draft.runway || ''} onChange={e => set('runway', e.target.value)} /></Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Paths</legend>
              <p className="fset-hint">Where this company's workers read and write on disk. Leave blank to use the defaults.</p>
              <div className="field-grid cols-1">
                <Field label="Codebase path" span>
                  <input type="text" value={draft.codebase_path || ''}
                         placeholder="Absolute path — required for CCA (e.g. E:\MyCompanySite)"
                         onChange={e => set('codebase_path', e.target.value)} />
                </Field>
                <Field label="Documents path" span>
                  <input type="text" value={draft.documents_path || ''}
                         placeholder={`Blank = <COMPANY_ROOT>/${companyId || '<id>'}/documents/`}
                         onChange={e => set('documents_path', e.target.value)} />
                </Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Mission & strategy</legend>
              <div className="field-grid cols-1">
                <Field label="Mission" span>
                  <textarea rows={2} value={draft.mission || ''} onChange={e => set('mission', e.target.value)} />
                </Field>
                <Field label="Strategic priorities" span>
                  <ListEdit items={draft.strategic_priorities} placeholder="A priority…" onChange={v => set('strategic_priorities', v)} />
                </Field>
                <Field label="Constraints" span>
                  <ListEdit items={draft.constraints} placeholder="A constraint…" onChange={v => set('constraints', v)} />
                </Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Decision-making</legend>
              <div className="field-grid">
                <Field label="Risk profile">
                  <select value={draft.risk_profile || 'moderate'} onChange={e => set('risk_profile', e.target.value)}>
                    {RISK_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </Field>
                <Field label="Decision style"><input type="text" value={draft.decision_style || ''} onChange={e => set('decision_style', e.target.value)} /></Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Escalation rules</legend>
              <p className="fset-hint">When the C-suite must hand a decision up to you instead of deciding on its own.</p>
              <div className="field-grid cols-1">
                <Field label="Always escalate" span>
                  <ListEdit items={esc.always_escalate} placeholder="A trigger…" onChange={v => setEsc('always_escalate', v)} />
                </Field>
                <Toggle on={esc.escalate_if_deadlock} onChange={v => setEsc('escalate_if_deadlock', v)}
                        label="Escalate on deadlock" sub="If the exec team can't reach consensus, escalate to the owner." />
                <Field label="CEO can decide alone" span>
                  <ListEdit items={esc.ceo_can_decide_alone} placeholder="A delegated area…" onChange={v => setEsc('ceo_can_decide_alone', v)} />
                </Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Executive personalities</legend>
              <p className="fset-hint">Behavioral prompt for each agent. This is what the runtime actually loads at session start (<code>prompts/&lt;role&gt;.md</code>) — saving here writes that file.</p>
              <div className="field-grid cols-1">
                {PERSONAS.map(([key, label]) => {
                  const ip = initialPrompts[key] || { source: 'empty', content: '', size: 0 };
                  const draftVal = promptDraft[key] || '';
                  const isDirty = draftVal !== (ip.content || '');
                  let badge;
                  if (ip.source === 'file') {
                    badge = <><span className="persona-source-file">editing <code>{ip.path}</code></span> <span className="persona-source-meta">· {ip.size.toLocaleString()} chars</span></>;
                  } else if (ip.source === 'config_fallback') {
                    badge = <><span className="persona-source-fallback">no <code>{`prompts/${key}.md`}</code> yet</span> <span className="persona-source-meta">· showing config fallback; saving will create the file</span></>;
                  } else {
                    badge = <span className="persona-source-fallback">no prompt yet · saving will create <code>{`prompts/${key}.md`}</code></span>;
                  }
                  return (
                    <Field key={key} label={<span className="persona-label">{label}<span className="persona-badge" data-source={ip.source} data-dirty={isDirty}>{badge}{isDirty && <span className="persona-source-meta"> · unsaved</span>}</span></span>} span>
                      <textarea className="persona-textarea" rows={16} value={draftVal}
                                onChange={e => setPersona(key, e.target.value)}
                                placeholder={`Behavioral prompt for the ${label}…`} />
                    </Field>
                  );
                })}
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Model</legend>
              <p className="fset-hint">Inference backend for every agent. Defaults live in <code>core/agents/base.py</code>. Leave blank to inherit them.</p>
              <div className="field-grid">
                <Field label="Provider">
                  <select value={draft.model_provider || ''}
                          onChange={e => set('model_provider', e.target.value)}>
                    <option value="">(default · {MODEL_DEFAULTS.model_provider})</option>
                    {PROVIDER_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </Field>
                <Field label="Model name">
                  <input type="text" value={draft.model_name || ''}
                         placeholder={`default: ${MODEL_DEFAULTS.model_name}`}
                         onChange={e => set('model_name', e.target.value)} />
                </Field>
                <Field label="Context length">
                  <input type="number" value={draft.context_length ?? ''}
                         placeholder={`default: ${MODEL_DEFAULTS.context_length}`}
                         onChange={e => set('context_length', e.target.value === '' ? null : Number(e.target.value))} />
                </Field>
              </div>
            </fieldset>

            <fieldset className="fset">
              <legend className="fset-legend">Engine tunables</legend>
              <p className="fset-hint">Per-company overrides of the system defaults in <code>core/config.py</code>. Leave at default unless you have a reason.</p>
              <div>
                {tunableKeys.map(k => {
                  const t = tunables[k];
                  const val = (draft[k] !== undefined ? draft[k] : t.value);
                  const isOverridden = draft[k] !== undefined && draft[k] !== t.default;
                  return (
                    <div className="tunable-row" key={k}>
                      <div>
                        <div className="tunable-name">{TUNABLE_LABELS[k] || k}</div>
                        <div className="tunable-def">
                          default {t.default}{isOverridden && <span className="ovr"> · overridden</span>}
                        </div>
                      </div>
                      <input type="number" value={val}
                             onChange={e => set(k, e.target.value === '' ? t.default : Number(e.target.value))} />
                    </div>
                  );
                })}
              </div>
            </fieldset>

            <div className="save-bar">
              <span className={`save-status ${status.startsWith('error') ? 'error' : status === 'dirty' ? 'dirty' : status === 'saved' ? 'saved' : ''}`}>
                {status.startsWith('error') ? status.slice(6) : statusText[status]}
              </span>
              <span className="save-spacer" />
              <button type="submit" className="btn-primary" disabled={status === 'clean' || status === 'saving'}>
                {status === 'saving' ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<SettingsApp />);
