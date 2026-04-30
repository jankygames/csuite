"""
tests/test_edges.py

Tests for core/graph/edges.py — all conditional routing functions.
"""

from core.graph.edges import (
    prior_decision_router,
    conflict_router,
    human_decision_router,
)


class TestPriorDecisionRouter:
    def test_already_decided(self):
        state = {"prior_decision_found": True}
        assert prior_decision_router(state) == "already_decided"

    def test_new_topic(self):
        state = {"prior_decision_found": False}
        assert prior_decision_router(state) == "deliberate"

    def test_missing_key_defaults_to_deliberate(self):
        assert prior_decision_router({}) == "deliberate"


class TestConflictRouter:
    def test_consensus_reached(self):
        state = {"consensus_reached": True, "debate_round": 1, "company_config": {}}
        assert conflict_router(state) == "resolved"

    def test_deadlocked_round_1(self):
        state = {"consensus_reached": False, "debate_round": 1, "company_config": {}}
        assert conflict_router(state) == "deadlocked"

    def test_deadlocked_round_2(self):
        state = {"consensus_reached": False, "debate_round": 2, "company_config": {}}
        assert conflict_router(state) == "deadlocked"

    def test_escalate_after_max_rounds(self):
        state = {"consensus_reached": False, "debate_round": 3, "company_config": {}}
        assert conflict_router(state) == "escalate"

    def test_custom_max_rounds(self):
        state = {
            "consensus_reached": False,
            "debate_round": 3,
            "company_config": {"max_debate_rounds": 3},
        }
        assert conflict_router(state) == "deadlocked"

    def test_custom_max_rounds_escalate(self):
        state = {
            "consensus_reached": False,
            "debate_round": 4,
            "company_config": {"max_debate_rounds": 3},
        }
        assert conflict_router(state) == "escalate"


class TestHumanDecisionRouter:
    def test_approve_finalizes(self):
        state = {"human_decision": "approve"}
        assert human_decision_router(state) == "finalize"

    def test_implement_finalizes(self):
        state = {"human_decision": "implement the feature"}
        assert human_decision_router(state) == "finalize"

    def test_override_finalizes(self):
        state = {"human_decision": "override: do something else"}
        assert human_decision_router(state) == "finalize"

    def test_more_info_reconsiders(self):
        state = {"human_decision": "more info: we have new data"}
        assert human_decision_router(state) == "reconsider"

    def test_more_info_case_insensitive(self):
        state = {"human_decision": "More Info the budget changed"}
        assert human_decision_router(state) == "reconsider"

    def test_empty_decision_finalizes(self):
        state = {"human_decision": ""}
        assert human_decision_router(state) == "finalize"

    def test_none_decision_finalizes(self):
        state = {"human_decision": None}
        assert human_decision_router(state) == "finalize"
