"""
scripts/financials.py

Manage company financial data from the command line.

Usage:
    python scripts/financials.py --company janky_games --add \
        --month 2026-04 --cash 5000 --revenue 1200 --expenses 800

    python scripts/financials.py --company janky_games --show
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from core.memory.financials import (
    add_monthly_snapshot,
    get_financial_summary,
    get_all_snapshots,
)


def main():
    parser = argparse.ArgumentParser(
        description="Manage company financial data."
    )
    parser.add_argument("--company", required=True, help="Company ID")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", action="store_true", help="Add/update a monthly snapshot")
    group.add_argument("--show", action="store_true", help="Show financial summary")

    parser.add_argument("--month", help="Month (YYYY-MM format)")
    parser.add_argument("--cash", type=float, help="Cash on hand")
    parser.add_argument("--revenue", type=float, help="Monthly revenue")
    parser.add_argument("--expenses", type=float, help="Monthly expenses")
    parser.add_argument("--notes", default="", help="Optional notes")

    args = parser.parse_args()

    if args.add:
        if not all([args.month, args.cash is not None,
                    args.revenue is not None, args.expenses is not None]):
            parser.error("--add requires --month, --cash, --revenue, --expenses")

        add_monthly_snapshot(
            args.company, args.month,
            args.cash, args.revenue, args.expenses,
            args.notes,
        )
        print(f"Added snapshot for {args.month} "
              f"(FCF: ${args.revenue - args.expenses:,.0f})")

    elif args.show:
        summary = get_financial_summary(args.company)
        if summary:
            print(summary)
        else:
            print("No financial data found. Use --add to add snapshots.")


if __name__ == "__main__":
    main()
