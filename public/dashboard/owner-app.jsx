// Owner Dashboard — multi-company landing surface.
// Same visual system as the deliberation view (editorial/terminal hybrid).

const { useState, useEffect, useMemo } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "density": "comfortable",
  "view": "grid",
  "accent": "#3e4a8c"
}/*EDITMODE-END*/;

function OwnerApp() {
  // Hydrate theme/density from localStorage so navigating here from
  // Memory/Settings doesn't flip the page back to light. Without this,
  // useTweaks would start with TWEAK_DEFAULTS.theme = 'light' and the
  // useEffect below would override what the <head> boot script set.
  const initialTweaks = (() => {
    let theme   = TWEAK_DEFAULTS.theme;
    let density = TWEAK_DEFAULTS.density;
    try {
      const t = localStorage.getItem('csuite-theme');
      if (t === 'light' || t === 'dark') theme = t;
      const d = localStorage.getItem('csuite-density');
      if (d === 'compact' || d === 'comfortable') density = d;
    } catch (e) { /* localStorage blocked — fall back to defaults */ }
    return { ...TWEAK_DEFAULTS, theme, density };
  })();
  const [tweaks, setTweak] = useTweaks(initialTweaks);
  // Seed from whatever is present at mount; re-render when an async loader
  // (integration build, fetching /api/companies) dispatches 'csuite-data'.
  // In the standalone prototype the event never fires — mock data stands.
  const [data, setData] = useState(() => window.CSUITE_COMPANIES);
  useEffect(() => {
    const onData = () => setData({ ...window.CSUITE_COMPANIES });
    window.addEventListener('csuite-data', onData);
    return () => window.removeEventListener('csuite-data', onData);
  }, []);
  const { COMPANIES, OWNER, ACTIVITY } = data;
  const [q, setQ] = useState("");

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme   = tweaks.theme;
    root.dataset.density = tweaks.density;
    root.dataset.view    = tweaks.view;
    root.style.setProperty('--accent', tweaks.accent);
    // Persist so Memory + Settings pages pick up the same choice. The HTML
    // <head> script on each page reads these back before first paint.
    try {
      localStorage.setItem('csuite-theme', tweaks.theme);
      localStorage.setItem('csuite-density', tweaks.density);
    } catch (e) { /* localStorage unavailable — page-local only */ }
  }, [tweaks]);

  const pending = COMPANIES.filter(c => c.status === 'pending');
  const deliberating = COMPANIES.filter(c => c.status === 'deliberating');
  const others = COMPANIES.filter(c => c.status !== 'pending' && c.status !== 'deliberating');
  const filtered = (list) => list.filter(c =>
    !q.trim() || c.name.toLowerCase().includes(q.toLowerCase()) || (c.sector || '').toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="dash-root">
      {/* TOP BAR */}
      <header className="dash-topbar">
        <div className="dash-topbar-inner">
          <div className="brand">
            <span className="brand-mark">C·S</span>
            <span className="brand-word">C-SUITE</span>
          </div>
          <nav className="top-nav">
            <a className="top-nav-link active" href="/">Companies</a>
            <a className="top-nav-link" href="memory.html">Memory</a>
            <a className="top-nav-link" href="settings.html">Settings</a>
          </nav>
          <div className="owner-id">
            <ThemeToggle />
            <span className="owner-name">{OWNER.name}</span>
            <span className="owner-avatar">{OWNER.initials}</span>
          </div>
        </div>
      </header>

      <div className="dash-canvas">
        <div className="dash-main">
          {/* HERO */}
          <section className="dash-hero">
            <div className="hero-meta">
              <MonoLabel dim>{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</MonoLabel>
              <MonoLabel dim>{COMPANIES.length} companies · {pending.length + deliberating.length} active</MonoLabel>
            </div>
            <h1 className="hero-greeting">
              {OWNER.greeting()} <em>{OWNER.name.split(' ')[0]}.</em>
            </h1>
            <p className="hero-status">
              {pending.length > 0 && (
                <>
                  <strong>{pending.length} decision{pending.length > 1 ? 's' : ''}</strong> awaiting your call
                  {deliberating.length > 0 && <>; </>}
                </>
              )}
              {deliberating.length > 0 && (
                <><strong>{deliberating.length} deliberation{deliberating.length > 1 ? 's' : ''}</strong> in progress.</>
              )}
              {pending.length === 0 && deliberating.length === 0 && <>Everything's quiet.</>}
            </p>
          </section>

          {/* PENDING — featured row */}
          {pending.length > 0 && (
            <section className="dash-section">
              <header className="dash-section-head">
                <MonoLabel>Awaiting your decision</MonoLabel>
                <MonoRule />
              </header>
              {pending.map(c => <PendingCard key={c.id} company={c} />)}
            </section>
          )}

          {/* DELIBERATING */}
          {deliberating.length > 0 && (
            <section className="dash-section">
              <header className="dash-section-head">
                <MonoLabel>Deliberating now</MonoLabel>
                <MonoRule />
              </header>
              <div className={`companies-grid view-${tweaks.view}`}>
                {filtered(deliberating).map(c => <CompanyCard key={c.id} company={c} />)}
              </div>
            </section>
          )}

          {/* IDLE */}
          <section className="dash-section">
            <header className="dash-section-head">
              <MonoLabel>All companies</MonoLabel>
              <div className="section-tools">
                <input
                  className="dash-search"
                  placeholder="Search company or sector…"
                  value={q}
                  onChange={e => setQ(e.target.value)}
                />
                <button className="btn-ghost small">+ New company</button>
              </div>
            </header>
            <div className={`companies-grid view-${tweaks.view}`}>
              {filtered([...pending, ...deliberating, ...others]).map(c => (
                <CompanyCard key={c.id} company={c} />
              ))}
            </div>
          </section>

          <footer className="dash-foot">
            <MonoLabel dim>C-Suite · session 2026-Q2 · institutional memory healthy</MonoLabel>
          </footer>
        </div>

        {/* SIDEBAR */}
        <aside className="dash-side">
          <section className="side-block">
            <MonoLabel>Recent activity</MonoLabel>
            <ul className="activity-list">
              {ACTIVITY.map((a, i) => {
                const c = COMPANIES.find(x => x.id === a.company);
                return (
                  <li key={i} className="activity-item" data-kind={a.kind}>
                    <span className="activity-dot" />
                    <div className="activity-body">
                      <div className="activity-line">
                        <span className="activity-company">{c?.name}</span>
                        <span className="activity-time">{a.time}</span>
                      </div>
                      <div className="activity-text">{a.text}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="side-block">
            <MonoLabel>This quarter</MonoLabel>
            <dl className="vital-list">
              <div><dt>Sessions opened</dt><dd>36</dd></div>
              <div><dt>CEO escalations</dt><dd>5</dd></div>
              <div><dt>Owner overrides</dt><dd>2</dd></div>
              <div><dt>Implementations dispatched</dt><dd>19</dd></div>
            </dl>
          </section>

          <section className="side-block">
            <MonoLabel>Shortcuts</MonoLabel>
            <ul className="shortcuts">
              <li><kbd>G</kbd> <kbd>C</kbd> <span>Companies</span></li>
              <li><kbd>G</kbd> <kbd>M</kbd> <span>Memory</span></li>
              <li><kbd>N</kbd> <span>New deliberation</span></li>
              <li><kbd>/</kbd> <span>Search</span></li>
            </ul>
          </section>
        </aside>
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Surface">
          <TweakRadio label="Theme"   value={tweaks.theme}   options={['light','dark']}
                      onChange={v => setTweak('theme', v)} />
          <TweakRadio label="Density" value={tweaks.density} options={['comfortable','compact']}
                      onChange={v => setTweak('density', v)} />
          <TweakRadio label="View"    value={tweaks.view}    options={['grid','list']}
                      onChange={v => setTweak('view', v)} />
        </TweakSection>
        <TweakSection label="Accent">
          <TweakColor label="Brand accent" value={tweaks.accent}
                      options={['#3e4a8c', '#3a3a3a', '#5a6235', '#8a4a2e']}
                      onChange={v => setTweak('accent', v)} />
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

// ---------- Pending card (the featured row) ----------

function PendingCard({ company }) {
  // Wrap the card in a real <a target="_blank"> so the browser treats clicks as
  // a deliberate user navigation — no popup-blocker hassles, Cmd/Ctrl+click for
  // same-tab still works, and the URL param means each tab carries its own
  // company id (no shared pending-file race when opening several at once).
  return (
    <a href={`/chat/?company=${company.id}`}
       target="_blank"
       rel="noopener noreferrer"
       style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
    <article className="pending-card">
      <div className="pending-stripe" />
      <div className="pending-inner">
        <header className="pending-head">
          <div className="pending-id">
            <CompanyMark name={company.name} />
            <div>
              <h2 className="pending-name">{company.name}</h2>
              <div className="pending-stats">
                <span>{company.stage}</span>
                <span className="middot">·</span>
                <span>{company.runway} runway</span>
                <span className="middot">·</span>
                <span>{company.employees} ppl</span>
                <span className="middot">·</span>
                <span>{company.sector}</span>
              </div>
            </div>
          </div>
          <StatusChip kind="ESCALATE" />
        </header>

        <div className="pending-body">
          <MonoLabel dim>CEO synthesis</MonoLabel>
          <p className="pending-task">{company.lastSession?.task}</p>
          <p className="pending-rec">
            CEO recommends <strong>{company.lastSession?.ceoRec}</strong>{company.lastSession?.reason ? <> — {company.lastSession.reason}</> : <> — your decision is required.</>}
          </p>
        </div>

        <footer className="pending-foot">
          <MonoLabel dim>Escalated {company.lastSession?.time}</MonoLabel>
          <span className="open-cta">Convene & decide <span className="arrow">→</span></span>
        </footer>
      </div>
    </article>
    </a>
  );
}

// ---------- Regular company card ----------

function CompanyCard({ company }) {
  const last = company.lastSession;
  const recKind = last?.ceoRec;
  return (
    <a href={`/chat/?company=${company.id}`}
       target="_blank"
       rel="noopener noreferrer"
       style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
    <article className={`company-card status-${company.status}`}>
      <header className="card-head">
        <CompanyMark name={company.name} />
        <div className="card-id">
          <h3 className="card-name">{company.name}</h3>
          <p className="card-mission">{company.mission}</p>
        </div>
      </header>

      <div className="card-stats">
        <span>{company.stage}</span>
        {company.runway && company.runway !== '—' && <><span className="middot">·</span><span>{company.runway} runway</span></>}
        {company.employees != null && <><span className="middot">·</span><span>{company.employees} ppl</span></>}
      </div>

      <footer className="card-foot">
        <div className="card-status">
          <span className={`status-dot status-dot-${company.status}`} />
          <MonoLabel>{company.statusLabel}</MonoLabel>
        </div>
        {last && (
          <div className="card-last">
            <span className="last-task">{last.task}</span>
            <div className="last-meta">
              {recKind && <StatusChip kind={recKind} />}
              <span className="last-time">{last.time}</span>
            </div>
          </div>
        )}
      </footer>

      <span className="card-open">Open <span className="arrow">→</span></span>
    </article>
    </a>
  );
}

// ---------- Company mark (serif monogram) ----------

function CompanyMark({ name }) {
  // First letter of first two words, or first two letters.
  const parts = name.split(/\s+/);
  const letters = parts.length >= 2
    ? (parts[0][0] + parts[1][0])
    : name.slice(0, 2);
  // Stable hue from name hash.
  const hue = (name.charCodeAt(0) * 17 + name.charCodeAt(1) * 7) % 360;
  return (
    <div className="company-mark" style={{
      background: `oklch(0.96 0.02 ${hue})`,
      borderColor: `oklch(0.85 0.04 ${hue})`,
      color: `oklch(0.32 0.08 ${hue})`,
    }}>
      <span>{letters.toUpperCase()}</span>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<OwnerApp />);
