"""
core/graph/worker_nodes.py

Node functions for worker dispatch and memory write.
"""

from core.agents import WORKER_AGENTS
from core.memory.writer import write_session_to_db
from core.graph.node_utils import _notify, _log


def spawn_workers(state: dict) -> dict:
    """
    After human approval, identifies and dispatches matching worker agents.

    Gates:
        - human_decision must start with 'implement'
        - Each worker's keywords must match the human's instruction

    Non-interactive workers execute inline. Interactive workers (CCA) are
    flagged as pending for the UI to handle.
    """
    human_decision = (state.get("human_decision") or "").strip().lower()

    if not human_decision.startswith("implement"):
        return {}

    human_text = (state.get("human_decision") or "").strip()
    for prefix in ("implement", "Implement", "IMPLEMENT"):
        if human_text.startswith(prefix):
            human_text = human_text[len(prefix):].strip()
            break

    match_text = human_text if human_text else state.get("current_task", "")
    config = state.get("company_config", {})

    task_parts = []
    if state.get("current_task"):
        task_parts.append(f"Task: {state['current_task']}")
    if state.get("ceo_synthesis"):
        task_parts.append(f"CEO recommendation: {state['ceo_synthesis']}")
    if state.get("human_decision"):
        task_parts.append(f"Owner direction: {state['human_decision']}")
    task_text = "\n\n".join(task_parts)

    results = []

    for WorkerClass in WORKER_AGENTS:
        if not worker_matches(WorkerClass, match_text):
            continue

        if WorkerClass.interactive:
            try:
                WorkerClass(config)
            except ValueError as e:
                _log(f"[{WorkerClass.role.upper()}] Skipped — {e}")
                continue

            _log(f"[{WorkerClass.role.upper()}] Flagged for interactive session.")
            results.append({
                "worker":  WorkerClass.role,
                "pending": True,
                "task":    task_text,
            })
            continue

        _notify("agent_start", agent=WorkerClass.role, phase="implementation",
                index=0, total=1)

        try:
            worker = WorkerClass(config)
        except ValueError as e:
            _log(f"[{WorkerClass.role.upper()}] Skipped — {e}")
            continue

        _log(f"[{WorkerClass.role.upper()}] Dispatching...")
        result = worker.execute(task_text)
        results.append(result)

        if result.get("success"):
            _log(f"[{WorkerClass.role.upper()}] Complete.")
        else:
            _log(f"[{WorkerClass.role.upper()}] Failed — "
                 f"{result.get('summary', '')[:80]}")

    if not results:
        return {}

    return {
        "worker_results": results,
        "messages": [
            {"role": "assistant",
             "content": f"[{r.get('worker', '?').upper()}] "
                        f"{'Pending interactive session' if r.get('pending') else r.get('summary', '')[:500]}"}
            for r in results
        ],
    }


def worker_matches(worker_cls, text: str) -> bool:
    """Check if a worker's keywords match the given text."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in worker_cls.keywords)


def memory_write(state: dict) -> dict:
    """
    Flushes the completed session to SQLite and ChromaDB.
    Triggers the knowledge indexer if threshold is reached.
    """
    write_session_to_db(state)
    _log("[MEMORY] Session written to SQLite and ChromaDB.")

    company_id = state.get("company_id", "")
    config = state.get("company_config", {})
    if company_id and config:
        from core.memory.indexer import should_reindex, run_indexer
        if should_reindex(company_id, config):
            _log("[INDEXER] Threshold reached — rebuilding knowledge document...")
            try:
                run_indexer(company_id)
                _log("[INDEXER] Knowledge document updated.")
            except Exception as e:
                _log(f"[INDEXER] Failed (non-fatal): {e}")

    return {}
