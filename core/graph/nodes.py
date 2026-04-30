"""
core/graph/nodes.py

Re-export hub for all graph node functions.

The actual implementations live in sub-modules:
    deliberation_nodes.py — task intake through human interrupt
    worker_nodes.py       — worker dispatch and memory write
    node_utils.py         — shared utilities (callbacks, logging, briefing)

This file re-exports everything so session_graph.py and app.py
don't need to change their imports.
"""

# ── Shared utilities ─────────────────────────────────────────────────────────

from core.graph.node_utils import (
    set_progress_callback,
    _notify,
    _log,
    build_agent_briefing,
    extract_owner_directions,
)

# ── Deliberation nodes ───────────────────────────────────────────────────────

from core.graph.deliberation_nodes import (
    task_intake,
    memory_retrieval,
    prior_decision_check,
    round1_deliberation,
    cross_response,
    ceo_synthesis,
    present_recommendation,
    human_interrupt_node,
    reconsider_with_info,
)

# ── Worker & memory nodes ────────────────────────────────────────────────────

from core.graph.worker_nodes import (
    spawn_workers,
    worker_matches as _worker_matches,
    memory_write,
)
