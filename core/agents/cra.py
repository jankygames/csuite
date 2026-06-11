"""
core/agents/cra.py

Research Agent (CRA) — a worker that performs analysis and research
after C-suite approval: competitive analysis, market research, pricing
studies, technology evaluations, audience analysis, etc.

Non-interactive. Performs web searches for live data, then uses the
company's configured LLM to synthesize findings into a structured report.
"""

import httpx
import re

from pathlib import Path

from core.agents.base_worker import BaseWorker
from core.agents.base import build_llm, invoke_llm


class CRAAgent(BaseWorker):

    role        = "cra"
    title       = "Research Agent"
    interactive = False
    keywords    = [
        "research", "analyze", "analysis", "compare", "competitive",
        "market", "pricing", "evaluate", "study", "investigate",
        "benchmark", "survey", "report", "assess", "review",
    ]

    def __init__(self, company_config: dict):
        super().__init__(company_config)
        from core.config import get_tunable
        self.llm = build_llm(company_config, temperature=0.4,
                             max_tokens=get_tunable(company_config, "worker_max_tokens"))
        self.config = company_config

    def build_prompt(self, task: str) -> str:
        company_name = self.config.get("company_name", "the company")
        industry = self.config.get("industry", "")
        mission = self.config.get("mission", "")
        priorities = self.config.get("strategic_priorities", [])
        constraints = self.config.get("constraints", [])

        priorities_text = "\n".join(f"- {p}" for p in priorities) if priorities else "None specified"
        constraints_text = "\n".join(f"- {c}" for c in constraints) if constraints else "None specified"

        return (
            f"You are a research analyst working for {company_name}, "
            f"a company in {industry}.\n\n"
            f"Company mission: {mission}\n"
            f"Strategic priorities:\n{priorities_text}\n"
            f"Constraints:\n{constraints_text}\n\n"
            f"--- RESEARCH TASK ---\n\n"
            f"{task}\n\n"
            f"--- INSTRUCTIONS ---\n\n"
            f"Produce a structured research report. Include:\n"
            f"1. **Executive Summary** — key findings in 2-3 sentences\n"
            f"2. **Findings** — detailed analysis organized by topic\n"
            f"3. **Recommendations** — actionable next steps tied to findings\n"
            f"4. **Risks & Unknowns** — what you couldn't determine or what needs validation\n\n"
            f"Be specific and factual. Clearly distinguish between established "
            f"facts, reasonable inferences, and speculation. If you don't have "
            f"enough information on a point, say so rather than guessing."
        )

    def execute(self, task: str) -> dict:
        # Gather web search results for context
        search_context = self._web_search(task)
        prompt = self.build_prompt(task)
        if search_context:
            prompt += (
                f"\n\n--- WEB SEARCH RESULTS ---\n"
                f"The following are real search results gathered for this task. "
                f"Use them to ground your analysis in current data. Cite sources "
                f"when referencing specific findings.\n\n"
                f"{search_context}"
            )

        try:
            findings = invoke_llm(self.llm, prompt)
        except Exception as e:
            return {
                "worker":  self.role,
                "success": False,
                "summary": f"Research failed: {e}",
                "output":  "",
            }

        artifact = ""
        try:
            artifact = str(self.write_artifact(task, findings))
        except Exception as e:
            return {
                "worker":   self.role,
                "success":  True,
                "summary":  f"Research report generated ({len(findings)} "
                            f"chars) — save failed: {e}",
                "output":   findings,
                "artifact": "",
            }

        return {
            "worker":   self.role,
            "success":  True,
            "summary":  f"Research report generated ({len(findings)} chars) "
                        f"— saved to {Path(artifact).name}",
            "output":   findings,
            "artifact": artifact,
        }

    @staticmethod
    def _web_search(query: str, max_results: int = 8) -> str:
        """
        Search DuckDuckGo for relevant results. Returns formatted text
        with titles, URLs, and snippets. No API key needed.
        Falls back gracefully if search fails.
        """
        try:
            # Extract key terms from the task for a focused search
            search_query = " ".join(query.split()[:15])

            resp = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": search_query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                follow_redirects=True,
            )

            if resp.status_code != 200:
                return ""

            html = resp.text
            results = []

            # Parse results from DuckDuckGo HTML
            # Each result is in a div with class "result"
            result_blocks = re.findall(
                r'<a rel="nofollow" class="result__a" href="([^"]*)"[^>]*>(.*?)</a>'
                r'.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )

            for url, title, snippet in result_blocks[:max_results]:
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                if title and snippet:
                    results.append(f"**{title}**\n{url}\n{snippet}\n")

            return "\n".join(results) if results else ""

        except Exception:
            return ""
