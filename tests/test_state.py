"""
tests/test_state.py

Tests for core/state.py — state schema validation.
"""

import operator
from typing import get_type_hints
from core.state import CompanyState, AgentOutput, Decision


class TestCompanyState:
    def test_has_required_fields(self):
        fields = CompanyState.__annotations__
        required = [
            "company_id", "company_name", "company_config",
            "session_id", "session_start",
            "current_task", "agenda", "task_context",
            "relevant_memories", "prior_decision_found", "debate_round",
            "agent_outputs", "ceo_synthesis", "conflicts_identified",
            "consensus_reached", "escalate_to_human", "escalation_reason",
            "human_decision", "messages", "decisions_made", "worker_results",
        ]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    def test_agent_outputs_is_annotated_with_add(self):
        hints = get_type_hints(CompanyState, include_extras=True)
        agent_outputs = hints["agent_outputs"]
        assert hasattr(agent_outputs, "__metadata__")
        assert agent_outputs.__metadata__[0] is operator.add

    def test_messages_is_annotated_with_add(self):
        hints = get_type_hints(CompanyState, include_extras=True)
        messages = hints["messages"]
        assert hasattr(messages, "__metadata__")
        assert messages.__metadata__[0] is operator.add


class TestAgentOutput:
    def test_can_create(self):
        output = AgentOutput(
            agent="cfo",
            analysis="Test analysis",
            recommendation="proceed",
            concerns=["concern 1"],
            confidence=0.85,
        )
        assert output["agent"] == "cfo"
        assert output["confidence"] == 0.85


class TestDecision:
    def test_can_create(self):
        d = Decision(
            decision_id="test-123",
            session_id="sess-456",
            task="Test task",
            outcome="approved",
            reasoning="Good idea",
            votes={"cfo": "proceed"},
            human_override=None,
            timestamp="2026-01-01T00:00:00",
        )
        assert d["task"] == "Test task"
