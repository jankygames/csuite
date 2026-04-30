"""
scripts/audit.py

Decision audit dashboard — view decision history, override patterns,
and agent agreement rates for a company.

Usage:
    python scripts/audit.py --company janky_games
    python scripts/audit.py --company janky_games --export audit.json
    python scripts/audit.py --all   (multi-company summary)
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from core.config import DATA_ROOT, COMPANY_ROOT


def audit_company(company_id: str) -> dict:
    """Generate a full audit report for a company."""
    db_path = DATA_ROOT / company_id / f"{company_id}.db"
    if not db_path.exists():
        return {"company_id": company_id, "error": "No database found"}

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Decision count and outcomes
        decisions = conn.execute("""
            SELECT task, outcome, reasoning, human_override,
                   escalated, decided_at
            FROM decisions ORDER BY decided_at ASC
        """).fetchall()

        # Agent votes
        votes = conn.execute("""
            SELECT agent, recommendation, confidence
            FROM agent_votes
        """).fetchall()

        # Sessions
        sessions = conn.execute("""
            SELECT COUNT(*) as count FROM sessions
        """).fetchone()

    total_decisions = len(decisions)
    overrides = [d for d in decisions if d["human_override"]]
    escalations = [d for d in decisions if d["escalated"]]

    # Agent agreement analysis
    agent_stats = {}
    for v in votes:
        agent = v["agent"]
        if agent not in agent_stats:
            agent_stats[agent] = {"total": 0, "proceed": 0, "block": 0,
                                  "modify": 0, "avg_confidence": 0,
                                  "confidence_sum": 0}
        stats = agent_stats[agent]
        stats["total"] += 1
        rec = v["recommendation"].lower()
        if rec in stats:
            stats[rec] += 1
        stats["confidence_sum"] += v["confidence"] or 0.5

    for agent, stats in agent_stats.items():
        if stats["total"] > 0:
            stats["avg_confidence"] = round(
                stats["confidence_sum"] / stats["total"], 2
            )
        del stats["confidence_sum"]

    return {
        "company_id":       company_id,
        "total_sessions":   sessions["count"] if sessions else 0,
        "total_decisions":  total_decisions,
        "total_overrides":  len(overrides),
        "override_rate":    f"{len(overrides)/total_decisions:.0%}" if total_decisions else "N/A",
        "total_escalations": len(escalations),
        "agent_stats":      agent_stats,
        "recent_overrides": [
            {
                "task": d["task"][:80],
                "override": d["human_override"][:80],
                "date": d["decided_at"],
            }
            for d in overrides[-5:]
        ],
        "recent_decisions": [
            {
                "task": d["task"][:80],
                "outcome": (d["outcome"] or "")[:80],
                "date": d["decided_at"],
            }
            for d in decisions[-10:]
        ],
    }


def audit_all_companies() -> list[dict]:
    """Generate summary audit for all companies."""
    summaries = []
    if not COMPANY_ROOT.exists():
        return summaries

    for d in sorted(COMPANY_ROOT.iterdir()):
        config_file = d / "config.json"
        if d.is_dir() and config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
                report = audit_company(d.name)
                report["company_name"] = config.get("company_name", d.name)
                summaries.append(report)
            except Exception:
                continue

    return summaries


def print_audit(report: dict) -> None:
    """Pretty-print an audit report."""
    if "error" in report:
        print(f"  {report['company_id']}: {report['error']}")
        return

    print(f"\n{'=' * 60}")
    print(f"  AUDIT: {report.get('company_name', report['company_id'])}")
    print(f"{'=' * 60}")
    print(f"  Sessions:    {report['total_sessions']}")
    print(f"  Decisions:   {report['total_decisions']}")
    print(f"  Overrides:   {report['total_overrides']} ({report['override_rate']})")
    print(f"  Escalations: {report['total_escalations']}")

    if report["agent_stats"]:
        print(f"\n  Agent Stats:")
        for agent, stats in sorted(report["agent_stats"].items()):
            print(f"    {agent.upper():12} — "
                  f"proceed:{stats['proceed']} block:{stats['block']} "
                  f"modify:{stats['modify']} "
                  f"avg_confidence:{stats['avg_confidence']}")

    if report["recent_overrides"]:
        print(f"\n  Recent Overrides:")
        for o in report["recent_overrides"]:
            print(f"    {o['date'][:10]} | {o['task']}")
            print(f"              -> {o['override']}")

    if report["recent_decisions"]:
        print(f"\n  Recent Decisions:")
        for d in report["recent_decisions"]:
            print(f"    {d['date'][:10]} | {d['task']} -> {d['outcome']}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Decision audit dashboard."
    )
    parser.add_argument("--company", help="Company ID")
    parser.add_argument("--all", action="store_true",
                        help="Show all companies")
    parser.add_argument("--export", help="Export to JSON file")
    args = parser.parse_args()

    if not args.company and not args.all:
        parser.error("Provide --company or --all")

    if args.all:
        reports = audit_all_companies()
        for r in reports:
            print_audit(r)
        if args.export:
            Path(args.export).write_text(
                json.dumps(reports, indent=2, default=str),
                encoding="utf-8",
            )
            print(f"Exported to {args.export}")
    else:
        report = audit_company(args.company)
        print_audit(report)
        if args.export:
            Path(args.export).write_text(
                json.dumps(report, indent=2, default=str),
                encoding="utf-8",
            )
            print(f"Exported to {args.export}")


if __name__ == "__main__":
    main()
