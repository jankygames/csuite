"""
core/graph/edges.py

Conditional edge functions for the session graph.

LangGraph conditional edges are plain Python functions that receive
the current state and return a string key. That key maps to the next
node name in the graph's routing table.

Currently defined edges:
    prior_decision_router  — routes after memory check (skip or deliberate)
    conflict_router        — routes after CEO synthesis based on consensus state
    human_decision_router  — routes after human response (approve/override/more info)
"""

def prior_decision_router(state: dict) -> str:
    """
    Called after prior_decision_check.

    If a closely matching prior decision was found, skip deliberation
    and go straight to presenting the prior decision to the human.
    Otherwise, proceed to full deliberation.
    """
    if state.get("prior_decision_found", False):
        return "already_decided"
    return "deliberate"


def conflict_router(state: dict) -> str:
    """
    Called after every ceo_synthesis node execution.

    Decision tree:
      1. Consensus reached → "resolved" → present recommendation to human
      2. No consensus, rounds remaining → "deadlocked" → loop back for round 2
      3. No consensus, rounds exhausted → "escalate" → present options to human

    The graph maps these string keys to node names:
        "resolved"   → present_recommendation
        "deadlocked" → round1_deliberation  (round 2 with CEO conflict framing)
        "escalate"   → present_recommendation (with escalate_to_human=True)
    """
    from core.config import get_tunable

    debate_round = state.get("debate_round", 1)
    config = state.get("company_config", {})
    max_rounds = get_tunable(config, "max_debate_rounds")

    if state.get("consensus_reached", False):
        return "resolved"

    if debate_round <= max_rounds:
        return "deadlocked"

    return "escalate"


def human_decision_router(state: dict) -> str:
    """
    Called after the human_interrupt node.

    If the human provides new information ("more info ..."), loops back
    to deliberation so the C-suite can reconsider with the new context.
    Otherwise, finalizes the session and writes to memory.

    The graph maps these string keys to node names:
        "finalize"    → memory_write → END
        "reconsider"  → reconsider_with_info → round1_deliberation
    """
    decision = (state.get("human_decision") or "").strip().lower()

    if decision.startswith("more info"):
        return "reconsider"

    return "finalize"
