"""
tests/test_config.py

Tests for core/config.py — tunables, agent prompt loading, path config.
"""

import os
import pytest
from pathlib import Path
from core.config import get_tunable, load_agent_prompt, DEFAULTS


class TestGetTunable:
    def test_returns_default_when_key_missing(self):
        assert get_tunable({}, "chat_history_length") == 20

    def test_returns_config_value_when_present(self):
        assert get_tunable({"chat_history_length": 50}, "chat_history_length") == 50

    def test_config_overrides_default(self):
        assert get_tunable({"max_debate_rounds": 5}, "max_debate_rounds") == 5

    def test_unknown_key_returns_none(self):
        assert get_tunable({}, "nonexistent_key") is None

    def test_all_defaults_exist(self):
        expected_keys = [
            "chat_history_length", "chat_message_cap", "cca_max_turns",
            "worker_max_tokens", "ceo_chat_max_tokens", "knowledge_max_pct",
            "max_debate_rounds",
        ]
        for key in expected_keys:
            assert key in DEFAULTS, f"Missing default: {key}"


class TestLoadAgentPrompt:
    def test_fallback_to_config_json(self):
        config = {"agent_personalities": {"cfo": "Test CFO personality."}}
        prompt = load_agent_prompt("nonexistent_company", "cfo", config)
        assert prompt == "Test CFO personality."

    def test_fallback_to_generic_when_no_config(self):
        prompt = load_agent_prompt("nonexistent_company", "cfo", {})
        assert "CFO" in prompt

    def test_loads_from_file(self, tmp_path, monkeypatch):
        # Create a temporary prompt file
        company_dir = tmp_path / "test_co" / "prompts"
        company_dir.mkdir(parents=True)
        prompt_file = company_dir / "cfo.md"
        prompt_file.write_text("You are an elite CFO.", encoding="utf-8")

        # Monkeypatch COMPANY_ROOT to use tmp_path
        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)

        prompt = load_agent_prompt("test_co", "cfo", {})
        assert prompt == "You are an elite CFO."

    def test_file_takes_priority_over_config(self, tmp_path, monkeypatch):
        company_dir = tmp_path / "test_co" / "prompts"
        company_dir.mkdir(parents=True)
        (company_dir / "cfo.md").write_text("File prompt.", encoding="utf-8")

        import core.config
        monkeypatch.setattr(core.config, "COMPANY_ROOT", tmp_path)

        config = {"agent_personalities": {"cfo": "Config prompt."}}
        prompt = load_agent_prompt("test_co", "cfo", config)
        assert prompt == "File prompt."
