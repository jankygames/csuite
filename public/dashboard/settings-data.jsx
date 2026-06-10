// settings-data.jsx — mock company settings for offline / preview.
// The live /api/settings/<id> response (server.py) overrides this when reachable.

window.CSUITE_MOCK_SETTINGS = {
  companies: [
    { id: "meridian", name: "Meridian Robotics" },
    { id: "verge",    name: "Verge Health" },
    { id: "lattice",  name: "Lattice Climate" },
  ],

  defaults: {
    chat_history_length: 20,
    chat_message_cap: 10000,
    cca_max_turns: 50,
    worker_max_tokens: 4096,
    ceo_chat_max_tokens: 2048,
    knowledge_max_pct: 50,
    max_debate_rounds: 2,
  },

  byCompany: {
    meridian: {
      companyId: "meridian",
      config: {
        company_id: "meridian",
        company_name: "Meridian Robotics",
        industry: "Industrial robotics",
        stage: "Series A",
        founded: "2023",
        team_size: 14,
        runway: "9 mo",
        mission: "Replace warehouse picking labor with robots that learn from a single demonstration.",
        strategic_priorities: [
          "Ship pilot to first paying customer",
          "Reach $2M ARR by Q4",
          "Hold 99.5% pick accuracy in production",
        ],
        constraints: [
          "9 months runway at current burn",
          "Cannot pull CFO/CTO off the pilot for more than 2 weeks",
        ],
        risk_profile: "moderate",
        decision_style: "data-driven with bias toward action",
        escalation_rules: {
          always_escalate: [
            "Any change to founder equity or vesting",
            "Fundraise term sheets",
            "Spend over $25,000",
          ],
          escalate_if_deadlock: true,
          ceo_can_decide_alone: [
            "Tactical priorities within approved budget",
            "Agent task assignments",
          ],
        },
        agent_personalities: {
          ceo: "Decisive and synthesis-focused. Pushes for clarity, comfortable sitting with ambiguity only long enough to understand it.",
          cfo: "Conservative and data-driven. Asks about runway and unit economics first. Skeptical of growth that ignores margin.",
          coo: "Process-oriented. Asks how something gets done before why it should. Surfaces hidden dependencies.",
          cmo: "Customer-empathy-driven and brand-conscious. Advocates for distribution and reference value.",
          cto: "Pragmatic and reliability-focused. Prefers boring technology that works. Guards the pilot timeline.",
        },
        // tunable overrides at top level
        max_debate_rounds: 2,
        cca_max_turns: 50,
      },
      prompts: {
        // Mock preview: pretend ceo has a real .md file, others fall back to
        // config so we can see both badge states side by side.
        ceo: {
          content: "You are the CEO of Meridian Robotics. You synthesize the team's perspectives into clear, decisive calls.\n\nCORE IDENTITY:\nYou are a decisive operator who balances long-term vision with disciplined execution.\n\nDECISION-MAKING STYLE:\n- Be decisive with 70-80% information\n- Name disagreements specifically — \"there is some tension\" is not useful\n- Default to action over analysis paralysis\n",
          source: "file",
          path: "prompts/ceo.md",
          size: 380,
        },
        cfo: { content: "Conservative and data-driven. Asks about runway and unit economics first. Skeptical of growth that ignores margin.", source: "config_fallback", path: null, size: 120 },
        coo: { content: "Process-oriented. Asks how something gets done before why it should. Surfaces hidden dependencies.", source: "config_fallback", path: null, size: 100 },
        cmo: { content: "Customer-empathy-driven and brand-conscious. Advocates for distribution and reference value.", source: "config_fallback", path: null, size: 92 },
        cto: { content: "Pragmatic and reliability-focused. Prefers boring technology that works. Guards the pilot timeline.", source: "config_fallback", path: null, size: 100 },
      },
      tunables: {
        cca_max_turns:       { value: 50,    default: 50,    overridden: true },
        ceo_chat_max_tokens: { value: 2048,  default: 2048,  overridden: false },
        chat_history_length: { value: 20,    default: 20,    overridden: false },
        chat_message_cap:    { value: 10000, default: 10000, overridden: false },
        knowledge_max_pct:   { value: 50,    default: 50,    overridden: false },
        max_debate_rounds:   { value: 2,     default: 2,     overridden: true },
        worker_max_tokens:   { value: 4096,  default: 4096,  overridden: false },
      },
    },
  },
};

// Build a sensible blank settings payload for companies without mock detail.
window.CSUITE_MOCK_SETTINGS.fallback = function (id, companies) {
  const name = (companies.find(c => c.id === id) || {}).name || id;
  const d = window.CSUITE_MOCK_SETTINGS.defaults;
  const tunables = {};
  Object.keys(d).sort().forEach(k => { tunables[k] = { value: d[k], default: d[k], overridden: false }; });
  return {
    companyId: id,
    config: {
      company_id: id, company_name: name, industry: "—", stage: "—",
      founded: "", team_size: null, runway: "—", mission: "",
      strategic_priorities: [], constraints: [],
      risk_profile: "moderate", decision_style: "",
      escalation_rules: { always_escalate: [], escalate_if_deadlock: true, ceo_can_decide_alone: [] },
      agent_personalities: { ceo: "", cfo: "", coo: "", cmo: "", cto: "" },
    },
    prompts: {
      ceo: { content: "", source: "empty", path: null, size: 0 },
      cfo: { content: "", source: "empty", path: null, size: 0 },
      coo: { content: "", source: "empty", path: null, size: 0 },
      cmo: { content: "", source: "empty", path: null, size: 0 },
      cto: { content: "", source: "empty", path: null, size: 0 },
    },
    tunables,
    defaults: d,
  };
};
