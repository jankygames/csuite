// memory-data.jsx — mock institutional memory.
// Lets memory.html render offline / in preview. The live /api/memory/<id>
// response (served by server.py) overrides this whenever it's reachable.

window.CSUITE_MOCK_MEMORY = {
  companies: [
    { id: "meridian", name: "Meridian Robotics" },
    { id: "verge",    name: "Verge Health" },
    { id: "lattice",  name: "Lattice Climate" },
  ],

  byCompany: {
    meridian: {
      companyId: "meridian",
      companyName: "Meridian Robotics",
      knowledge: {
        exists: true,
        lastIndexedAt: "2026-06-01T18:22:00Z",
        indexedCount: 4,
        text: `## Decision Precedents

**Fundraising.** The owner has twice chosen brand and board access over a higher headline cap — the Honeywell pilot was accepted at a 60% discount for a 12-month logo lock-in (CMO override). Expect the same lean on the Tessera Series B: terms matter less than the introductions.

**Hiring sequencing.** Hiring a VP Engineering *before* the pilot ships was blocked on a COO objection. The owner consistently protects the pilot timeline from fundraise/hiring distractions.

## Owner Profile

- Values founder equity highly — **any** change to founder vesting escalates regardless of internal consensus (Company DNA rule #3).
- Tolerates dilution in exchange for strategic distribution; skeptical of growth that pulls the exec team off execution.
- Decides fast once a portfolio-conflict ("firewall") concern is resolved.

## Executive Dynamics

CFO and CTO converge on "modify, not block"; they disagree on *leverage* (the cap we can credibly counter to). COO and CMO are the recurring tension — process/retention cost vs. brand value. Deadlock here reliably triggers a CEO synthesis rather than a clean vote.

## Lessons Learned

Moving perception inference off-device was *modified* rather than adopted wholesale — kept edge inference, moved training only. The owner rewards proposals that preserve optionality.`,
      },
      stats: { decisions: 4, escalations: 1, overrides: 2, sessions: 6 },
      decisions: [
        {
          id: "d-117",
          task: "Accept the Series B term sheet from Tessera Ventures at a $48M cap with the founder-vesting reset clause?",
          outcome: "Escalated — pending owner decision",
          reasoning: "Genuine conflict between Christine and Dmitri on whether Tessera's brand clears the vesting-reset cost. Lean: $52M with a portfolio firewall and vesting carve-out to the last 12 months. No authority to accept a founder-vesting reset — escalating.",
          escalated: true,
          humanOverride: "",
          decidedAt: "2026-06-02T14:08:00Z",
          votes: [
            { agent: "CFO", recommendation: "MODIFY", confidence: 0.72, analysis: "Cap is 23% below the comparable median; counter at $58M, then $52M after Solene repriced the set.", concerns: ["Series C precedent risk", "9-month runway leaves no parallel process"] },
            { agent: "COO", recommendation: "BLOCK", confidence: 0.65, analysis: "Vesting reset costs 41 months of accrued founder time; fundraise pulls CFO+CTO off the pilot for 6 weeks.", concerns: ["Loaded replacement cost ≈ $1.4M", "No structural reason it can't wait a quarter"] },
            { agent: "CMO", recommendation: "PROCEED", confidence: 0.58, analysis: "Tessera's partner sits on the Honeywell and Mitsubishi boards; the introductions unlock stalled pilots.", concerns: ["Losing Tessera lowers brand value of next-best lead"] },
            { agent: "CTO", recommendation: "MODIFY", confidence: 0.80, analysis: "Clean on tech diligence. Atlas Forge is in Tessera's portfolio — a portfolio firewall is non-negotiable.", concerns: ["Information rights are a competitive leak without a firewall"] },
          ],
        },
        {
          id: "d-101",
          task: "Accept the Honeywell pilot at a 60% discount?",
          outcome: "Proceeded — CMO override, 12-month logo lock-in",
          reasoning: "Brand and reference value judged to outweigh the margin hit at this stage.",
          escalated: false,
          humanOverride: "Take it. The logo is worth more than the margin right now — revisit pricing at renewal.",
          decidedAt: "2026-04-18T11:30:00Z",
          votes: [
            { agent: "CFO", recommendation: "BLOCK", confidence: 0.7, analysis: "60% discount sets an anchor we'll fight at renewal.", concerns: ["Discount anchoring"] },
            { agent: "CMO", recommendation: "PROCEED", confidence: 0.82, analysis: "Reference logo accelerates every later enterprise conversation.", concerns: [] },
          ],
        },
        {
          id: "d-088",
          task: "Hire a VP Engineering before the pilot ships?",
          outcome: "Blocked — COO objection on sequencing",
          reasoning: "Onboarding a VP mid-pilot risks the timeline the whole quarter depends on.",
          escalated: false,
          humanOverride: "",
          decidedAt: "2026-03-02T09:15:00Z",
          votes: [
            { agent: "COO", recommendation: "BLOCK", confidence: 0.78, analysis: "Ramp time competes directly with the pilot ship date.", concerns: ["Timeline risk"] },
            { agent: "CTO", recommendation: "MODIFY", confidence: 0.6, analysis: "Contract a senior IC instead; defer the VP hire to post-pilot.", concerns: [] },
          ],
        },
      ],
      sessions: [
        { session_id: "s-06", started_at: "2026-06-02T14:00:00Z", ended_at: "", task_count: 1, outcome_summary: "Task: Tessera Series B term sheet | 2 rounds | escalated" },
        { session_id: "s-05", started_at: "2026-04-18T11:00:00Z", ended_at: "2026-04-18T11:40:00Z", task_count: 1, outcome_summary: "Task: Honeywell pilot pricing | resolved internally | human decision: take it" },
      ],
    },

    // A company with no distilled knowledge yet — demonstrates the empty state.
    verge: {
      companyId: "verge",
      companyName: "Verge Health",
      knowledge: { exists: false, lastIndexedAt: "", indexedCount: 0, text: "" },
      stats: { decisions: 1, escalations: 0, overrides: 0, sessions: 1 },
      decisions: [
        {
          id: "d-v1",
          task: "Submit the 510(k) on the lower-extremity model before the Atlas Health pilot closes?",
          outcome: "Deliberating — Round 1",
          reasoning: "",
          escalated: false,
          humanOverride: "",
          decidedAt: "2026-06-02T13:50:00Z",
          votes: [],
        },
      ],
      sessions: [
        { session_id: "s-v1", started_at: "2026-06-02T13:50:00Z", ended_at: "", task_count: 0, outcome_summary: "Task: 510(k) submission timing | in progress" },
      ],
    },

    lattice: {
      companyId: "lattice",
      companyName: "Lattice Climate",
      knowledge: { exists: false, lastIndexedAt: "", indexedCount: 0, text: "" },
      stats: { decisions: 0, escalations: 0, overrides: 0, sessions: 0 },
      decisions: [],
      sessions: [],
    },
  },
};
