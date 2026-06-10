"""Standalone CCA smoke test. Run via: python .cca_smoke_test.py"""
import asyncio
import json
import sys

sys.path.insert(0, r'd:\csuite')
from dotenv import load_dotenv
load_dotenv()

from core.agents.cca import (
    CCAAgent,
    _snapshot_claude_pids,
    _kill_new_claude_pids,
)
from core.config import COMPANY_ROOT


async def main() -> int:
    cfg = json.loads(
        (COMPANY_ROOT / 'janky_games' / 'config.json').read_text(encoding='utf-8')
    )
    cfg['company_id'] = 'janky_games'

    baseline = _snapshot_claude_pids()
    print(f'baseline claude PIDs: {len(baseline)} = {sorted(baseline)}')

    agent = CCAAgent(cfg)
    print(f'agent built, codebase={agent.codebase_path}, model={agent.model}')

    messages, sid = await agent.start_session('say hello in one word')
    print(f'session ended. messages={len(messages)}, sid={sid!r}')

    last = messages[-1] if messages else {}
    print(f'last message type: {last.get("type")}')
    print(f'last is_error:     {last.get("is_error")}')
    if last.get('is_error'):
        print(f'  content head:    {(last.get("content") or "")[:300]}')

    after = _snapshot_claude_pids()
    new = after - baseline
    survived = baseline & after
    print(f'after run: total={len(after)}, new={len(new)}, '
          f'baseline-still-alive={len(survived)}')

    if new:
        print(f'  LEAK: {sorted(new)} survived our cleanup')
        return 1

    print('OK — no new claude processes leaked.')

    # Also clean up any baseline-leftover that's been hanging around so the
    # user starts fresh. (Forces baseline to empty for the next test.)
    if survived:
        n = _kill_new_claude_pids(set())  # baseline=empty -> kill everything
        print(f'  bonus: also killed {n} leftover baseline process(es)')

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
