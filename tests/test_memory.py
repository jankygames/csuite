"""
tests/test_memory.py

Tests for the memory system:
    - writer.py (chat messages, worker outputs)
    - financials.py
    - ingest.py
    - indexer.py (load_knowledge, should_reindex)
"""

import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from core.memory.writer import (
    write_chat_message,
    load_chat_history,
    write_worker_output,
)
from core.memory.financials import (
    add_monthly_snapshot,
    get_financial_summary,
    get_all_snapshots,
    ensure_financials_table,
)
from core.memory.ingest import ingest_file, ingest_directory
from core.memory.indexer import load_knowledge, should_reindex


class TestChatPersistence:
    def test_write_and_load(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        # Monkeypatch the writer's path functions
        import core.memory.writer as writer_mod
        monkeypatch.setattr(
            writer_mod, "_db_path",
            lambda cid: db_path
        )
        monkeypatch.setattr(
            writer_mod, "_ensure_db_exists",
            lambda cid: None
        )

        write_chat_message(company_id, "user", "Hello CEO")
        write_chat_message(company_id, "assistant", "Hello owner")

        history = load_chat_history(company_id, limit=10)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello CEO"
        assert history[1]["role"] == "assistant"

    def test_load_respects_limit(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        for i in range(10):
            write_chat_message(company_id, "user", f"Message {i}")

        history = load_chat_history(company_id, limit=3)
        assert len(history) == 3

    def test_load_empty_returns_empty(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        history = load_chat_history(company_id)
        assert history == []


class TestWorkerOutputPersistence:
    def test_write_worker_output(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        write_worker_output(company_id, {
            "worker": "cwa",
            "task": "draft a blog post",
            "success": True,
            "summary": "Blog post drafted",
            "output": "# My Blog Post\n\nContent here.",
        })

        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM worker_outputs WHERE company_id = ?",
                (company_id,),
            ).fetchone()
        assert row is not None


class TestFinancials:
    def test_add_and_retrieve(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        import core.memory.financials as fin_mod
        monkeypatch.setattr(fin_mod, "ensure_financials_table",
                            lambda cid: None)

        # Create financials table manually
        with sqlite3.connect(str(db_path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS financials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL, month TEXT NOT NULL,
                    cash REAL DEFAULT 0, revenue REAL DEFAULT 0,
                    expenses REAL DEFAULT 0, fcf REAL DEFAULT 0,
                    notes TEXT, updated_at TEXT NOT NULL,
                    UNIQUE(company_id, month)
                );
            """)

        add_monthly_snapshot(company_id, "2026-01", 5000, 1200, 800)
        add_monthly_snapshot(company_id, "2026-02", 5400, 1300, 850)

        snapshots = get_all_snapshots(company_id)
        assert len(snapshots) == 2
        assert snapshots[0]["month"] == "2026-01"
        assert snapshots[0]["fcf"] == 400  # 1200 - 800

    def test_summary_format(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        import core.memory.financials as fin_mod
        monkeypatch.setattr(fin_mod, "ensure_financials_table",
                            lambda cid: None)

        with sqlite3.connect(str(db_path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS financials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL, month TEXT NOT NULL,
                    cash REAL DEFAULT 0, revenue REAL DEFAULT 0,
                    expenses REAL DEFAULT 0, fcf REAL DEFAULT 0,
                    notes TEXT, updated_at TEXT NOT NULL,
                    UNIQUE(company_id, month)
                );
            """)

        add_monthly_snapshot(company_id, "2026-01", 5000, 1200, 800)

        summary = get_financial_summary(company_id)
        assert "FINANCIAL DATA" in summary
        assert "$5,000" in summary

    def test_empty_summary(self, temp_db, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        import core.memory.financials as fin_mod
        monkeypatch.setattr(fin_mod, "ensure_financials_table",
                            lambda cid: None)

        with sqlite3.connect(str(db_path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS financials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL, month TEXT NOT NULL,
                    cash REAL DEFAULT 0, revenue REAL DEFAULT 0,
                    expenses REAL DEFAULT 0, fcf REAL DEFAULT 0,
                    notes TEXT, updated_at TEXT NOT NULL,
                    UNIQUE(company_id, month)
                );
            """)

        summary = get_financial_summary(company_id)
        assert summary == ""


class TestIngest:
    def test_ingest_text_file(self, temp_db, tmp_path, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        doc = tmp_path / "strategy.md"
        doc.write_text("# Strategy\n\nOur plan is to grow.", encoding="utf-8")

        result = ingest_file(company_id, str(doc))
        assert result["success"] is True
        assert result["entries"] == 1

        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute("SELECT * FROM knowledge").fetchall()
        assert len(rows) == 1

    def test_ingest_json_array(self, temp_db, tmp_path, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        doc = tmp_path / "data.json"
        doc.write_text(json.dumps([
            {"title": "Item 1", "content": "Data 1"},
            {"title": "Item 2", "content": "Data 2"},
        ]), encoding="utf-8")

        result = ingest_file(company_id, str(doc))
        assert result["success"] is True
        assert result["entries"] == 2

    def test_ingest_csv(self, temp_db, tmp_path, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        doc = tmp_path / "data.csv"
        doc.write_text("title,value\nRow1,100\nRow2,200", encoding="utf-8")

        result = ingest_file(company_id, str(doc))
        assert result["success"] is True
        assert result["entries"] == 2

    def test_ingest_nonexistent_file(self):
        result = ingest_file("test", "/nonexistent/file.txt")
        assert result["success"] is False

    def test_ingest_unsupported_extension(self, tmp_path):
        doc = tmp_path / "file.xyz"
        doc.write_text("data", encoding="utf-8")
        result = ingest_file("test", str(doc))
        assert result["success"] is False

    def test_ingest_directory(self, temp_db, tmp_path, monkeypatch):
        db_path, company_id = temp_db

        import core.memory.writer as writer_mod
        monkeypatch.setattr(writer_mod, "_db_path", lambda cid: db_path)
        monkeypatch.setattr(writer_mod, "_ensure_db_exists", lambda cid: None)

        (tmp_path / "a.txt").write_text("Doc A", encoding="utf-8")
        (tmp_path / "b.md").write_text("Doc B", encoding="utf-8")
        (tmp_path / "c.xyz").write_text("Ignored", encoding="utf-8")

        result = ingest_directory(company_id, str(tmp_path))
        assert result["files"] == 2
        assert result["entries"] == 2


class TestIndexer:
    def test_load_knowledge_empty(self, monkeypatch):
        import core.memory.indexer as idx_mod
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", Path("/nonexistent"))
        monkeypatch.setattr(idx_mod, "COMPANY_ROOT", Path("/nonexistent"))
        assert load_knowledge("fake_company") == ""

    def test_load_knowledge_from_file(self, tmp_path, monkeypatch):
        import core.memory.indexer as idx_mod
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)
        monkeypatch.setattr(idx_mod, "COMPANY_ROOT", tmp_path)

        company_dir = tmp_path / "test_co"
        company_dir.mkdir()
        (company_dir / "knowledge.md").write_text(
            "# Knowledge\nTest content.", encoding="utf-8"
        )

        result = load_knowledge("test_co")
        assert "Test content." in result

    def test_should_reindex_no_knowledge(self, tmp_path, monkeypatch):
        import core.memory.indexer as idx_mod
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)
        monkeypatch.setattr(idx_mod, "COMPANY_ROOT", tmp_path)

        company_dir = tmp_path / "test_co"
        company_dir.mkdir()

        # Mock decision count > 0
        monkeypatch.setattr(idx_mod, "_count_decisions", lambda cid: 3)

        # No knowledge.md + decisions exist = should reindex
        assert should_reindex("test_co", {}) is True

    def test_should_reindex_below_threshold(self, tmp_path, monkeypatch):
        import core.memory.indexer as idx_mod
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)
        monkeypatch.setattr(idx_mod, "COMPANY_ROOT", tmp_path)

        company_dir = tmp_path / "test_co"
        company_dir.mkdir()
        (company_dir / "knowledge.md").write_text("existing", encoding="utf-8")
        (company_dir / "index_meta.json").write_text(
            json.dumps({"last_indexed_decision_count": 3}), encoding="utf-8"
        )

        monkeypatch.setattr(idx_mod, "_count_decisions", lambda cid: 5)

        # 5 - 3 = 2, below default threshold of 5
        assert should_reindex("test_co", {}) is False

    def test_should_reindex_above_threshold(self, tmp_path, monkeypatch):
        import core.memory.indexer as idx_mod
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)
        monkeypatch.setattr(idx_mod, "COMPANY_ROOT", tmp_path)

        company_dir = tmp_path / "test_co"
        company_dir.mkdir()
        (company_dir / "knowledge.md").write_text("existing", encoding="utf-8")
        (company_dir / "index_meta.json").write_text(
            json.dumps({"last_indexed_decision_count": 3}), encoding="utf-8"
        )

        monkeypatch.setattr(idx_mod, "_count_decisions", lambda cid: 10)

        # 10 - 3 = 7, above default threshold of 5
        assert should_reindex("test_co", {}) is True
