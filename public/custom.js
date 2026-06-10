/* custom.js — progressive enhancement for the Chainlit chat.
   Served at /public/custom.js via config.toml:  custom_js = "/public/custom.js"

   Because Chainlit runs with unsafe_allow_html = false, Python can't emit chip
   or avatar HTML. So we do it on the client after Chainlit renders the markdown:

     1. Wrap status words (PROCEED / MODIFY / BLOCK / ESCALATE) in colored chips.
     2. Stamp a per-role monogram avatar next to each agent's author label.

   A MutationObserver re-runs the pass as new messages stream in. Everything is
   idempotent (guarded by data-cs-* flags) so re-processing is safe. */

(function () {
  // 0 ── theme: keep /chat and the dashboard in sync ──────────────────────────
  //
  // Two persisted keys are at play:
  //   csuite-theme   — written by the dashboard's toggle (source of truth)
  //   vite-ui-theme  — read by Chainlit's own theme provider (shadcn-ui default)
  //
  // If they disagree, the dashboard sees dark but Chainlit boots light and we
  // get light text on a light background. So on every load: copy csuite-theme
  // onto vite-ui-theme BEFORE Chainlit's module bundle runs, then apply
  // data-theme to <html> so our custom.css cascade also kicks in immediately.
  // custom.js is loaded with `defer` and appears earlier in the head than
  // Chainlit's `type="module"` bundle, so this runs first.
  function applyTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') return;
    try {
      document.documentElement.dataset.theme = theme;
      // Chainlit's theme provider reads this on boot AND watches it for changes
      // via window 'storage' events (only fires cross-tab) and its own state.
      localStorage.setItem('vite-ui-theme', theme);
    } catch (e) { /* localStorage blocked — best-effort only */ }
  }

  try {
    var savedTheme = localStorage.getItem('csuite-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      applyTheme(savedTheme);
    } else {
      // No dashboard preference yet — adopt whatever Chainlit had stored so
      // we don't surprise the user by overriding their chat-side choice.
      var chainlitTheme = localStorage.getItem('vite-ui-theme');
      if (chainlitTheme === 'light' || chainlitTheme === 'dark') {
        document.documentElement.dataset.theme = chainlitTheme;
      }
    }
  } catch (e) { /* localStorage blocked — fall through to OS preference */ }

  // Cross-tab sync: if the user toggles theme on the dashboard while chat is
  // open in another tab, mirror it here. Storage events only fire in *other*
  // tabs, which is exactly the cross-tab case we want.
  window.addEventListener('storage', function (e) {
    if (e.key === 'csuite-theme') {
      if (e.newValue === 'light' || e.newValue === 'dark') applyTheme(e.newValue);
    } else if (e.key === 'vite-ui-theme') {
      // Chainlit's own toggle changed in another tab — mirror to data-theme
      // so our custom.css tokens stay in agreement, and write back so the
      // dashboard tabs follow too.
      if (e.newValue === 'light' || e.newValue === 'dark') {
        document.documentElement.dataset.theme = e.newValue;
        try { localStorage.setItem('csuite-theme', e.newValue); } catch (_) {}
      }
    }
  });

  // Same-tab sync: when the user clicks Chainlit's own moon/sun toggle, it
  // writes vite-ui-theme but doesn't fire a storage event (those only fire
  // cross-tab). Chainlit's provider toggles class="dark" / class="light" on
  // <html>; watch for those and mirror to csuite-theme so dashboard tabs
  // follow on next visit.
  function currentTheme() {
    var el = document.documentElement;
    if (el.classList.contains('dark')) return 'dark';
    if (el.classList.contains('light')) return 'light';
    if (el.dataset.theme === 'dark' || el.dataset.theme === 'light') return el.dataset.theme;
    return '';
  }

  if (typeof MutationObserver !== 'undefined') {
    var lastSeen = currentTheme();
    var themeObserver = new MutationObserver(function () {
      var cur = currentTheme();
      if (cur === lastSeen || !cur) return;
      lastSeen = cur;
      try { localStorage.setItem('csuite-theme', cur); } catch (_) {}
      try { localStorage.setItem('vite-ui-theme', cur); } catch (_) {}
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'class'],
    });
  }

  // ── Per-tab title: pick up ?company=<id> so 4 open chats are readable ────
  // The dashboard links cards at /chat/?company=<id> (target="_blank"). Show
  // the company name in the tab title; otherwise every Chainlit tab says
  // "Assistant" and tab juggling is awful.
  try {
    var companyParam = new URLSearchParams(location.search).get('company');
    if (companyParam) {
      var pretty = companyParam.replace(/_/g, ' ').replace(/\b\w/g, function (c) {
        return c.toUpperCase();
      });
      document.title = pretty + ' · C-Suite';
    }
  } catch (e) { /* best effort — title stays "Assistant" if URL parsing fails */ }

  var STATUSES = ['PROCEED', 'MODIFY', 'BLOCK', 'ESCALATE'];
  var ROLES = ['CEO', 'CFO', 'COO', 'CMO', 'CTO', 'CCA'];

  // 1 ── status chips ────────────────────────────────────────────────────────
  // Chainlit renders **PROCEED** as <strong>PROCEED</strong>. Find those.
  function chipify(root) {
    var strongs = root.querySelectorAll('strong:not([data-cs])');
    strongs.forEach(function (el) {
      var word = (el.textContent || '').trim().toUpperCase();
      if (STATUSES.indexOf(word) === -1) return;
      el.setAttribute('data-cs', '1');
      el.classList.add('cs-chip');
      el.setAttribute('data-kind', word);
    });
  }

  // 2 ── monogram avatars ─────────────────────────────────────────────────────
  // Each agent message exposes its role via the author label text. We read it
  // and prepend a monogram if we haven't already.
  function avatarize(root) {
    // Author label selectors vary by Chainlit version; try a few.
    var labels = root.querySelectorAll(
      '.message-author:not([data-cs]), .step .name:not([data-cs]), [data-step] .name:not([data-cs])'
    );
    labels.forEach(function (el) {
      var text = (el.textContent || '').trim().toUpperCase();
      // Author may be "CFO — CHIEF FINANCIAL OFFICER"; take the leading token.
      var role = text.split(/[\s—-]/)[0];
      if (ROLES.indexOf(role) === -1) return;
      el.setAttribute('data-cs', '1');
      var av = document.createElement('span');
      av.className = 'cs-avatar';
      av.setAttribute('data-role', role);
      av.textContent = role;
      el.parentNode.insertBefore(av, el);
    });
  }

  function pass() {
    try {
      chipify(document.body);
      avatarize(document.body);
    } catch (e) { /* never break the chat */ }
  }

  // Initial pass once the app has painted, then observe for streamed messages.
  function boot() {
    pass();
    var obs = new MutationObserver(function () {
      // Debounce-ish: schedule a single pass per frame.
      if (boot._raf) return;
      boot._raf = requestAnimationFrame(function () {
        boot._raf = 0;
        pass();
      });
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
