"""Floor three, from the terminal: list the cards on the shelf, or burn one.

    uv run python scripts/shelf.py             list them
    uv run python scripts/shelf.py --burn 2    take card 2 off the shelf

Reads the same tower `.env` names, with the same scope the Archive files under
— (app_name, user_id). Before chapter 4 the shelf is inside the running
Archive's process, and no other process can see it; that is chapter 3's whole
point, so this script only works once there is a tower.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import forge  # noqa: F401,E402  — reads .env, settles Vertex-vs-key

from archive import tower  # noqa: E402
from archive.service import APP, USER, _memory  # noqa: E402  — the services the Archive runs on


async def main() -> int:
    if not os.environ.get("AGENT_ENGINE"):
        print("\n  no tower in .env yet — the shelf is inside the Archive's own process,"
              "\n  and this process cannot see it. Chapter 4 builds the tower.\n")
        return 1
    cards = await tower.cards(_memory, APP, USER)
    if "--burn" in sys.argv:
        n = int(sys.argv[sys.argv.index("--burn") + 1])
        if not 1 <= n <= len(cards):
            print(f"\n  there is no card {n} — the shelf has {len(cards)}\n")
            return 1
        gone = cards[n - 1]
        await tower.burn(_memory, APP, USER, gone["id"])
        print(f"\n  burned card {n}:  {gone['text'][:80]}")
        cards = await tower.cards(_memory, APP, USER)
    print(f"\n  floor three · Memory Bank · {len(cards)} card{'' if len(cards) == 1 else 's'}\n")
    for i, c in enumerate(cards, 1):
        when = f" · {c['date']}" if c.get("date") else ""
        print(f"  {i}  {c['kind']}{when}   {c['text']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
