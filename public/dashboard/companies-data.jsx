// Mock multi-company roster for the Owner Dashboard.

const COMPANIES = [
  {
    id: "meridian",
    name: "Meridian Robotics",
    mission: "Replace warehouse picking labor with robots that learn from a single demonstration.",
    stage: "Series A",
    runway: "9 mo",
    employees: 14,
    sector: "Industrial robotics",
    status: "pending",                // pending | deliberating | idle
    statusLabel: "Decision pending",
    lastSession: {
      task: "Accept Series B term sheet from Tessera at $48M cap with founder-vesting reset",
      time: "2 min ago",
      ceoRec: "ESCALATE",
      reason: "vesting reset changes founder equity. Your call.",
    },
    decisionsThisQuarter: 4,
    href: "C-Suite Deliberation.html",
  },
  {
    id: "verge",
    name: "Verge Health",
    mission: "Clinical-grade AI second opinions for radiology — read by the model, signed by the doctor.",
    stage: "Series B",
    runway: "22 mo",
    employees: 41,
    sector: "Clinical AI",
    status: "deliberating",
    statusLabel: "Deliberating · Round 1",
    lastSession: {
      task: "Submit 510(k) on the lower-extremity model before the Atlas Health pilot closes",
      time: "live",
      ceoRec: null,
    },
    decisionsThisQuarter: 11,
  },
  {
    id: "lattice",
    name: "Lattice Climate",
    mission: "Direct air capture at $40/ton by stacking solid-state sorbents in standard shipping containers.",
    stage: "Pre-seed",
    runway: "14 mo",
    employees: 3,
    sector: "Climate",
    status: "idle",
    statusLabel: "Idle",
    lastSession: {
      task: "Take the SOSV check or wait for the Lowercarbon partner intro",
      time: "Yesterday",
      ceoRec: "MODIFY",
    },
    decisionsThisQuarter: 2,
  },
  {
    id: "holm",
    name: "Holm Press",
    mission: "An independent book publisher built around translations of mid-century Nordic literature.",
    stage: "Bootstrapped",
    runway: "—",
    employees: 4,
    sector: "Publishing",
    status: "idle",
    statusLabel: "Idle",
    lastSession: {
      task: "Print run sizing for the Tarjei Vesaas reissue",
      time: "3 days ago",
      ceoRec: "PROCEED",
    },
    decisionsThisQuarter: 7,
  },
  {
    id: "strata",
    name: "Strata Foundry",
    mission: "Open-source RTL synthesis with first-class support for the analog/digital boundary.",
    stage: "Series A",
    runway: "17 mo",
    employees: 22,
    sector: "EDA / semis",
    status: "idle",
    statusLabel: "Idle · session closed 2h ago",
    lastSession: {
      task: "License the Cadence cell library or finish the open replacement first",
      time: "2h ago",
      ceoRec: "MODIFY",
    },
    decisionsThisQuarter: 9,
  },
  {
    id: "argosy",
    name: "Argosy Maritime",
    mission: "Autonomous wind-routing for small-fleet container shipping.",
    stage: "Seed",
    runway: "11 mo",
    employees: 8,
    sector: "Logistics",
    status: "idle",
    statusLabel: "Idle",
    lastSession: {
      task: "Pivot the simulator off Windward data after the contract dispute",
      time: "5 days ago",
      ceoRec: "PROCEED",
    },
    decisionsThisQuarter: 3,
  },
];

const OWNER = {
  name: "Alex Reyes",
  initials: "AR",
  greeting: () => {
    const h = new Date().getHours();
    if (h < 5)  return "Late night,";
    if (h < 12) return "Good morning,";
    if (h < 18) return "Good afternoon,";
    return "Good evening,";
  },
};

const ACTIVITY = [
  { company: "meridian", text: "CEO escalated to owner — vesting reset", time: "2 min ago", kind: "escalate" },
  { company: "verge",    text: "CFO submitted Round 1 — MODIFY at 71%",   time: "4 min ago", kind: "progress" },
  { company: "verge",    text: "Deliberation opened: 510(k) submission timing", time: "6 min ago", kind: "open" },
  { company: "strata",   text: "Owner approved CEO recommendation — MODIFY", time: "2h ago", kind: "close" },
  { company: "lattice",  text: "CCA drafted SOSV counter-terms", time: "Yesterday", kind: "worker" },
  { company: "holm",     text: "Session closed — print run set at 4,200", time: "3 days ago", kind: "close" },
];

window.CSUITE_COMPANIES = { COMPANIES, OWNER, ACTIVITY };
