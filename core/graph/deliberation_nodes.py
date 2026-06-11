"""
core/graph/deliberation_nodes.py

Node functions for the deliberation pipeline:
    task_intake, memory_retrieval, prior_decision_check,
    round1_deliberation, cross_response, ceo_synthesis,
    present_recommendation, human_interrupt, reconsider_with_info
"""

import sqlite3
import uuid
from datetime import datetime, timezone

from core.agents import CEOAgent, CSUITE_AGENTS
from core.memory.retrieval import retrieve_relevant_memories
from core.state import AgentOutput
from core.graph.node_utils import _notify, _log, build_agent_briefing


# ── Infrastructure ───────────────────────────────────────────────────────────

def task_intake(state: dict) -> dict:
    """Entry point. Initialises session-level fields."""
    return {
        "session_id":           str(uuid.uuid4()),
        "session_start":        datetime.now(timezone.utc).isoformat(),
        "debate_round":         1,
        "agent_outputs":        [],
        "messages":             [],
        "consensus_reached":    False,
        "escalate_to_human":    False,
        "escalation_reason":    "",
        "ceo_synthesis":        "",
        "conflicts_identified": [],
        "decisions_made":       [],
    }


def memory_retrieval(state: dict) -> dict:
    """Fetches relevant past decisions and injects them into state."""
    memories = retrieve_relevant_memories(
        company_id=state["company_id"],
        query=state["current_task"],
    )
    return {"relevant_memories": memories}


# ── Prior decision check ─────────────────────────────────────────────────────

def prior_decision_check(state: dict) -> dict:
    """
    Checks whether the current task is asking about something already decided.
    Uses SQLite keyword search and ChromaDB similarity.
    """
    task = state.get("current_task", "").strip()
    company_id = state.get("company_id", "")
    memories = state.get("relevant_memories", [])

    if not task or not company_id:
        return {"prior_decision_found": False}

    question_patterns = [
        "what did we decide", "where do we stand", "what was decided",
        "what happened with", "status of", "update on", "did we",
        "have we decided", "what's the decision on", "recap",
    ]
    is_status_question = any(p in task.lower() for p in question_patterns)

    best_match = _find_matching_decision(company_id, task)

    if not best_match:
        for m in memories:
            score = m.get("similarity_score")
            if score is not None and score >= 0.85:
                if best_match is None or score > best_match.get("similarity_score", 0):
                    best_match = m

    if not best_match and not is_status_question:
        return {"prior_decision_found": False}

    knowledge_doc = ""
    for m in memories:
        if m.get("source") == "distilled_knowledge":
            knowledge_doc = m.get("reasoning", "")
            break

    if is_status_question and knowledge_doc:
        _log("[MEMORY] Status question detected — CEO answering from knowledge document.")
        ceo = CEOAgent(state["company_config"])
        prompt = (
            f"The owner is asking: \"{task}\"\n\n"
            f"Answer this question using ONLY the institutional knowledge below. "
            f"Be specific about what was decided, when, and why. If the topic "
            f"hasn't been decided yet, say so clearly.\n\n"
            f"INSTITUTIONAL KNOWLEDGE:\n{knowledge_doc}"
        )
        from core.agents.base import invoke_llm
        synthesis = invoke_llm(ceo.llm, prompt)

        return {
            "prior_decision_found": True,
            "ceo_synthesis":        synthesis,
            "consensus_reached":    True,
            "escalate_to_human":    False,
            "messages": [{"role": "assistant", "content": synthesis}],
        }

    if best_match:
        _log("[MEMORY] Prior decision found — skipping deliberation.")
        prior_task = best_match.get("task", "")
        prior_outcome = best_match.get("outcome", "")
        prior_reasoning = best_match.get("reasoning", "")
        prior_override = best_match.get("human_override", "")

        synthesis_parts = [
            "This topic has already been decided in a prior session.",
            "",
            f"**Prior task:** {prior_task}",
            f"**Decision:** {prior_outcome}",
        ]
        if prior_reasoning:
            synthesis_parts.append(f"**Reasoning:** {prior_reasoning}")
        if prior_override:
            synthesis_parts.append(f"**Owner directive:** {prior_override}")
        synthesis_parts.append(
            "\nIf circumstances have changed, provide new information "
            "via 'more info' to trigger a fresh deliberation."
        )

        return {
            "prior_decision_found": True,
            "ceo_synthesis":        "\n".join(synthesis_parts),
            "consensus_reached":    True,
            "escalate_to_human":    False,
            "messages": [{"role": "assistant", "content": "\n".join(synthesis_parts)}],
        }

    return {"prior_decision_found": False}


def _find_matching_decision(company_id: str, task: str) -> dict | None:
    """Search SQLite for a prior decision matching the current task."""
    from core.config import database_path

    db_path = database_path(company_id)
    if not db_path.exists():
        return None

    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "we", "our", "us",
        "did", "do", "does", "what", "where", "how", "when", "about",
        "with", "for", "and", "or", "but", "not", "this", "that", "on",
        "in", "to", "of", "it", "its", "has", "have", "had", "can",
        "should", "would", "could", "will", "been", "being", "from",
    }
    words = [
        w.lower().strip("?.,!\"'")
        for w in task.split()
        if len(w) > 2 and w.lower().strip("?.,!\"'") not in stop_words
    ]
    if not words:
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task, outcome, reasoning, human_override, decided_at
                FROM decisions WHERE outcome IS NOT NULL
                ORDER BY decided_at DESC
                """,
            ).fetchall()

        best = None
        best_score = 0
        for row in rows:
            prior_task = (row["task"] or "").lower()
            matches = sum(1 for w in words if w in prior_task)
            score = matches / len(words) if words else 0
            if score > best_score and score >= 0.4:
                best_score = score
                best = {
                    "task":           row["task"],
                    "outcome":        row["outcome"],
                    "reasoning":      row["reasoning"] or "",
                    "human_override": row["human_override"] or "",
                    "source":         "sqlite_keyword_match",
                    "similarity_score": None,
                }
        return best
    except Exception:
        return None


# ── Deliberation ─────────────────────────────────────────────────────────────

def round1_deliberation(state: dict) -> dict:
    """Each C-suite agent independently analyzes the current task."""
    round_num = state.get("debate_round", 1)
    outputs   = []
    briefing  = build_agent_briefing(state, include_prior_outputs=False,
                                      round_num=round_num)

    for i, AgentClass in enumerate(CSUITE_AGENTS):
        agent  = AgentClass(state["company_config"])
        _notify("agent_start", agent=agent.role, phase="deliberation",
                round=round_num, index=i, total=len(CSUITE_AGENTS))
        result = agent.analyze(briefing)
        output = AgentOutput(
            agent          = agent.role,
            analysis       = result["analysis"],
            recommendation = result["recommendation"],
            concerns       = result["concerns"],
            confidence     = result["confidence"],
        )
        outputs.append(output)
        _notify("agent_complete", agent=agent.role, phase="deliberation",
                output=dict(output))
        _log(f"[{agent.role.upper()}] {result['recommendation'].upper()} "
             f"({result['confidence']:.0%} confidence)")

    return {
        "agent_outputs": outputs,
        "messages": [{"role": "system",
                      "content": f"Round {round_num} deliberation complete."}],
    }


def cross_response(state: dict) -> dict:
    """Each agent reads peer outputs and responds."""
    round_num     = state.get("debate_round", 1)
    prior_outputs = state["agent_outputs"]
    briefing      = build_agent_briefing(state, include_prior_outputs=True,
                                          round_num=round_num)
    outputs = []

    for i, AgentClass in enumerate(CSUITE_AGENTS):
        agent  = AgentClass(state["company_config"])
        _notify("agent_start", agent=agent.role, phase="cross-response",
                round=round_num, index=i, total=len(CSUITE_AGENTS))
        peers  = [o for o in prior_outputs if o["agent"] != agent.role]
        result = agent.respond_to_peers(briefing, peers)
        output = AgentOutput(
            agent          = f"{agent.role}_response",
            analysis       = result["analysis"],
            recommendation = result["recommendation"],
            concerns       = result["concerns"],
            confidence     = result["confidence"],
        )
        outputs.append(output)
        _notify("agent_complete", agent=f"{agent.role}_response",
                phase="cross-response", output=dict(output))
        _log(f"[{agent.role.upper()} cross-response] {result['recommendation'].upper()}")

    return {
        "agent_outputs": outputs,
        "messages": [{"role": "system",
                      "content": f"Round {round_num} cross-response complete."}],
    }


# ── CEO ──────────────────────────────────────────────────────────────────────

def ceo_synthesis(state: dict) -> dict:
    """CEO reads all agent outputs and attempts synthesis."""
    ceo       = CEOAgent(state["company_config"])
    round_num = state.get("debate_round", 1)
    is_final  = round_num >= 2
    _notify("agent_start", agent="ceo", phase="synthesis", round=round_num,
            index=0, total=1)

    result = ceo.synthesize(
        task           = state["current_task"],
        agent_outputs  = state["agent_outputs"],
        memories       = state.get("relevant_memories", []),
        is_final_round = is_final,
    )

    _log(f"[CEO] {'CONSENSUS' if result['consensus'] else 'CONFLICT DETECTED'}")

    return {
        "ceo_synthesis":        result["synthesis"],
        "conflicts_identified": result["conflicts"],
        "consensus_reached":    result["consensus"],
        "escalate_to_human":    result["escalate"],
        "debate_round":         round_num + 1,
        "messages": [{"role": "assistant", "content": result["synthesis"]}],
    }


def present_recommendation(state: dict) -> dict:
    """Assembles the full deliberation report for display."""
    ceo    = CEOAgent(state["company_config"])
    report = ceo.format_presentation(state)
    print(report)
    return {
        "messages": [{"role": "assistant", "content": report}],
    }


# ── Human interaction ────────────────────────────────────────────────────────

def human_interrupt_node(state: dict) -> dict:
    """LangGraph pauses here. Resumed with the human's decision."""
    human_decision = state.get("human_decision", "")
    _log(f"[HUMAN] {human_decision[:80]}")
    return {
        "messages": [{"role": "user", "content": human_decision}],
    }


def reconsider_with_info(state: dict) -> dict:
    """Human provided new info — reset deliberation with updated context."""
    raw = state.get("human_decision", "")
    new_info = raw.strip()
    for prefix in ("more info", "More info", "MORE INFO"):
        if new_info.startswith(prefix):
            new_info = new_info[len(prefix):].strip().lstrip(":").strip()
            break

    existing = state.get("task_context", "")
    separator = "\n\n" if existing else ""
    updated_context = f"{existing}{separator}[Additional information from owner] {new_info}"

    _log("[RECONSIDER] New information received — restarting deliberation")

    return {
        "task_context":         updated_context,
        "debate_round":         1,
        "consensus_reached":    False,
        "escalate_to_human":    False,
        "escalation_reason":    "",
        "ceo_synthesis":        "",
        "conflicts_identified": [],
        "human_decision":       None,
        "messages": [{"role": "system",
                      "content": f"Owner provided new information: {new_info}. "
                                 f"Restarting deliberation with updated context."}],
    }
