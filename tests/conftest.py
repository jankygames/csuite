"""
tests/conftest.py

Shared fixtures for the test suite.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_config():
    """A minimal company config dict for testing."""
    return {
        "company_id":   "test_company",
        "company_name": "Test Corp",
        "industry":     "Software",
        "stage":        "early",
        "founded":      "2024",
        "mission":      "Test mission.",
        "strategic_priorities": ["Priority 1", "Priority 2"],
        "constraints":  ["Constraint 1"],
        "risk_profile": "moderate",
        "decision_style": "data-driven",
        "model_provider":  "ollama",
        "model_name":      "gpt-oss:20b",
        "context_length":  32768,
        "escalation_rules": {
            "always_escalate": ["Any spend over $1000"],
            "escalate_if_deadlock": True,
            "ceo_can_decide_alone": ["Minor decisions"],
        },
        "agent_personalities": {
            "ceo": "Decisive CEO.",
            "cfo": "Conservative CFO.",
            "coo": "Execution-focused COO.",
            "cmo": "Customer-first CMO.",
            "cto": "Pragmatic CTO.",
        },
        "codebase_path": "",
        "indexer_model": "",
        "index_threshold": 5,
        "index_version_days": 7,
        "chat_history_length": 20,
        "chat_message_cap": 10000,
        "cca_max_turns": 50,
        "worker_max_tokens": 4096,
        "ceo_chat_max_tokens": 2048,
        "knowledge_max_pct": 50,
        "max_debate_rounds": 2,
    }


@pytest.fixture
def sample_state(sample_config):
    """A minimal CompanyState dict for testing node functions."""
    return {
        "company_id":           "test_company",
        "company_name":         "Test Corp",
        "company_config":       sample_config,
        "current_task":         "Should we launch a new product?",
        "task_context":         "",
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


@pytest.fixture
def temp_db(tmp_path):
    """
    Create a temporary SQLite database with the full schema.
    Returns (db_path, company_id).
    """
    company_id = "test_company"
    db_dir = tmp_path / company_id
    db_dir.mkdir()
    db_path = db_dir / f"{company_id}.db"

    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, company_id TEXT NOT NULL,
                started_at TEXT NOT NULL, ended_at TEXT,
                task_count INTEGER DEFAULT 0, outcome_summary TEXT
            );
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                company_id TEXT NOT NULL, task TEXT NOT NULL,
                outcome TEXT, reasoning TEXT, escalated INTEGER DEFAULT 0,
                human_override TEXT, decided_at TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL, agent TEXT NOT NULL,
                recommendation TEXT NOT NULL, analysis TEXT,
                concerns TEXT, confidence REAL
            );
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT NOT NULL, category TEXT,
                title TEXT NOT NULL, content TEXT NOT NULL,
                source TEXT, added_at TEXT, chroma_id TEXT
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS worker_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT NOT NULL, worker TEXT NOT NULL,
                task TEXT NOT NULL, success INTEGER NOT NULL,
                summary TEXT, output TEXT, created_at TEXT NOT NULL
            );
        """)

    return db_path, company_id
