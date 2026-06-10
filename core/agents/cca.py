"""
core/agents/cca.py

Claude Code Agent (CCA) — an interactive worker that executes implementation
tasks via the Claude Code Python SDK.

Supports multi-turn conversations: the user can review CCA's work and
send follow-up instructions within the same session.

Required config.json field:
    codebase_path — absolute path to the codebase this company manages.
"""

from pathlib import Path

from core.agents.base_worker import BaseWorker


# ── Subprocess leak prevention (Windows) ─────────────────────────────────────
#
# The Claude Code SDK uses anyio.open_process to spawn claude.cmd, whose
# real worker is a node.exe process underneath. On Windows, the SDK's
# transport.close() calls Process.terminate() — which kills the .cmd shim
# but not the node.exe child. After many sessions you end up with dozens
# of orphaned claude processes pinning ~370 MB each.
#
# These helpers snapshot the set of claude PIDs before a query and force-kill
# (taskkill /T /F) any new ones afterward. Pure stdlib; no psutil dependency.

def _snapshot_claude_pids() -> set[int]:
    """Return PIDs of every currently-running claude(.exe) process."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq claude.exe",
             "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW — no console flash
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return set()

    pids: set[int] = set()
    for line in out.splitlines():
        # CSV with quoted fields: "claude.exe","12345","Console","1","41,000 K"
        parts = line.split('","')
        if len(parts) >= 2:
            try:
                pids.add(int(parts[1].strip('"')))
            except ValueError:
                pass
    return pids


def _kill_new_claude_pids(baseline: set[int]) -> int:
    """Force-kill claude processes started after the baseline snapshot.

    Uses taskkill /T to take down the whole process tree (node.exe children
    included), /F to skip the "are you sure" dance. Returns kill count.
    """
    import subprocess
    new_pids = _snapshot_claude_pids() - baseline
    killed = 0
    for pid in new_pids:
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=0x08000000,
            )
            killed += 1
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
    return killed


class CCAAgent(BaseWorker):

    role        = "cca"
    title       = "Claude Code Agent"
    interactive = True
    keywords    = [
        "code", "codebase", "build app", "build page", "develop app",
        "deploy", "write code", "create file", "configure server",
        "install", "migrate", "refactor", "fix bug", "patch",
        "repository", "frontend", "backend", "api", "database",
        "script", "website", "landing page", "web page",
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
        """Sync fallback for non-interactive contexts (CLI runner)."""
        import asyncio
        messages, _ = asyncio.run(self.start_session(task))
        result_msg = next(
            (m for m in reversed(messages) if m["type"] == "result"), None
        )
        return {
            "worker":        self.role,
            "success":       not result_msg["is_error"] if result_msg else False,
            "summary":       result_msg["content"][:2000] if result_msg else "",
            "files_changed": [m.get("file", "") for m in messages
                              if m["type"] == "tool_use" and m.get("file")],
            "output":        "\n".join(m["content"] for m in messages
                                       if m.get("content")),
        }

    def _build_options(self, resume: str | None = None):
        from claude_code_sdk import ClaudeCodeOptions
        from core.config import get_tunable

        provider = self.config.get("model_provider", "ollama").lower()

        # Build environment variables based on model provider
        if provider == "ollama":
            env = {
                "ANTHROPIC_AUTH_TOKEN": "ollama",
                "ANTHROPIC_API_KEY": "",
                "ANTHROPIC_BASE_URL": "http://localhost:11434",
                "OLLAMA_CONTEXT_LENGTH": str(
                    self.config.get("context_length", 65536)
                ),
            }
        else:
            # Anthropic — use real API key from environment
            import os
            env = {}
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                env["ANTHROPIC_API_KEY"] = api_key

        opts = ClaudeCodeOptions(
            model=self.model,
            cwd=str(self.codebase_path),
            permission_mode="acceptEdits",
            max_turns=get_tunable(self.config, "cca_max_turns"),
            system_prompt=(
                f"You are a developer working on the codebase for {self.company}. "
                f"Your job is to IMPLEMENT — write code, create files, edit files, "
                f"and run commands. Do NOT ask clarifying questions unless something "
                f"is genuinely ambiguous. Do NOT present options or wait for approval. "
                f"Just start building. Read the existing codebase first to understand "
                f"the structure, then make the changes described in the task. "
                f"When done, summarize what you built and what files you changed."
            ),
            env=env,
        )
        if resume:
            opts.resume = resume
        return opts

    async def start_session(self, task: str,
                             on_message=None) -> tuple[list[dict], str]:
        """
        Start a new CCA session.

        Args:
            task: The implementation instruction.
            on_message: Optional async callback(msg_dict) called as each
                        message arrives, for real-time UI streaming.

        Returns (all_messages, session_id).
        """
        return await self._run_query(task, self._build_options(),
                                      on_message=on_message)

    async def continue_session(self, session_id: str, user_input: str,
                                on_message=None) -> tuple[list[dict], str]:
        """
        Continue an existing CCA session with user follow-up.
        Returns (all_messages, session_id).
        """
        return await self._run_query(
            user_input, self._build_options(resume=session_id),
            on_message=on_message,
        )

    @staticmethod
    async def _run_query(prompt, options, on_message=None):
        """
        Run a Claude Code SDK query. Yields parsed message dicts to
        on_message (if provided) as they arrive, and also collects
        them into a list returned at the end.

        Windows event-loop dodge: the SDK spawns claude.cmd via
        asyncio.create_subprocess_exec, which only works on the
        ProactorEventLoop. uvicorn picks the SelectorEventLoop whenever
        it runs with --reload or multiple workers (use_subprocess=True),
        and that combination raises NotImplementedError before claude
        ever starts. We always thread-jump into a fresh ProactorEventLoop
        so CCA is independent of however the surrounding server is
        configured. on_message (a Chainlit UI coroutine bound to the
        parent loop) is bridged back via run_coroutine_threadsafe.
        """
        import asyncio as _asyncio
        parent_loop = _asyncio.get_running_loop()

        async def bridged_on_message(parsed):
            if on_message is None:
                return
            fut = _asyncio.run_coroutine_threadsafe(
                on_message(parsed), parent_loop,
            )
            await _asyncio.wrap_future(fut)

        def thread_target():
            loop = _asyncio.ProactorEventLoop()
            try:
                _asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    CCAAgent._run_query_impl(
                        prompt, options,
                        on_message=bridged_on_message if on_message else None,
                    )
                )
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
                _asyncio.set_event_loop(None)

        return await _asyncio.to_thread(thread_target)

    @staticmethod
    async def _run_query_impl(prompt, options, on_message=None):
        """The original SDK-streaming loop, run inside a ProactorEventLoop
        worker thread. Don't call directly — go through _run_query."""
        from claude_code_sdk import (
            query, ResultMessage, AssistantMessage,
            TextBlock, ToolUseBlock,
        )

        messages = []
        session_id = ""

        # Snapshot existing claude PIDs so we can identify (and clean up)
        # whatever the SDK spawns during this query.
        baseline_pids = _snapshot_claude_pids()

        try:
            async for msg in query(prompt=prompt, options=options):
                parsed = None

                if isinstance(msg, ResultMessage):
                    session_id = msg.session_id or session_id
                    parsed = {
                        "type":     "result",
                        "content":  msg.result or "",
                        "is_error": msg.is_error,
                    }
                elif isinstance(msg, AssistantMessage):
                    if not hasattr(msg, "content"):
                        continue
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            parsed = {
                                "type":    "text",
                                "content": block.text,
                            }
                        elif isinstance(block, ToolUseBlock):
                            name = block.name if hasattr(block, "name") else "tool"
                            inp = block.input if hasattr(block, "input") else {}
                            file_path = ""
                            if isinstance(inp, dict):
                                file_path = inp.get("file_path",
                                                    inp.get("path", ""))
                            parsed = {
                                "type":    "tool_use",
                                "tool":    name,
                                "file":    file_path,
                                "content": f"Using {name}"
                                           + (f" on `{file_path}`"
                                              if file_path else ""),
                            }

                        if parsed:
                            messages.append(parsed)
                            if on_message:
                                await on_message(parsed)
                            parsed = None
                            continue

                if parsed:
                    messages.append(parsed)
                    if on_message:
                        await on_message(parsed)

        except Exception as e:
            # Always dump the real traceback to stderr — uvicorn console will
            # show it. Without this, the catch swallows the chained cause and
            # the chat sees only a one-line summary (or sometimes just an
            # error class name followed by an empty colon, when the SDK wraps
            # an inner exception whose str() is empty).
            import sys
            import traceback
            traceback.print_exc(file=sys.stderr)

            # Suppress async generator cleanup noise on stderr.
            _orig_unraisable = sys.unraisablehook
            def _suppress_generator_exit(unraisable):
                if (unraisable.exc_type is RuntimeError
                        and "GeneratorExit" in str(unraisable.exc_value)):
                    return
                _orig_unraisable(unraisable)
            sys.unraisablehook = _suppress_generator_exit

            # Build a richer string: include the exception class so the chat
            # at least names the failure mode when the SDK's message is empty.
            err_str = str(e).strip() or "(no message)"
            err_label = f"{type(e).__name__}: {err_str}"

            # If the SDK chained from a real OS-level error (FileNotFoundError,
            # PermissionError, etc.) surface that too — that's usually the
            # actually-actionable detail.
            cause = e.__cause__ or e.__context__
            if cause is not None:
                cause_str = str(cause).strip() or "(no message)"
                err_label = (
                    f"{err_label} -> {type(cause).__name__}: {cause_str}"
                )

            if messages:
                parsed = {
                    "type":    "result",
                    "content": f"Session ended early: {err_label}",
                    "is_error": False,
                }
            else:
                parsed = {
                    "type":    "result",
                    "content": f"CCA failed: {err_label}",
                    "is_error": True,
                }
            messages.append(parsed)
            if on_message:
                await on_message(parsed)

        finally:
            # The SDK's transport.close() runs Process.terminate() but on
            # Windows that only kills the .cmd shim — the real worker (a
            # node.exe child) is left running. Force-kill anything new.
            # Give the SDK a tick to do its own cleanup first.
            import asyncio as _asyncio
            await _asyncio.sleep(0.1)
            n_killed = _kill_new_claude_pids(baseline_pids)
            if n_killed:
                import sys
                print(f"  [cca] cleaned up {n_killed} leaked claude "
                      f"subprocess(es)", file=sys.stderr)

        return messages, session_id
