"""
tests/test_agents.py

Tests for agent registries, base classes, and LLM factory.
"""

import pytest
from core.agents import (
    CEOAgent, CFOAgent, COOAgent, CMOAgent, CTOAgent,
    CCAAgent, CWAAgent, CRAAgent, CSAAgent,
    CSUITE_AGENTS, WORKER_AGENTS, BaseWorker,
)
from core.agents.base import (
    build_llm, invoke_llm, stream_llm,
    DEFAULT_OLLAMA_MODEL, DEFAULT_ANTHROPIC_MODEL,
    VALID_RECOMMENDATIONS, BaseAgent,
)
from core.agents.base_worker import BaseWorker


class TestAgentRegistries:
    def test_csuite_agents_not_empty(self):
        assert len(CSUITE_AGENTS) >= 4

    def test_worker_agents_not_empty(self):
        assert len(WORKER_AGENTS) >= 4

    def test_csuite_agents_have_roles(self):
        roles = {a.role for a in CSUITE_AGENTS}
        assert "cfo" in roles
        assert "coo" in roles
        assert "cmo" in roles
        assert "cto" in roles

    def test_worker_agents_have_roles(self):
        roles = {w.role for w in WORKER_AGENTS}
        assert "cca" in roles
        assert "cwa" in roles
        assert "cra" in roles
        assert "csa" in roles

    def test_ceo_not_in_csuite_agents(self):
        """CEO synthesizes, doesn't deliberate."""
        roles = {a.role for a in CSUITE_AGENTS}
        assert "ceo" not in roles

    def test_all_csuite_extend_base_agent(self):
        for AgentClass in CSUITE_AGENTS:
            assert issubclass(AgentClass, BaseAgent)

    def test_all_workers_extend_base_worker(self):
        for WorkerClass in WORKER_AGENTS:
            assert issubclass(WorkerClass, BaseWorker)


class TestBaseWorker:
    def test_keywords_not_empty(self):
        for WorkerClass in WORKER_AGENTS:
            assert len(WorkerClass.keywords) > 0, \
                f"{WorkerClass.role} has no keywords"

    def test_can_handle_matches_keywords(self):
        cwa = CWAAgent.__new__(CWAAgent)
        cwa.keywords = CWAAgent.keywords
        assert cwa.can_handle("draft a blog post")
        assert not cwa.can_handle("fix the database")

    def test_interactive_flag(self):
        assert CCAAgent.interactive is True
        assert CWAAgent.interactive is False
        assert CRAAgent.interactive is False
        assert CSAAgent.interactive is False

    def test_build_prompt_returns_string(self, sample_config):
        for WorkerClass in [CWAAgent, CRAAgent, CSAAgent]:
            worker = WorkerClass(sample_config)
            prompt = worker.build_prompt("test task")
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestBuildLlm:
    def test_default_ollama(self, sample_config):
        llm = build_llm(sample_config)
        assert type(llm).__name__ == "OllamaLLM"

    def test_custom_model_name(self):
        config = {"model_provider": "ollama", "model_name": "llama3:8b"}
        llm = build_llm(config)
        assert llm.model == "llama3:8b"

    def test_default_model_name(self):
        llm = build_llm({})
        assert llm.model == DEFAULT_OLLAMA_MODEL

    def test_context_length_applied(self):
        config = {"context_length": 65536}
        llm = build_llm(config)
        assert llm.num_ctx == 65536

    def test_anthropic_provider(self):
        config = {"model_provider": "anthropic"}
        llm = build_llm(config)
        assert type(llm).__name__ == "ChatAnthropic"


class TestResponseParsing:
    def test_parse_valid_json(self, sample_config):
        agent = CFOAgent(sample_config)
        result = agent._parse_response(
            '{"analysis": "Test", "recommendation": "proceed", '
            '"concerns": ["c1"], "confidence": 0.8}'
        )
        assert result["recommendation"] == "proceed"
        assert result["confidence"] == 0.8

    def test_parse_with_markdown_fences(self, sample_config):
        agent = CFOAgent(sample_config)
        result = agent._parse_response(
            '```json\n{"analysis": "Test", "recommendation": "modify", '
            '"concerns": [], "confidence": 0.5}\n```'
        )
        assert result["recommendation"] == "modify"

    def test_parse_invalid_recommendation_fuzzy(self, sample_config):
        agent = CFOAgent(sample_config)
        result = agent._parse_response(
            '{"analysis": "Test", "recommendation": "I recommend we proceed", '
            '"concerns": [], "confidence": 0.5}'
        )
        assert result["recommendation"] == "proceed"

    def test_parse_clamps_confidence(self, sample_config):
        agent = CFOAgent(sample_config)
        result = agent._parse_response(
            '{"analysis": "Test", "recommendation": "block", '
            '"concerns": [], "confidence": 1.5}'
        )
        assert result["confidence"] == 1.0

    def test_parse_failure_raises(self, sample_config):
        agent = CFOAgent(sample_config)
        with pytest.raises(ValueError):
            agent._parse_response("not json at all")

    def test_fallback_output(self, sample_config):
        agent = CFOAgent(sample_config)
        result = agent._fallback_output("raw text", "parse error")
        assert result["recommendation"] == "modify"
        assert result["confidence"] == 0.0
        assert "PARSE FAILURE" in result["analysis"]


class TestCCAAgent:
    def test_requires_codebase_path(self, sample_config):
        with pytest.raises(ValueError, match="codebase_path"):
            CCAAgent(sample_config)

    def test_requires_valid_directory(self, sample_config):
        sample_config["codebase_path"] = "/nonexistent/path"
        with pytest.raises(ValueError, match="does not exist"):
            CCAAgent(sample_config)

    def test_accepts_valid_path(self, sample_config, tmp_path):
        sample_config["codebase_path"] = str(tmp_path)
        agent = CCAAgent(sample_config)
        assert agent.codebase_path == tmp_path
