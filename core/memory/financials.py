"""
core/memory/financials.py

Financial data management — store and query company financial data
so agents can make data-grounded recommendations.

Data is stored in a `financials` table in the per-company SQLite database.
Each row is a monthly snapshot: cash on hand, revenue, expenses, and
computed free cash flow.

Usage:
    python scripts/financials.py --company janky_games --add \
        --month 2026-04 --cash 5000 --revenue 1200 --expenses 800

    python scripts/financials.py --company janky_games --show

Agents access financial data via get_financial_summary(), which is
included in the agent briefing when available.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_ROOT


def ensure_financials_table(company_id: str) -> None:
    """Create the financials table if it doesn't exist."""
    from core.memory.writer import _db_path, _ensure_db_exists
    _ensure_db_exists(company_id)
    db = _db_path(company_id)
    with sqlite3.connect(str(db)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS financials (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id  TEXT NOT NULL,
                month       TEXT NOT NULL,
                cash        REAL NOT NULL DEFAULT 0,
                revenue     REAL NOT NULL DEFAULT 0,
                expenses    REAL NOT NULL DEFAULT 0,
                fcf         REAL NOT NULL DEFAULT 0,
                notes       TEXT,
                updated_at  TEXT NOT NULL,
                UNIQUE(company_id, month)
            );
            CREATE INDEX IF NOT EXISTS idx_financials_company
                ON financials(company_id, month DESC);
        """)


def add_monthly_snapshot(
    company_id: str,
    month: str,
    cash: float,
    revenue: float,
    expenses: float,
    notes: str = "",
) -> None:
    """
    Add or update a monthly financial snapshot.
    FCF is computed automatically as revenue - expenses.
    """
    ensure_financials_table(company_id)
    from core.memory.writer import _db_path
    db = _db_path(company_id)
    now = datetime.now(timezone.utc).isoformat()
    fcf = revenue - expenses

    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            """
            INSERT INTO financials
                (company_id, month, cash, revenue, expenses, fcf, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, month) DO UPDATE SET
                cash=excluded.cash,
                revenue=excluded.revenue,
                expenses=excluded.expenses,
                fcf=excluded.fcf,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (company_id, month, cash, revenue, expenses, fcf, notes, now),
        )


def get_financial_summary(company_id: str, months: int = 6) -> str:
    """
    Returns a formatted financial summary for inclusion in agent briefings.
    Shows the last N months of data plus computed trends.
    Returns empty string if no financial data exists.
    """
    ensure_financials_table(company_id)
    from core.memory.writer import _db_path
    db = _db_path(company_id)

    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT month, cash, revenue, expenses, fcf, notes
                FROM financials
                WHERE company_id = ?
                ORDER BY month DESC
                LIMIT ?
                """,
                (company_id, months),
            ).fetchall()

        if not rows:
            return ""

        lines = ["FINANCIAL DATA:"]
        lines.append(f"| Month | Cash | Revenue | Expenses | FCF | Notes |")
        lines.append(f"|-------|------|---------|----------|-----|-------|")

        for row in reversed(rows):  # oldest first
            notes = row["notes"][:30] if row["notes"] else ""
            lines.append(
                f"| {row['month']} | ${row['cash']:,.0f} | "
                f"${row['revenue']:,.0f} | ${row['expenses']:,.0f} | "
                f"${row['fcf']:,.0f} | {notes} |"
            )

        # Compute trends from most recent vs oldest
        if len(rows) >= 2:
            latest = rows[0]
            oldest = rows[-1]
            rev_change = latest["revenue"] - oldest["revenue"]
            fcf_change = latest["fcf"] - oldest["fcf"]
            lines.append("")
            lines.append(f"Revenue trend ({len(rows)} months): "
                         f"{'up' if rev_change > 0 else 'down'} ${abs(rev_change):,.0f}")
            lines.append(f"FCF trend: {'up' if fcf_change > 0 else 'down'} "
                         f"${abs(fcf_change):,.0f}")
            lines.append(f"Current cash position: ${latest['cash']:,.0f}")
            if latest["fcf"] != 0:
                runway = latest["cash"] / abs(latest["fcf"])
                if latest["fcf"] < 0:
                    lines.append(f"Runway at current burn: {runway:.1f} months")

        return "\n".join(lines)

    except Exception:
        return ""


def get_all_snapshots(company_id: str) -> list[dict]:
    """Return all financial snapshots for display/export."""
    ensure_financials_table(company_id)
    from core.memory.writer import _db_path
    db = _db_path(company_id)

    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT month, cash, revenue, expenses, fcf, notes
                FROM financials
                WHERE company_id = ?
                ORDER BY month ASC
                """,
                (company_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
