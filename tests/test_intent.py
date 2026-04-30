"""
tests/test_intent.py

Tests for intent classification (keyword fast-path in app.py).
"""

import sys
sys.path.insert(0, "D:/csuite")

from app import _classify_intent


class TestIntentClassification:
    """Test the keyword fast-path classifier."""

    def test_implement_prefix(self):
        assert _classify_intent("implement build a page") == "implement"

    def test_implement_alone(self):
        assert _classify_intent("implement") == "implement"

    def test_should_we_deliberates(self):
        assert _classify_intent("should we raise prices") == "deliberate"

    def test_lets_decide_deliberates(self):
        assert _classify_intent("lets decide on marketing") == "deliberate"

    def test_evaluate_whether_deliberates(self):
        assert _classify_intent("evaluate whether to hire") == "deliberate"

    def test_chat_is_default(self):
        """Ambiguous messages return None (deferred to LLM)."""
        result = _classify_intent("hello there")
        assert result is None

    def test_question_is_chat(self):
        result = _classify_intent("what did we decide")
        assert result is None  # deferred to LLM

    def test_case_insensitive(self):
        assert _classify_intent("IMPLEMENT something") == "implement"
        assert _classify_intent("Should We do this") == "deliberate"
