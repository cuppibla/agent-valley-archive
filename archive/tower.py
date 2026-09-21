"""Reading the whole of floor three, and burning one page off it.

Two honest boundaries live in this file, and the codelab points at both.

1. **There is no "list everything" in the ADK memory abstraction.** `search_memory`
   needs a query. The tower panel has to show what is on the shelf whether or not
   anyone asked a question, so each backend gets its own reader here:

       InMemoryMemoryService   read the events it stored — our own dev stand-in,
                               so reaching into it is acceptable, and what comes
                               back is the visitor's OWN WORDS.
       VertexAiMemoryBankService   list by scope through the Vertex client — and
                               what comes back is DISTILLED FACTS with dates.

   That difference is not a detail, it is chapter 3's payoff: before the edit the
   shelf holds quotes, after it the shelf holds facts.

2. **There is no delete either.** `BaseMemoryService` has add_session_to_memory,
   add_events_to_memory, add_memory and search_memory. Forgetting is a governance
   action, not an agent action, so it lives here in the application — where the
   model cannot reach it by accident.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _quote_cards(mem, app: str, user: str) -> list[dict[str, Any]]:
    """In-memory: the events it kept, verbatim. One card per thing that was said."""
    store = getattr(mem, "_session_events", {})
    cards: list[dict[str, Any]] = []
    for (a, u), sessions in store.items():
        if a != app or u != user:
            continue
        for sid, events in sessions.items():
            for ev in events:
                parts = (ev.content.parts or []) if getattr(ev, "content", None) else []
                text = " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
                if not text or getattr(ev, "author", "") != "user":
                    continue
                if text.startswith("[close]") or text.startswith("[show]"):
                    continue
                cards.append({"id": f"{sid}:{ev.id}", "text": text[:220],
                              "date": "", "kind": "quote"})
    return cards


async def _fact_cards(mem, app: str, user: str) -> list[dict[str, Any]]:
    """Memory Bank: every memory in this scope, distilled, with its date.

    Not `search_memory` — that needs a query. This lists the scope, which the
    ADK surface does not expose, so it goes through the Vertex client:
    `memories.retrieve` with simple (non-similarity) retrieval params.
    """
    cards: list[dict[str, Any]] = []
    try:
        client = mem._get_api_client()                     # noqa: SLF001
        pager = await client.agent_engines.memories.retrieve(
            name="reasoningEngines/" + mem._agent_engine_id,  # noqa: SLF001
            scope={"app_name": app, "user_id": user},
            simple_retrieval_params={"page_size": 100},
        )
        async for hit in pager:
            m = getattr(hit, "memory", None)
            fact = getattr(m, "fact", None) if m else None
            if not fact:
                continue
            at = getattr(m, "update_time", None)
            cards.append({"id": getattr(m, "name", "") or "",
                          "text": fact[:220],
                          "date": at.date().isoformat() if at else "",
                          "kind": "fact"})
    except Exception as exc:                               # noqa: BLE001
        logger.warning("could not list the tower: %s", exc)
    return cards


def _bare(mem):
    """The service itself. The app wraps it in `Counted` to count writes, and a
    wrapper answers to a different class name than the thing it wraps."""
    return getattr(mem, "inner", mem)


async def cards(mem, app: str, user: str) -> list[dict[str, Any]]:
    """Everything on floor three, whichever tower is in use."""
    mem = _bare(mem)
    if mem is None:
        return []
    if type(mem).__name__ == "VertexAiMemoryBankService":
        return await _fact_cards(mem, app, user)
    return _quote_cards(mem, app, user)


async def burn(mem, app: str, user: str, memory_id: str) -> bool:
    """Take one page off the shelf. ADK has no delete; this is the application
    doing it, which is where forgetting belongs."""
    mem = _bare(mem)
    if mem is None:
        return False
    if type(mem).__name__ == "VertexAiMemoryBankService":
        try:
            client = mem._get_api_client()                 # noqa: SLF001
            await client.agent_engines.memories.delete(name=memory_id)
            return True
        except Exception as exc:                           # noqa: BLE001
            logger.warning("could not burn %s: %s", memory_id, exc)
            return False
    # the dev stand-in: drop that one event out of the store
    sid, _, eid = memory_id.partition(":")
    store = getattr(mem, "_session_events", {})
    events = store.get((app, user), {}).get(sid)
    if not events:
        return False
    before = len(events)
    store[(app, user)][sid] = [e for e in events if e.id != eid]
    return len(store[(app, user)][sid]) < before


async def forget_all(mem, app: str, user: str) -> int:
    """The right to be forgotten. Floor three empties; floor one keeps its books,
    because those are the record that the visits happened, not the memory of them."""
    gone = 0
    for c in await cards(mem, app, user):
        if await burn(mem, app, user, c["id"]):
            gone += 1
    return gone
