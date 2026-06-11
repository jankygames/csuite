"""
core/agents/base_worker.py

Abstract base class for all worker-tier agents.

Workers sit below the C-suite. They are invoked after human approval
to execute concrete tasks — coding, writing, research, comms, art, etc.

Every worker must define:
    role      (str)       — short identifier, e.g. "cca"
    title     (str)       — display name, e.g. "Claude Code Agent"
    keywords  (list[str]) — words that trigger this worker when found
                            in the CEO synthesis or task text

Every worker must implement:
    execute(task: str) -> dict
        Returns at minimum: {worker, success, summary, output}
        Workers may add extra keys (e.g. files_changed for CCA).

Workers may set:
    interactive (bool) — if True, the worker manages a multi-turn session
        with the user through the UI. The graph flags it as pending and
        the UI layer (app.py) handles the conversation loop. Default: False.

To add a new worker:
    1. Create core/agents/<name>.py with a class extending BaseWorker
    2. Add it to WORKER_AGENTS in core/agents/__init__.py
    That's it — spawn_workers will pick it up automatically.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseWorker(ABC):

    role:        str
    title:       str
    keywords:    list[str]
    interactive: bool = False

    def __init__(self, company_config: dict):
        self.config = company_config
        self.company = company_config.get("company_name", "the company")
        self.company_id = company_config.get("company_id", "")

    def write_artifact(self, task: str, content: str,
                       ext: str = "md") -> Path:
        """Save worker output as a real file under the company's documents
        directory. Filename is <UTC-stamp>-<slug>.<ext> where the slug is
        derived from the first ~6 words of the task. Returns the absolute
        path written. Requires `company_id` to be present in self.config —
        injected by the app/server when the company is loaded."""
        from datetime import datetime, timezone
        import re
        from core.config import documents_dir

        if not self.company_id:
            raise ValueError(
                "write_artifact requires company_id in the worker's config; "
                "the loader should inject it. See _load_company in app.py."
            )

        words = (task or "").lower().split()[:6]
        slug = re.sub(r"[^a-z0-9]+", "-", " ".join(words)).strip("-")[:60]
        slug = slug or "untitled"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        out_dir = documents_dir(self.company_id, self.config)
        path = out_dir / f"{stamp}-{self.role}-{slug}.{ext}"
        path.write_text(content, encoding="utf-8")
        return path

    @abstractmethod
    def execute(self, task: str) -> dict:
        """
        Execute a task and return a result dict.

        Required keys in the returned dict:
            worker  (str)       — self.role
            success (bool)      — whether the task completed
            summary (str)       — human-readable description of what happened
            output  (str)       — raw output for debugging/logging

        Workers may add additional keys relevant to their domain.
        """

    def build_prompt(self, task: str) -> str:
        """
        Build the prompt for this worker. Override in subclasses to
        customize. Returns the prompt string. Used by stream_execute()
        to stream output instead of returning it all at once.
        Default returns empty string (subclass should override if streaming
        is desired).
        """
        return ""

    def can_handle(self, text: str) -> bool:
        """
        Returns True if this worker's keywords match the given text.
        Used by spawn_workers to decide which workers to invoke.
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.keywords)
