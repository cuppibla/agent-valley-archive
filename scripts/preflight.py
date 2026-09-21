"""Is this machine ready, and where are you in the lab?

Run it now, and run it again any time you want the answer to "which edits have
I actually made?" — every line is read from your code, not from a checklist.

    uv run python scripts/preflight.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import forge  # noqa: E402  — settles Vertex-vs-key before anything else

from google.adk.memory import InMemoryMemoryService  # noqa: E402
from google.adk.sessions.sqlite_session_service import SqliteSessionService  # noqa: E402

from archive import progress  # noqa: E402

TICK, BOX = "\033[32m✓\033[0m", "\033[90m▢\033[0m"
DIM, OFF = "\033[90m", "\033[0m"


def bar(p: dict) -> list[str]:
    """The six things the tower can be, and which of them are true right now."""
    rows = [
        ("desk   ", p["state_write"], "the slip",
         "write_down writes to state" if p["state_write"] else "write_down writes nothing",
         "chapter 1 · EDIT ONE"),
        ("floor 1", p["session_store"] == "SqliteSessionService", "the file",
         p["session_store"], "chapter 1, read only"),
        ("floor 2", str(p["case_key"]).startswith("user:"), "the drawer",
         f'CASE = "{p["case_key"]}"', "chapter 2 · EDIT TWO"),
        ("floor 3", bool(p["file_writes"]), "what was said",
         "closing time files the day" if p["file_writes"]
         else "closing time writes nothing", "chapter 3, read only"),
        ("floor 3", bool(p["recall_reads"]), "the asking",
         "recall asks the tower" if p["recall_reads"] else "recall never looks",
         "chapter 3 · EDIT THREE"),
        ("floor 3", p["memory_store"] == "VertexAiMemoryBankService", "the tower",
         p["memory_store"], "chapter 4 · built, not edited"),
        ("floor 3", bool(p["topics"]), "the rules",
         ", ".join(p["topics"]) if p["topics"] else "the tower keeps everything",
         "chapter 5, read only"),
    ]
    return [f"  {where}   {TICK if done else BOX} {name:<14}{DIM}· {how:<34}{note}{OFF}"
            for where, done, name, how, note in rows]


def main() -> int:
    print()
    mode = forge.MODE
    if not mode:
        print("  ✗ Not configured. Either point gcloud at a project:")
        print("        gcloud config set project YOUR_PROJECT_ID")
        print("    or put a key in .env — see .env.example.")
        return 1
    where = (os.environ.get("GOOGLE_CLOUD_PROJECT", "?") if mode == "vertex"
             else "an API key")
    print(f"  talking to Gemini through {DIM}{mode} · {where}{OFF}")

    try:
        import logging

        from google import genai
        # the SDK warns that one-shot generate_content is not the AFC way. It is
        # one call to prove the key works; the warning is noise here.
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)
        client = genai.Client()
        reply = client.models.generate_content(
            model="gemini-3-flash-preview", contents="Reply with the word: ready")
        print(f"  the model answers {DIM}· {(reply.text or '').strip()[:40]}{OFF}")
    except Exception as exc:                               # noqa: BLE001
        print(f"  ✗ the model did not answer: {type(exc).__name__}: {exc}"[:200])
        return 1

    engine = os.environ.get("AGENT_ENGINE", "")
    print(f"  the tower {DIM}· " + (f"reasoningEngines/{engine.split('/')[-1]}" if engine
          else "not built yet — chapter 4 builds it") + OFF)

    print("\n  where you are:\n")
    p = progress.read(SqliteSessionService(str(ROOT / "archive.db")),
                      InMemoryMemoryService())
    for line in bar(p):
        print(line)
    print(f"\n  {DIM}three are ticked before you start — those are the ones you only"
          f" read. Three are lines you write; one is a tower you build.{OFF}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
