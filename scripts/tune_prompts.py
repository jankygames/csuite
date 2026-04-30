"""
scripts/tune_prompts.py

Analyze human override patterns and suggest prompt adjustments
for agents that are frequently overridden.

This does NOT modify prompts automatically — it generates suggestions
that the owner reviews and applies manually.

Usage:
    python scripts/tune_prompts.py --company janky_games
    python scripts/tune_prompts.py --company janky_games --apply (writes suggestions to prompts/)
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import argparse
from core.config import COMPANY_ROOT, DATA_ROOT, load_agent_prompt
from core.agents.base import build_llm, invoke_llm


def analyze_overrides(company_id: str) -> dict:
    """
    Analyze which agents are most frequently overridden and why.
    Returns structured analysis per agent.
    """
    db_path = DATA_ROOT / company_id / f"{company_id}.db"
    if not db_path.exists():
        return {}

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Get all decisions with overrides
        overrides = conn.execute("""
            SELECT d.task, d.outcome, d.human_override, d.decided_at
            FROM decisions d
            WHERE d.human_override IS NOT NULL AND d.human_override != ''
            ORDER BY d.decided_at ASC
        """).fetchall()

        # Get all agent votes
        votes = conn.execute("""
            SELECT av.decision_id, av.agent, av.recommendation,
                   av.confidence, av.analysis,
                   d.human_override, d.outcome
            FROM agent_votes av
            JOIN decisions d ON av.decision_id = d.decision_id
            WHERE d.human_override IS NOT NULL AND d.human_override != ''
        """).fetchall()

    # Analyze per agent
    agent_analysis = {}
    for v in votes:
        agent = v["agent"]
        if agent not in agent_analysis:
            agent_analysis[agent] = {
                "total_votes": 0,
                "overridden_votes": 0,
                "patterns": [],
            }

        stats = agent_analysis[agent]
        stats["total_votes"] += 1

        # Check if the human override contradicts this agent's recommendation
        override = (v["human_override"] or "").lower()
        rec = (v["recommendation"] or "").lower()

        # Simple contradiction detection
        if rec == "block" and ("approve" in override or "proceed" in override):
            stats["overridden_votes"] += 1
            stats["patterns"].append(
                f"Agent said BLOCK, owner said proceed: {v['analysis'][:200]}"
            )
        elif rec == "proceed" and ("override" in override or "block" in override):
            stats["overridden_votes"] += 1
            stats["patterns"].append(
                f"Agent said PROCEED, owner disagreed: {v['analysis'][:200]}"
            )

    return agent_analysis


def generate_suggestions(company_id: str, config: dict) -> dict:
    """
    Use the LLM to generate prompt adjustment suggestions based on
    override patterns.
    """
    analysis = analyze_overrides(company_id)
    if not analysis:
        return {}

    llm = build_llm(config, temperature=0.4, max_tokens=2048)
    suggestions = {}

    for agent, stats in analysis.items():
        if stats["overridden_votes"] == 0:
            continue

        override_rate = stats["overridden_votes"] / max(stats["total_votes"], 1)
        if override_rate < 0.2:
            continue  # Less than 20% override rate — probably fine

        current_prompt = load_agent_prompt(company_id, agent, config)
        patterns = "\n".join(stats["patterns"][:5])

        prompt = (
            f"An AI agent playing the role of {agent.upper()} in a company's "
            f"C-suite has been overridden by the human owner {stats['overridden_votes']} "
            f"out of {stats['total_votes']} times ({override_rate:.0%} override rate).\n\n"
            f"Override patterns:\n{patterns}\n\n"
            f"Current agent prompt:\n{current_prompt[:2000]}\n\n"
            f"Suggest specific, concrete adjustments to the agent's prompt that would "
            f"better align its recommendations with the owner's demonstrated preferences. "
            f"Do NOT make the agent a yes-man — it should still raise genuine concerns. "
            f"But it should calibrate its risk tolerance and recommendation bias to better "
            f"match the owner's actual decision-making style.\n\n"
            f"Output ONLY the suggested prompt additions or modifications, not the full prompt."
        )

        suggestion = invoke_llm(llm, prompt)
        suggestions[agent] = {
            "override_rate": f"{override_rate:.0%}",
            "total_votes": stats["total_votes"],
            "overridden": stats["overridden_votes"],
            "suggestion": suggestion,
        }

    return suggestions


def main():
    parser = argparse.ArgumentParser(
        description="Analyze override patterns and suggest prompt adjustments."
    )
    parser.add_argument("--company", required=True, help="Company ID")
    parser.add_argument("--apply", action="store_true",
                        help="Write suggestions to prompts/ as .suggested.md files")
    args = parser.parse_args()

    config_path = COMPANY_ROOT / args.company / "config.json"
    if not config_path.exists():
        print(f"Error: No company found: {args.company}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    print(f"\nAnalyzing override patterns for {config.get('company_name', args.company)}...\n")

    suggestions = generate_suggestions(args.company, config)

    if not suggestions:
        print("No significant override patterns found. Agent prompts appear well-calibrated.")
        return

    for agent, data in suggestions.items():
        print(f"{'─' * 60}")
        print(f"  {agent.upper()} — override rate: {data['override_rate']} "
              f"({data['overridden']}/{data['total_votes']})")
        print(f"{'─' * 60}")
        print(data["suggestion"])
        print()

        if args.apply:
            suggest_path = (COMPANY_ROOT / args.company / "prompts"
                           / f"{agent}.suggested.md")
            suggest_path.write_text(data["suggestion"], encoding="utf-8")
            print(f"  Written to: {suggest_path}")
            print(f"  Review and merge into {agent}.md manually.\n")


if __name__ == "__main__":
    main()
