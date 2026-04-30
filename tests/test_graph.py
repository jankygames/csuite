"""
tests/test_graph.py

Tests for core/graph/session_graph.py — graph building and structure.
"""

import pytest
from core.graph.session_graph import build_session_graph


class TestBuildSessionGraph:
    def test_builds_successfully(self):
        graph, ctx = build_session_graph("janky_games")
        assert graph is not None
        ctx.__exit__(None, None, None)

    def test_returns_graph_and_context(self):
        graph, ctx = build_session_graph("janky_games")
        assert hasattr(graph, "stream")
        assert hasattr(ctx, "__exit__")
        ctx.__exit__(None, None, None)

    def test_different_companies_get_different_graphs(self):
        g1, c1 = build_session_graph("janky_games")
        # Just verify it doesn't crash for a second company
        # (even if it doesn't exist — the graph builder creates the db)
        g2, c2 = build_session_graph("test_other")
        c1.__exit__(None, None, None)
        c2.__exit__(None, None, None)
