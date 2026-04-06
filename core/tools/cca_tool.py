"""
core/tools/cca_tool.py

Direct invocation wrapper for the Claude Code Agent.
Kept for backwards compatibility — spawn_workers uses the
worker registry, but this can be called standalone.
"""

from core.agents.cca import CCAAgent


def invoke_cca(company_config: dict, task: str) -> dict:
    agent = CCAAgent(company_config)
    return agent.execute(task)
