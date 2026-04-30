"""
scripts/scheduled_session.py

Run a scheduled deliberation session for a company.
Generates an agenda from the knowledge document and recent activity,
then runs the deliberation through the CLI runner.

Designed to be triggered by cron / Task Scheduler.

Usage:
    python scripts/scheduled_session.py --company janky_games
    python scripts/scheduled_session.py --company janky_games --topic "Weekly review"

Schedule example (Windows Task Scheduler):
    Program: E:\\venvs\\csuite\\Scripts\\python.exe
    Arguments: scripts/scheduled_session.py --company janky_games
    Start in: D:\\csuite
    Trigger: Weekly, Monday 9:00 AM
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import argparse
from core.config import COMPANY_ROOT
from core.agents.ceo import CEOAgent
from core.agents.base import invoke_llm
from core.memory.indexer import load_knowledge
from core.memory.financials import get_financial_summary


def generate_agenda(company_id: str, config: dict,
                     topic: str = "") -> str:
    """
    Ask the CEO to generate a session agenda based on the company's
    knowledge document, recent financial data, and optional topic.
    """
    ceo = CEOAgent(config)
    knowledge = load_knowledge(company_id)
    financials = get_financial_summary(company_id)

    prompt_parts = [
        f"You are the CEO of {config.get('company_name', 'the company')}.",
        "Generate a focused agenda for today's strategy session.",
        "List 1-3 specific topics that need discussion or decision based on:",
        "- Recent decisions and their status",
        "- Any unresolved issues or pending items",
        "- Financial trends (if available)",
        "- Strategic priorities",
        "",
        "Format each topic as a clear question for the C-suite to deliberate on.",
    ]

    if topic:
        prompt_parts.append(f"\nThe owner has requested this specific topic: {topic}")

    if knowledge:
        prompt_parts.append(f"\nINSTITUTIONAL KNOWLEDGE:\n{knowledge}")

    if financials:
        prompt_parts.append(f"\n{financials}")

    prompt_parts.append(
        "\nProduce ONLY the agenda items, one per line, each as a question. "
        "No preamble, no numbering."
    )

    return invoke_llm(ceo.llm, "\n".join(prompt_parts))


def run_scheduled_session(company_id: str, topic: str = "") -> None:
    """Run a complete scheduled session."""
    config_path = COMPANY_ROOT / company_id / "config.json"
    if not config_path.exists():
        print(f"Error: No company found: {company_id}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    company_name = config.get("company_name", company_id)

    print(f"\n{'=' * 60}")
    print(f"  SCHEDULED SESSION: {company_name}")
    print(f"{'=' * 60}\n")

    # Generate agenda
    print("  Generating agenda...")
    agenda = generate_agenda(company_id, config, topic)
    print(f"\n  Agenda:\n")
    for line in agenda.strip().split("\n"):
        line = line.strip()
        if line:
            print(f"    - {line}")

    # Run each agenda item through the CLI runner
    from core.graph.session_graph import build_session_graph

    for item in agenda.strip().split("\n"):
        item = item.strip().lstrip("-•").strip()
        if not item:
            continue

        print(f"\n{'─' * 60}")
        print(f"  TOPIC: {item[:80]}")
        print(f"{'─' * 60}\n")

        graph, ctx = build_session_graph(company_id)
        thread = {"configurable": {"thread_id": f"{company_id}_sched_{hash(item)}"}}

        initial_state = {
            "company_id":           company_id,
            "company_name":         company_name,
            "company_config":       config,
            "current_task":         item,
            "task_context":         "This is a scheduled review session.",
            "agenda":               [],
            "relevant_memories":    [],
            "agent_outputs":        [],
            "messages":             [],
            "prior_decision_found": False,
            "consensus_reached":    False,
            "escalate_to_human":    False,
            "escalation_reason":    "",
            "human_decision":       None,
            "decisions_made":       [],
            "debate_round":         1,
            "session_id":           "",
            "session_start":        "",
            "ceo_synthesis":        "",
            "conflicts_identified": [],
            "worker_results":       [],
        }

        # Stream to human interrupt
        for _ in graph.stream(initial_state, thread, stream_mode="values"):
            pass

        # Auto-approve scheduled items (no human in the loop)
        graph.update_state(
            thread,
            {"human_decision": "approve (scheduled session — auto-approved)"},
            as_node="human_interrupt",
        )

        for _ in graph.stream(None, thread, stream_mode="values"):
            pass

        ctx.__exit__(None, None, None)
        print("  Decision written to memory.\n")

    print(f"\n{'=' * 60}")
    print(f"  Scheduled session complete.")
    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run a scheduled deliberation session."
    )
    parser.add_argument("--company", required=True, help="Company ID")
    parser.add_argument("--topic", default="",
                        help="Optional specific topic for the session")
    args = parser.parse_args()

    run_scheduled_session(args.company, args.topic)


if __name__ == "__main__":
    main()
