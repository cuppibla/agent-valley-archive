"""How the app knows which edits you have made.

Week three's service re-imported the learner's `agent.py` on every message and
read `topology()` off the graph — add one `approve,` and Odo appeared in the back
room. This is the same idea. Week four's graph is flat, so instead of a shape we
read four facts, and the tower lights the floors they justify.

Some are structural (a constant, a class name, a dict key). Three — whether
`write_down` writes to state, whether `file` writes to memory, whether `recall`
asks — can only be read out of a function's source, because each is a line
inside a body. Source text can be fooled: the codelab's own
👉 comment contains the very call we are looking for. So we strip comments first,
AND the service pairs this with a runtime counter (`writes`), which cannot be
fooled and which resets when the process does — that reset being exactly what
chapter 3's blackout is meant to show.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import logging
from typing import Any

logger = logging.getLogger(__name__)

_last_good: dict[str, Any] | None = None


def _strip_comments(src: str) -> str:
    """Drop `#` lines. The codelab's EDIT TWO comment block spells out the exact
    call, so a naive `in` test on the raw source reports True before the edit."""
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line.split("  #")[0] if "  #" in line else line)
    return "\n".join(out)


def _filing_has_topics(mod) -> list[str] | None:
    """The topic names FILING hands the tower — a `MemoryTopicId` is a dict
    with one of two keys, and the bar wants the label either way."""
    filing = getattr(mod, "FILING", None)
    if isinstance(filing, dict):
        got = filing.get("allowed_topics") or []
        names = [t.get("managed_memory_topic") or t.get("custom_memory_topic_label")
                 if isinstance(t, dict) else str(t) for t in got]
        return [n for n in names if n] or None
    return None


def read(sessions: Any, memory: Any, *, db: str = "archive.db") -> dict[str, Any]:
    """One look at the learner's code. Never raises — a syntax error keeps the
    last good answer and reports the error alongside it, so the tower holds its
    state instead of flashing empty."""
    global _last_good
    try:
        state = importlib.reload(importlib.import_module("archive.state"))
        agent = importlib.reload(importlib.import_module("archive.agent"))

        body = _strip_comments(inspect.getsource(agent.file))
        writes = "add_events_to_memory" in body or "add_session_to_memory" in body
        pen = _strip_comments(inspect.getsource(agent.write_down))
        state_write = "tool_context.state[" in pen
        eyes = _strip_comments(inspect.getsource(agent.recall))
        recall_reads = "search_memory" in eyes

        out = {
            "session_store": type(sessions).__name__,
            "memory_store": type(getattr(memory, "inner", memory)).__name__,
            "state_write": state_write,
            "case_key": state.CASE,
            "file_writes": writes,
            "recall_reads": recall_reads,
            "has_written": int(getattr(memory, "writes", 0)),
            "topics": _filing_has_topics(agent),
            "user_mode": "fixed",
            "season": _season(db),
            "error": None,
        }
        out["level"] = _level(out)
        _last_good = out
        return out
    except Exception as exc:                               # noqa: BLE001
        logger.warning("could not read the learner's code: %s", exc)
        stale = dict(_last_good or _blank(sessions, memory))
        stale["error"] = f"{type(exc).__name__}: {exc}"
        return stale


def _level(p: dict[str, Any]) -> int:
    """How far up the tower the learner has actually climbed.

    Monotonic on purpose, and it starts at zero: until `write_down` writes to
    state there is no slip, so the desk is not lit either. Floor four's tables
    can be laid down at any moment — they are a file on disk — but a badge that
    jumped to 4/4 while floors two and three were dark would be lying.
    """
    level = 0
    if p["state_write"]:
        level = 1
    if level == 1 and str(p["case_key"]).startswith("user:"):
        level = 2
    if level == 2 and p["file_writes"] and p["recall_reads"] \
            and p["memory_store"] == "VertexAiMemoryBankService":
        level = 3
    if level == 3 and p["season"] == "open":
        level = 4
    return level


def _season(db: str) -> str:
    """Chapter 6: has the season been loaded into the warehouse?"""
    _ = db
    from archive import season
    return "open" if season.is_open() else "locked"


def _blank(sessions: Any, memory: Any) -> dict[str, Any]:
    return {"session_store": type(sessions).__name__,
            "memory_store": type(getattr(memory, "inner", memory)).__name__,
            "state_write": False, "recall_reads": False,
            "case_key": "case", "file_writes": False, "has_written": 0,
            "topics": None, "user_mode": "fixed", "season": "locked",
            "level": 0, "error": None}
