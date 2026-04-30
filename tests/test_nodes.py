"""
tests/test_nodes.py

Tests for graph node functions (via the hub and sub-modules).
"""

import pytest
from core.graph.nodes import (
    set_progress_callback,
    _worker_matches,
)
from core.graph.node_utils import (
    build_agent_briefing,
    extract_owner_directions,
)
from core.graph.deliberation_nodes import (
    task_intake,
    reconsider_with_info,
)
from core.graph.worker_nodes import (
    spawn_workers,
    worker_matches,
)
from core.agents import WORKER_AGENTS


class TestTaskIntake:
    def test_initializes_session_fields(self, sample_state):
        result = task_intake(sample_state)
        assert result["session_id"] != ""
        assert result["session_start"] != ""
        assert result["debate_round"] == 1
        assert result["consensus_reached"] is False
        assert result["agent_outputs"] == []

    def test_session_id_is_unique(self, sample_state):
        r1 = task_intake(sample_state)
        r2 = task_intake(sample_state)
        assert r1["session_id"] != r2["session_id"]


class TestReconsiderWithInfo:
    def test_extracts_new_info(self, sample_state):
        sample_state["human_decision"] = "more info: budget is now $10k"
        result = reconsider_with_info(sample_state)
        assert "budget is now $10k" in result["task_context"]
        assert result["debate_round"] == 1
        assert result["consensus_reached"] is False

    def test_appends_to_existing_context(self, sample_state):
        sample_state["task_context"] = "existing context"
        sample_state["human_decision"] = "more info: new data"
        result = reconsider_with_info(sample_state)
        assert "existing context" in result["task_context"]
        assert "new data" in result["task_context"]


class TestWorkerMatches:
    def test_cwa_matches_draft(self):
        from core.agents.cwa import CWAAgent
        assert worker_matches(CWAAgent, "draft a blog post")

    def test_cwa_no_match_code(self):
        from core.agents.cwa import CWAAgent
        assert not worker_matches(CWAAgent, "fix the database query")

    def test_cra_matches_research(self):
        from core.agents.cra import CRAAgent
        assert worker_matches(CRAAgent, "research competitive pricing")

    def test_csa_matches_social(self):
        from core.agents.csa import CSAAgent
        assert worker_matches(CSAAgent, "post to discord about the launch")

    def test_cca_matches_code(self):
        from core.agents.cca import CCAAgent
        assert worker_matches(CCAAgent, "fix bug in the frontend code")

    def test_cca_no_match_blog(self):
        from core.agents.cca import CCAAgent
        assert not worker_matches(CCAAgent, "draft a blog post")


class TestSpawnWorkers:
    def test_skips_when_not_implement(self, sample_state):
        sample_state["human_decision"] = "approve"
        result = spawn_workers(sample_state)
        assert result == {}

    def test_skips_when_no_match(self, sample_state):
        sample_state["human_decision"] = "implement something very vague"
        result = spawn_workers(sample_state)
        assert result == {} or result.get("worker_results") == []


class TestBuildAgentBriefing:
    def test_includes_company_and_task(self, sample_state):
        briefing = build_agent_briefing(sample_state, False, 1)
        assert "Test Corp" in briefing
        assert "launch a new product" in briefing

    def test_includes_knowledge(self, sample_state):
        sample_state["relevant_memories"] = [{
            "source": "distilled_knowledge",
            "reasoning": "Prior knowledge content here.",
            "task": "", "outcome": "", "human_override": "",
            "similarity_score": None,
        }]
        briefing = build_agent_briefing(sample_state, False, 1)
        assert "Prior knowledge content here." in briefing

    def test_includes_owner_directions(self, sample_state):
        sample_state["messages"] = [
            {"role": "user", "content": "We decided to proceed."},
        ]
        briefing = build_agent_briefing(sample_state, False, 1)
        assert "We decided to proceed." in briefing

    def test_includes_prior_outputs_when_requested(self, sample_state):
        sample_state["agent_outputs"] = [{
            "agent": "cfo", "analysis": "Financial analysis.",
            "recommendation": "proceed", "concerns": [], "confidence": 0.8,
        }]
        briefing = build_agent_briefing(sample_state, True, 1)
        assert "Financial analysis." in briefing

    def test_excludes_prior_outputs_when_not_requested(self, sample_state):
        sample_state["agent_outputs"] = [{
            "agent": "cfo", "analysis": "Financial analysis.",
            "recommendation": "proceed", "concerns": [], "confidence": 0.8,
        }]
        briefing = build_agent_briefing(sample_state, False, 1)
        assert "Financial analysis." not in briefing

    def test_includes_conflicts_in_round_2(self, sample_state):
        sample_state["conflicts_identified"] = ["CFO vs CMO on pricing"]
        briefing = build_agent_briefing(sample_state, False, 2)
        assert "CFO vs CMO on pricing" in briefing

    def test_no_conflicts_in_round_1(self, sample_state):
        sample_state["conflicts_identified"] = ["CFO vs CMO on pricing"]
        briefing = build_agent_briefing(sample_state, False, 1)
        assert "CFO vs CMO on pricing" not in briefing


class TestExtractOwnerDirections:
    def test_extracts_user_messages(self):
        state = {"messages": [
            {"role": "user", "content": "Do it."},
            {"role": "assistant", "content": "OK."},
            {"role": "user", "content": "Also this."},
        ]}
        dirs = extract_owner_directions(state)
        assert dirs == ["Do it.", "Also this."]

    def test_empty_when_no_user_messages(self):
        state = {"messages": [{"role": "assistant", "content": "OK."}]}
        assert extract_owner_directions(state) == []

    def test_empty_when_no_messages(self):
        assert extract_owner_directions({}) == []


class TestProgressCallback:
    def test_set_and_clear(self):
        events = []
        set_progress_callback(lambda e, d: events.append((e, d)))
        from core.graph.node_utils import _notify
        _notify("test_event", key="value")
        assert len(events) == 1
        assert events[0][0] == "test_event"

        set_progress_callback(None)
        _notify("test_event2")
        assert len(events) == 1  # no new event
