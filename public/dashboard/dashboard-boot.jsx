// dashboard-boot.jsx — integration data loader.
// Fetches real company state from /api/companies (served by server.py), shapes
// it into what OwnerApp expects, and renders. Falls back to mock data if the
// API isn't reachable (e.g. opening the file directly), so the page never blanks.

(function () {
  // Owner + activity aren't in config.json today — supply sensible defaults.
  // Wire these to real sources later if you add an owner profile / event log.
  const OWNER = {
    name: "Owner",
    initials: "OW",
    greeting: () => {
      const h = new Date().getHours();
      if (h < 5)  return "Late night,";
      if (h < 12) return "Good morning,";
      if (h < 18) return "Good afternoon,";
      return "Good evening,";
    },
  };

  function deriveActivity(companies) {
    // Build a lightweight feed from whatever last-session data exists.
    return companies
      .filter(c => c.lastSession)
      .slice(0, 6)
      .map(c => ({
        company: c.id,
        text: c.lastSession.task,
        time: c.lastSession.time || "recently",
        kind: c.status === "pending" ? "escalate"
            : c.status === "deliberating" ? "progress"
            : "close",
      }));
  }

  function render(companies, ownerOverride, activityOverride) {
    window.CSUITE_COMPANIES = {
      COMPANIES: companies,
      OWNER: ownerOverride || OWNER,
      ACTIVITY: activityOverride || deriveActivity(companies),
    };
    window.dispatchEvent(new Event('csuite-data'));
  }

  // A mock may have been loaded before us (companies-data.jsx) so the page is
  // demo-able offline. Show it immediately, then hydrate from the live API.
  const mock = (window.CSUITE_COMPANIES && window.CSUITE_COMPANIES.COMPANIES) || [];
  const mockOwner = window.CSUITE_COMPANIES && window.CSUITE_COMPANIES.OWNER;
  const mockActivity = window.CSUITE_COMPANIES && window.CSUITE_COMPANIES.ACTIVITY;
  render(mock, mockOwner, mockActivity);

  fetch('/api/companies')
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => {
      const companies = (d.companies || []).map(c => ({
        ...c,
        statusLabel: c.statusLabel || ({
          pending: "Decision pending",
          deliberating: "Deliberating",
        }[c.status] || "Idle"),
      }));
      // Live API wins; OWNER/ACTIVITY fall back to defaults derived here.
      render(companies);
    })
    .catch(() => {
      // Offline / opened as a file — the mock already rendered above stands.
    });
})();
