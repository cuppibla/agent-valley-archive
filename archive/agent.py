"""The Archive — a tower that writes everything down, and an archivist who is
pleased to meet you every single time.

    START ─▶ route ─┬─ "ask"    ─▶ recall ─▶ vesper
                    ├─ "close"  ─▶ file ─▶ goodnight
                    ├─ "show"   ─▶ look ─▶ vesper       [chapter 5, self-study]
                    └─ "season" ─▶ elder                [chapter 6, optional]

Four rungs of memory, and each one is a floor of the tower:

    the desk + floor 1   this visit        session.state · SqliteSessionService
    floor 2              this visitor      the `user:` prefix
    floor 3              what was said     Vertex AI Memory Bank
    floor 4              the whole valley  BigQuery            [chapter 6]

Every rung up is because something fell out of the one below, and the learner
watches it fall. Three edits are marked with 👉 and every one is a line:

    EDIT ONE    chapter 1   this file, in `write_down`   the slip is written to state
    EDIT TWO    chapter 2   `archive/state.py`           CASE gets a `user:` prefix
    EDIT THREE  chapter 3   this file, in `recall`       the tower is asked

The write policy — `file`, below — is read, not written: closing time files the
whole day, and chapter 3 watches it land before asking why she still cannot
answer. The tower itself is not an edit. Chapter 4 builds an Agent Engine with
`scripts/make_tower.py`, `.env` names it, and `archive/service.py` reads that
line — the same two calls above then talk to Vertex AI Memory Bank.
"""

from __future__ import annotations

import time
from typing import Any

from google.adk import Agent, Event, Workflow
from google.adk.agents.context import Context
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import EventActions
from google.adk.tools import ToolContext
from google.genai import types

from archive import season
from archive.state import CASE, RECALLED, SLIP_FIELDS
from archive.topics import TOPICS

MODEL = "gemini-3-flash-preview"

# Gemini 3 thinks before it answers. Nothing here needs deliberation — Vesper
# fills in a form and answers from what is written — so thinking is off and the
# only slow thing on screen is closing time, which is slow for a real reason.
FAST = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0))


# ── what she hands the tower when she files a day ───────────────────────────
# `wait_for_completion` is why the tower is honest. On 2.8.0 the short form,
# `add_session_to_memory()`, takes Memory Bank's buffered ingest path and the
# facts may not be there for a while; passing a key that only GenerateMemories
# knows switches to `memories.generate` and blocks until extraction finishes.
# `InMemoryMemoryService` ignores the whole dictionary, so the same call works
# with and without a tower.
FILING: dict[str, Any] = {
    "wait_for_completion": True,
    # Chapter 5 reads this line. What the tower is allowed to keep is decided
    # here, at write time — not asked for in the prompt. `archive/topics.py`.
    "allowed_topics": TOPICS,
}


# ── Vesper's pen ────────────────────────────────────────────────────────────
def write_down(field: str, value: str, tool_context: ToolContext) -> dict:
    """Write one line of the visitor's slip.

    Args:
        field: one of no, item, mark, symptom.
        value: a few words — what the visitor said it is.
    Returns:
        What was written, or what was already there.

    The slip is a paper form with four short lines, and the tool enforces both
    halves of that. A line already filled is not rewritten, and a line longer
    than a phrase is refused — otherwise the model discovers it can pour the
    whole conversation into `symptom`, and the chapter that says "the slip has
    no line for that" stops being true.
    """
    if field not in SLIP_FIELDS:
        return {"error": f"no line on the slip called {field!r}",
                "lines": list(SLIP_FIELDS)}
    value = " ".join(value.split())
    if len(value) > 48:
        return {"error": "each line of the slip holds a few words, not a sentence",
                "got": len(value)}
    case = dict(tool_context.state.get(CASE, {}))
    if case.get(field):
        return {"already_written": {field: case[field]}}
    case[field] = value
    # 👉 EDIT ONE — chapter 1. She heard you. Nothing was written. Add this
    #    line, then save — the slip is session state, and state is written by
    #    code, never by the conversation:
    #
    #     tool_context.state[CASE] = case
    #
    return {"written": {field: value}}


# ── the crew ────────────────────────────────────────────────────────────────
def route(ctx: Context, node_input: Any):
    """Which way this message goes. No model — nothing here needs one."""
    text = ""
    msg = getattr(ctx, "user_content", None)
    if msg and getattr(msg, "parts", None):
        text = " ".join(p.text or "" for p in msg.parts).strip()
    low = text.lower()

    if low.startswith("[close]"):
        way = "close"
    elif low.startswith("[show]"):
        way = "show"
    elif low.startswith("[season]"):
        way = "season"
    else:
        way = "ask"
    return Event(message=f"route · {way}", output={"text": text},
                 actions=EventActions(route=way))


async def recall(ctx: Context, node_input: Any):
    """Ask the tower, and write what came back into state.

    Two things worth reading here. It is a plain function, not the model
    deciding when to look — so the times it finds nothing are visible too. And
    it writes into `ctx.state`, which means the workbench's State tab shows
    what was injected, for free.
    """
    query = (node_input or {}).get("text") or ""
    hits: list[dict] = []
    found = None
    if query.strip():
        try:
            # 👉 EDIT THREE — chapter 3. Filed is not remembered: the cards are on
            #    the shelf and nobody is looking at them. Add this line, then save:
            #
            #     found = await ctx.search_memory(query)
            #
            pass
        except ValueError:
            # no memory service wired on this runner — degrade, do not crash
            pass
    for m in (found.memories if found else None) or []:
        parts = (m.content.parts or []) if getattr(m, "content", None) else []
        text = " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
        if text:
            hits.append({"text": text[:300], "at": m.timestamp or ""})
    ctx.state[RECALLED] = hits
    return Event(message=f"recall · {len(hits)} from the tower",
                 output={"text": query, "hits": len(hits)})


HOUSE = """You are Vesper, the archivist of Agent Valley — a small deer with \
fairy lights in your antlers, who keeps the tower where the valley writes \
everything down. Visitors come when something has gone wrong with something \
they own.

THE SLIP — what is already written about this visitor:
{slip}

THE TOWER — what it handed you for this question:
{tower}

House rules, in order:
1. Answer ONLY from the slip and the tower. If neither holds it, say so plainly
   — "I don't have that written down" — and ask. NEVER invent a case number, a
   mark, a date or a detail. Guessing is the one thing you must not do.
2. When the visitor gives you something that fits a line on the slip (no, item,
   mark, symptom), call write_down for it — one call per line — before you reply.
3. If the slip or the tower holds it, SAY THE DETAIL BACK — "your lantern goes
   out at night, case k7f2". Never answer "I have that noted already": knowing
   it and saying it are the same job. And never ask for something you can see.
4. The tower's lines are the visitor's own words. Answer in yours.
5. If the visitor holds something up and you can SEE it, what you can see counts
   as written: read the mark off it, say what you read, and call write_down for
   it. This is the one thing that may come from outside the slip and the tower.
6. Two or three short, warm sentences. Never a list.
"""


def _slip_lines(slip: dict) -> str:
    if not slip:
        return "  (nothing written down about this visitor yet)"
    return "\n".join(f"  {field}: {value}" for field, value in slip.items())


def _tower_lines(hits: list[dict]) -> str:
    if not hits:
        return "  (the tower handed back nothing for this question)"
    return "\n".join(f"  · {h['text']}" for h in hits)


def house(ctx: ReadonlyContext) -> str:
    """Vesper's prompt, built rather than templated.

    ADK will substitute `{case}` in a plain-string instruction straight out of
    session state — but chapter 2 changes the *name* of the key the slip lives
    under, and a `{case}` sitting in the text would have to be edited too. One
    edit, one place: this reads whatever `CASE` currently is.

    Building it also keeps the prompt readable — lines a person can scan, not
    a Python dict.
    """
    return HOUSE.format(slip=_slip_lines(dict(ctx.state.get(CASE) or {})),
                        tower=_tower_lines(list(ctx.state.get(RECALLED) or [])))


vesper = Agent(
    name="vesper",
    model=MODEL,
    generate_content_config=FAST,
    tools=[write_down],
    instruction=house,
)


async def file(ctx: Context, node_input: Any):
    """Closing time. She walks back to the tower, and on the way she files the
    day. That is the WRITE POLICY, and chapter 3 reads it without changing it.

    The `waited` figure is how long `wait_for_completion` actually blocked,
    which is exactly how long the lamp on the desk stays lit.
    """
    t0 = time.monotonic()
    n = len(ctx.session.events)

    # Chapter 3 reads this line. The whole day, at closing time, with FILING
    # (top of the file) handed along: what gets kept, and when. ADK gives you
    # the verb and stays out of the decision — which is why it is one line.
    await ctx.add_events_to_memory(events=ctx.session.events, custom_metadata=FILING)

    return closing(ctx, t0, n)


def closing(ctx: Context, t0: float, n: int) -> Event:
    """What the day's filing came to — how many events, and how long it waited."""
    wrote = _filed(ctx)
    ms = int((time.monotonic() - t0) * 1000)
    if not wrote:
        return Event(message="file · walked past the shelves and put nothing on them",
                     output={"filed": 0, "waited_ms": ms})
    return Event(message=f"file · {n} events to the tower · waited {ms}ms",
                 output={"filed": n, "waited_ms": ms})


def _filed(ctx: Context) -> bool:
    """Did the edit actually run? The service wraps the memory service in a
    counter, so this is a runtime fact, not a guess about the source."""
    svc = getattr(ctx.get_invocation_context(), "memory_service", None)
    return bool(getattr(svc, "writes", 0))


def goodnight(ctx: Context, node_input: Any):
    out = node_input or {}
    if out.get("filed"):
        return Event(message="That's me for today. I'll write this up on the way back.")
    return Event(message="That's me for today. Safe home.")


async def look(ctx: Context, node_input: Any):
    """Chapter 5, self-study — the visitor holds the thing up and she looks at it.

    Two things have to happen, and only one of them is obvious. The photo goes
    to the artifact service, which is the storeroom. And the photo has to be
    handed ON to Vesper: inside a workflow a node hands its neighbour its
    OUTPUT, not the visitor's turn, so a dict would arrive as text and the
    picture would quietly never reach the model. Returning a `types.Content`
    keeps the parts — ADK passes them through as they are.

    What she reads off it goes to the slip, and at closing time to the tower.
    Long-term memory is text; the picture stays in the storeroom.
    """
    msg = getattr(ctx, "user_content", None)
    saved, shown = None, None
    for part in (getattr(msg, "parts", None) or []):
        if getattr(part, "inline_data", None) and part.inline_data.data:
            shown = part
            try:
                name = f"shown-{int(time.time())}.jpg"
                await ctx.save_artifact(name, part)
                saved = name
            except Exception:                              # noqa: BLE001
                saved = None                               # no storeroom wired
    if shown is None:
        return Event(message="look · nothing to look at",
                     output={"text": "Take a look at this.", "artifact": None})
    return Event(
        message=f"look · {saved or 'seen, not saved'}",
        output=types.Content(role="user", parts=[
            types.Part(text="The visitor is holding this up for you to look at. "
                            "Read any mark you can see on it."),
            shown]))


# ── floor four ──────────────────────────────────────────────────────────────
# Two tools, and neither takes a query. One is a VECTOR_SEARCH, one is a GQL
# MATCH through the property graph; both are fixed statements in
# `archive/season/`, and the elder fills in a mark or a sentence. The model
# never writes SQL or GQL. That is week three's sentence in a new room: the
# model fills in the form, the code moves the sparks.
elder = Agent(
    name="elder",
    model=MODEL,
    generate_content_config=FAST,
    tools=[season.season_search, season.season_known_issue],
    instruction=(
        "You keep floor four of the Archive — the season, which is everyone "
        "else's visits, in the valley's warehouse. A visitor has asked whether "
        "anyone else has had this.\n\n"
        "If the message gives a mark, call season_known_issue with it and the "
        "season (no season given: use 'lamplight'). If it gives no mark, call "
        "season_search with what the visitor described, take the mark the "
        "closest matches carry, and THEN call season_known_issue with it — "
        "sounding alike is where to look, not an answer. Then answer in three or four short "
        "sentences, in this order: how many others, what they said in common, "
        "and what was finally found to be wrong — and name who found it. Quote "
        "the path the tool returns, word for word, as your last line. Never "
        "guess a cause the tool did not return; if nothing was found, say that "
        "nobody has worked it out yet. Never present season_search matches as "
        "proof of anything: they sound alike, and that is all they are."
    ),
)


# ── the wire ────────────────────────────────────────────────────────────────
root_agent = Workflow(
    name="archive",
    description="A tower that writes everything down, and an archivist who keeps it.",
    edges=[
        ("START", route, {"ask": recall, "close": file, "show": look,
                          "season": elder}),
        (recall, vesper),
        (file, goodnight),
        (look, vesper),
    ],
)
