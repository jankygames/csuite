// topbar.jsx — shared top bar across Companies / Memory / Settings.
// One source of truth for the nav so links + active state stay consistent.
// Exports TopBar + CompanySwitcher to window for the other page scripts.

const { useState: _tbUseState, useEffect: _tbUseEffect } = React;

const NAV = [
  { key: 'companies', label: 'Companies', href: '/' },
  { key: 'memory',    label: 'Memory',    href: 'memory.html' },
  { key: 'settings',  label: 'Settings',  href: 'settings.html' },
];

function TopBar({ active, right = null }) {
  return (
    <header className="dash-topbar">
      <div className="dash-topbar-inner">
        <a className="brand" href="/" style={{ textDecoration: 'none' }}>
          <span className="brand-mark">C·S</span>
          <span className="brand-word">C-SUITE</span>
        </a>
        <nav className="top-nav">
          {NAV.map(n => (
            <a key={n.key}
               className={`top-nav-link${n.key === active ? ' active' : ''}`}
               href={n.href}>{n.label}</a>
          ))}
        </nav>
        <div className="topbar-right">
          <ThemeToggle />
          {right}
        </div>
      </div>
    </header>
  );
}

// One-click theme flip. Reads the current state from the document (set early
// by the inline boot script in each HTML head), writes the inverse to
// localStorage, and applies it. Persisted choice survives navigation and
// reloads; matches owner-app.jsx's tweak persistence so all three pages stay
// in sync without coupling them through a shared store.
function ThemeToggle() {
  // Track the current effective theme so the icon flips immediately.
  // 'light' / 'dark' — defaults to whatever the boot script set, or 'light'.
  const initial = (typeof document !== 'undefined' &&
    document.documentElement.dataset.theme) || 'light';
  const [theme, setTheme] = _tbUseState(initial);

  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('csuite-theme', next); } catch (e) {}
  };

  return (
    <button type="button" className="theme-toggle" onClick={flip}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}>
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  );
}

// Per-company switcher used on Memory + Settings. Reads/writes ?company=<id>
// so a chosen company survives reload and is shareable.
function CompanySwitcher({ companies, value, onChange }) {
  if (!companies || companies.length === 0) {
    return <span className="switcher-empty">No companies</span>;
  }
  return (
    <label className="company-switcher">
      <span className="switcher-label">Company</span>
      <select value={value || ''} onChange={e => onChange(e.target.value)}>
        {companies.map(c => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
      </select>
    </label>
  );
}

// Small helper: read/replace the ?company= param without a full SPA router.
function useCompanyParam(companies) {
  const param = new URLSearchParams(location.search).get('company');
  const ids = (companies || []).map(c => c.id);
  const initial = (param && ids.includes(param)) ? param : (ids[0] || '');
  const [company, setCompany] = _tbUseState(initial);

  // Once companies arrive, make sure we point at a real one.
  _tbUseEffect(() => {
    if (!company && ids.length) setCompany(ids[0]);
    else if (company && ids.length && !ids.includes(company)) setCompany(ids[0]);
  }, [companies]); // eslint-disable-line

  const choose = (id) => {
    setCompany(id);
    const u = new URL(location.href);
    u.searchParams.set('company', id);
    history.replaceState(null, '', u);
  };
  return [company, choose];
}

Object.assign(window, { TopBar, CompanySwitcher, useCompanyParam, ThemeToggle });
