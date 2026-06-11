"""
core/agents/cwa.py

Content Writer Agent (CWA) — a worker that drafts written content
after C-suite approval: blog posts, game descriptions, social media
copy, newsletter content, press releases, documentation, etc.

Non-interactive. Uses the company's configured LLM to generate content
based on the task briefing and company DNA.
"""

from pathlib import Path

from core.agents.base_worker import BaseWorker
from core.agents.base import build_llm, invoke_llm


class CWAAgent(BaseWorker):

    role        = "cwa"
    title       = "Content Writer Agent"
    interactive = False
    keywords    = [
        "write", "draft", "blog", "post", "copy", "content",
        "newsletter", "press release", "description", "article",
        "announcement", "documentation", "readme", "guide",
        # Document-shaped requests that aren't code:
        "document", "memo", "brief", "plan", "proposal", "spec",
        "goal", "strategy", "outline", "summary",
    ]

    def __init__(self, company_config: dict):
        super().__init__(company_config)
        from core.config import get_tunable
        self.llm = build_llm(company_config, temperature=0.8,
                             max_tokens=get_tunable(company_config, "worker_max_tokens"))
        self.config = company_config

    def build_prompt(self, task: str) -> str:
        company_name = self.config.get("company_name", "the company")
        industry = self.config.get("industry", "")
        mission = self.config.get("mission", "")
        personality = (
            self.config.get("agent_personalities", {})
                       .get("cmo", "")
        )

        return (
            f"You are a professional content writer for {company_name}, "
            f"a company in {industry}.\n\n"
            f"Company mission: {mission}\n\n"
            f"Brand voice guidance: {personality}\n\n"
            f"--- TASK ---\n\n"
            f"{task}\n\n"
            f"--- INSTRUCTIONS ---\n\n"
            f"Write the requested content. Match the company's brand voice. "
            f"Be specific, engaging, and ready to publish with minimal editing. "
            f"If the task asks for multiple pieces (e.g. several social posts), "
            f"produce all of them clearly separated.\n\n"
            f"Output the content directly — no preamble or meta-commentary."
        )

    def execute(self, task: str) -> dict:
        try:
            content = invoke_llm(self.llm, self.build_prompt(task))
        except Exception as e:
            return {
                "worker":  self.role,
                "success": False,
                "summary": f"Content generation failed: {e}",
                "output":  "",
            }

        artifact = ""
        try:
            artifact = str(self.write_artifact(task, content))
        except Exception as e:
            # Saving failed (path/perm issue, missing company_id). Don't
            # lose the content — return it in `output` so the caller can
            # still surface it; just flag the save error in the summary.
            return {
                "worker":   self.role,
                "success":  True,
                "summary":  f"Content drafted ({len(content)} chars) — "
                            f"save failed: {e}",
                "output":   content,
                "artifact": "",
            }

        return {
            "worker":   self.role,
            "success":  True,
            "summary":  f"Content drafted ({len(content)} chars) — "
                        f"saved to {Path(artifact).name}",
            "output":   content,
            "artifact": artifact,
        }
