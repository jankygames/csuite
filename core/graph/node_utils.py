"""
core/graph/node_utils.py

Shared utilities used across all graph node modules.
Includes the progress callback system, logging, and briefing builder.
"""

from datetime import datetime, timezone
from typing import Callable, Optional


# ── Progress callback ────────────────────────────────────────────────────────

_progress_callback: Optional[Callable] = None


def set_progress_callback(cb: Optional[Callable]) -> None:
    global _progress_callback
    _progress_callback = cb


def _notify(event: str, **data) -> None:
    """
    Notify the UI layer of progress events.
    Events:
        agent_start    — an agent is about to run
        agent_complete — an agent finished, includes full output dict
    """
    if _progress_callback:
        _progress_callback(event, data)


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  {ts}  {msg}")


# ── Briefing builder ────────────────────────────────────────────────────────

def build_agent_briefing(
    state: dict,
    include_prior_outputs: bool,
    round_num: int,
) -> str:
    """
    Assembles the briefing text injected into each agent's prompt.
    On round 2, explicitly frames the CEO-identified conflicts so agents
    know what the sticking points are and can address them directly.
    """
    parts = [
        f"Company: {state['company_name']}",
        f"Task: {state['current_task']}",
        f"Context: {state.get('task_context', 'None provided')}",
    ]

    # Include financial data if available
    company_id = state.get("company_id", "")
    if company_id:
        from core.memory.financials import get_financial_summary
        fin_summary = get_financial_summary(company_id)
        if fin_summary:
            parts.append(fin_summary)

    if state.get("relevant_memories"):
        distilled = [m for m in state["relevant_memories"]
                     if m.get("source") == "distilled_knowledge"]
        other = [m for m in state["relevant_memories"]
                 if m.get("source") != "distilled_knowledge"]

        if distilled:
            parts.append(
                "COMPANY INSTITUTIONAL KNOWLEDGE:\n"
                + distilled[0].get("reasoning", "")
            )

        if other:
            mem_text = "\n".join(
                f"- {m['task']}: {m['outcome']}"
                for m in other if m.get("task")
            )
            if mem_text:
                parts.append(f"Recent decisions (since last knowledge update):\n{mem_text}")

    owner_directions = extract_owner_directions(state)
    if owner_directions:
        parts.append(
            "OWNER DIRECTIONS (treat these as settled — do not re-litigate):\n"
            + "\n".join(f"- {d}" for d in owner_directions)
        )

    if include_prior_outputs and state.get("agent_outputs"):
        outputs_text = "\n\n".join(
            f"{o['agent'].upper()}:\n{o['analysis']}\n"
            f"Recommendation: {o['recommendation']}"
            for o in state["agent_outputs"]
        )
        parts.append(f"Your colleagues' positions:\n{outputs_text}")

    if round_num >= 2 and state.get("conflicts_identified"):
        conflict_text = "\n".join(
            f"- {c}" for c in state["conflicts_identified"]
        )
        parts.append(
            f"NOTE — Round 2 of deliberation. The CEO has identified the "
            f"following unresolved conflicts after round 1. Please reconsider "
            f"your position with these specific tensions in mind:\n{conflict_text}"
        )

    return "\n\n".join(parts)


def extract_owner_directions(state: dict) -> list[str]:
    """
    Pull any human decisions or 'more info' context from the session's
    message history.
    """
    directions = []
    for msg in state.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content", "").strip()
            if content:
                directions.append(content)
    return directions
