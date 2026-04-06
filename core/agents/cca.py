"""
core/agents/cca.py

Claude Code Agent (CCA) — a worker that executes implementation tasks
by spawning a local Claude Code subprocess backed by Ollama.

Required config.json field:
    codebase_path — absolute path to the codebase this company manages.
                    If missing or empty, spawn_workers skips CCA silently.
                    If present but not a valid directory, raises ValueError.
"""

import json
import os
import subprocess
from pathlib import Path

from core.agents.base_worker import BaseWorker


class CCAAgent(BaseWorker):

    role  = "cca"
    title = "Claude Code Agent"
    keywords = [
        "code", "implement", "build", "develop", "deploy", "write code",
        "create file", "set up", "configure", "install", "migrate",
        "refactor", "fix bug", "patch", "launch", "repository",
    ]

    def __init__(self, company_config: dict):
        super().__init__(company_config)
        self.model = company_config.get("model_name", "gpt-oss:20b")

        codebase_path = company_config.get("codebase_path", "")
        if not codebase_path:
            raise ValueError(
                f"CCAAgent requires 'codebase_path' in company config for "
                f"'{self.company}'. Set it to the absolute path of the "
                f"codebase this company manages."
            )
        self.codebase_path = Path(codebase_path)
        if not self.codebase_path.is_dir():
            raise ValueError(
                f"codebase_path '{codebase_path}' does not exist or is not "
                f"a directory."
            )

    def execute(self, task: str) -> dict:
        env = os.environ.copy()
        env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
        env["ANTHROPIC_API_KEY"] = ""
        env["ANTHROPIC_BASE_URL"] = "http://localhost:11434"
        env["OLLAMA_CONTEXT_LENGTH"] = "65536"

        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
            "--model", self.model,
            "--prompt", task,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.codebase_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )

            output = result.stdout or ""
            stderr = result.stderr or ""

            if result.returncode != 0:
                return {
                    "worker":        self.role,
                    "success":       False,
                    "summary":       f"Claude Code exited with code {result.returncode}.",
                    "files_changed": [],
                    "output":        f"STDOUT:\n{output}\n\nSTDERR:\n{stderr}",
                }

            return self._parse_output(output)

        except subprocess.TimeoutExpired:
            return {
                "worker": self.role, "success": False,
                "summary": "Claude Code timed out after 10 minutes.",
                "files_changed": [], "output": "",
            }
        except FileNotFoundError:
            return {
                "worker": self.role, "success": False,
                "summary": "Claude Code CLI not found. Is it installed and on PATH?",
                "files_changed": [], "output": "",
            }
        except Exception as e:
            return {
                "worker": self.role, "success": False,
                "summary": f"CCA execution failed: {e}",
                "files_changed": [], "output": "",
            }

    def _parse_output(self, raw: str) -> dict:
        result_text = ""
        files_changed = set()

        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                result_text += line + "\n"
                continue

            msg_type = msg.get("type", "")
            if msg_type == "result":
                result_text = msg.get("result", result_text)
            elif msg_type == "assistant":
                for block in msg.get("content", []):
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            result_text = block.get("text", "")
                        elif block.get("type") == "tool_use":
                            inp = block.get("input", {})
                            if isinstance(inp, dict):
                                for key in ("file_path", "path"):
                                    val = inp.get(key, "")
                                    if val:
                                        files_changed.add(str(val))

        if not result_text:
            result_text = raw[:2000] if raw else "No output captured."

        return {
            "worker":        self.role,
            "success":       True,
            "summary":       result_text[:2000],
            "files_changed": sorted(files_changed),
            "output":        raw[:5000],
        }
