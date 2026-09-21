"""The Archive's service — one agent, two windows.

`adk web .` loads `archive/` and this file loads the same package, so there is no
practice copy: the file the learner edits is the file both surfaces run. The
session store is a file both can open. Once `.env` names a tower, the memory
store is one Memory Bank both can reach.

The graph is re-imported on every request, so an edit in `archive/agent.py` or
`archive/state.py` changes what the tower does without restarting anything.
Connecting the tower is a change to `.env`, and that needs a restart — the
codelab says so where it asks for it.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forge  # noqa: F401,E402  — settles Vertex-vs-key for every surface
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from google.adk.memory import InMemoryMemoryService  # noqa: E402
from google.adk.memory.base_memory_service import BaseMemoryService  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.sqlite_session_service import SqliteSessionService  # noqa: E402
from google.genai import types  # noqa: E402

from archive import progress, tower  # noqa: E402

log = logging.getLogger(__name__)
app = FastAPI(title="Agent 101 · W4 The Archive")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# The names `adk web .` uses: the app is the folder, the user is "user". That is
# what lets the workbench open the very visit this service wrote.
APP = "archive"

# 👉 SELF-STUDY — chapter 5. Every visitor shares one drawer and one tower while
#    this is a constant. Make it come from the request and each gets their own.
#    Scope is (app_name, user_id), and the same pair keys both.
USER = "user"

DB = str(Path(__file__).resolve().parents[1] / "archive.db")

# ── where the visits live ───────────────────────────────────────────────────
# Chapter 1 reads this line and does not change it. A visit in a file survives
# closing time, and `adk web --session_service_uri=sqlite:///archive.db` opens
# the same one. Three slashes.
_sessions = SqliteSessionService(DB)


class Counted(BaseMemoryService):
    """A memory service that remembers how many times it was written to.

    The count is what tells the app "the edit is in AND a day has actually been
    filed", which source-reading alone cannot say. It resets with the process,
    and that reset is chapter 3's blackout telling the truth.
    """

    def __init__(self, inner):
        self.inner = inner
        self.writes = 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def search_memory(self, **kw):
        return await self.inner.search_memory(**kw)

    async def add_events_to_memory(self, **kw):
        out = await self.inner.add_events_to_memory(**kw)
        self.writes += 1
        return out

    async def add_session_to_memory(self, session):
        out = await self.inner.add_session_to_memory(session)
        self.writes += 1
        return out


# ── where what was said lives ───────────────────────────────────────────────
# Chapter 4 reads this block and changes nothing in it. The archive is
# in-process keyword memory until `.env` names a tower — then the SAME write
# and recall (chapter 3's `add_events_to_memory`, `recall`'s `search_memory`)
# talk to Vertex AI Memory Bank instead. `scripts/make_tower.py` builds one and
# writes AGENT_ENGINE here; `adk web --memory_service_uri agentengine://…`
# is the same connection in the workbench's spelling.
AGENT_ENGINE = os.environ.get("AGENT_ENGINE", "")
if AGENT_ENGINE:
    from google.adk.memory import VertexAiMemoryBankService

    _memory = Counted(VertexAiMemoryBankService(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],                   # which project
        location=os.environ.get("MEMORY_BANK_LOCATION", "us-central1"),  # where it lives
        agent_engine_id=AGENT_ENGINE.split("/")[-1],                  # WHICH tower
    ))
else:
    _memory = Counted(InMemoryMemoryService())

def _probe() -> dict[str, Any]:
    return progress.read(_sessions, _memory, db=DB)


# ── plain reads ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {"ok": True, "progress": _probe()}


@app.get("/progress")
async def get_progress() -> dict:
    return _probe()


@app.get("/tower")
async def get_tower() -> dict:
    cards = await tower.cards(_memory, APP, USER)
    listed = await _sessions.list_sessions(app_name=APP, user_id=USER)
    return {"cards": cards, "books": _visits(listed),
            "store": type(_memory.inner).__name__}


def _slip(state: dict) -> dict:
    """The slip, whichever key it is under — chapter 2 moves it."""
    return dict(state.get("user:case") or state.get("case") or {})


def _visits(listed) -> int:
    """Books on floor one — one per visit."""
    return len([s for s in listed.sessions if not s.id.startswith("trial-")])


async def _floors(sess) -> dict:
    p = _probe()
    cards = await tower.cards(_memory, APP, USER)
    listed = await _sessions.list_sessions(app_name=APP, user_id=USER)
    state = dict(sess.state) if sess else {}
    slip = _slip(state)
    prefixed = str(p["case_key"]).startswith("user:")
    drawer = dict(state.get("user:case") or {}) if prefixed else {}
    return {
        "desk": {"lit": bool(slip), "fields": slip},
        "f1": {"lit": True, "books": _visits(listed)},
        "f2": {"lit": bool(drawer), "fields": drawer,
               "why": None if drawer else
               ("the last visit's slip did not follow you" if not prefixed
                else "nothing written down yet")},
        "f3": {"lit": bool(cards), "cards": cards,
               "store": "Memory Bank" if p["memory_store"] == "VertexAiMemoryBankService"
               else "in this process",
               "topics": p["topics"],
               "why": None if cards else
               ("nothing was filed at closing time" if not p["file_writes"]
                else "filed at closing time — say goodnight to fill it")},
        "f4": {"lit": p["season"] == "open", "locked": p["season"] != "open"},
    }


@app.get("/session/{sid}")
async def get_session(sid: str) -> dict:
    """The visit the app is looking at — opened the moment you walk in.

    Walking in IS the visit: the session is created here, before a word is
    said, so floor one gets its book at once and — after chapter 2 — the
    `user:` drawer is already merged into the state the tower draws. Waiting
    for the first message would show an empty drawer to a visitor it knows.
    """
    sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
    fresh = sess is None
    if fresh:
        sess = await _sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
    return {"exists": True, "id": sid, "state": dict(sess.state), "fresh": fresh,
            "events": _events(sess), "progress": _probe(), "floors": await _floors(sess)}


def _node_of(ev) -> str:
    info = (ev.model_dump().get("node_info") or {})
    return (info.get("path") or "").split("/")[-1].split("@")[0]


def _text_of(ev) -> str:
    parts = (ev.content.parts if ev.content else []) or []
    return " ".join(p.text.strip() for p in parts if p.text and p.text.strip())


def _events(sess) -> list[dict]:
    out = []
    for ev in sess.events:
        parts = (ev.content.parts if ev.content else []) or []
        if any(p.function_call or p.function_response for p in parts):
            continue
        text = _text_of(ev)
        if not text:
            continue
        out.append({"author": ev.author, "node": _node_of(ev), "text": text[:400],
                    "delta": dict(ev.actions.state_delta or {}) if ev.actions else {},
                    "at": ev.timestamp})
    return out


# ── the stream ──────────────────────────────────────────────────────────────
def _sse(kind: str, **data) -> str:
    return f"data: {json.dumps({'kind': kind, **data}, default=str)}\n\n"


async def _run(sid: str, message: types.Content):
    """Drive the graph and translate ADK events into what the tower draws."""
    p = _probe()
    yield _sse("progress", **p)

    import importlib
    mod = importlib.import_module("archive.agent")
    wf = mod.root_agent

    sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
    if sess is None:
        sess = await _sessions.create_session(app_name=APP, user_id=USER, session_id=sid)

    runner = Runner(app_name=APP, agent=wf, session_service=_sessions,
                    memory_service=_memory)
    t0 = time.monotonic()
    try:
        async for ev in runner.run_async(user_id=USER, session_id=sid, new_message=message):
            node = _node_of(ev)
            if not node:
                continue
            parts = (ev.content.parts if ev.content else []) or []
            if any(p_.function_call or p_.function_response for p_ in parts):
                continue
            text = _text_of(ev)
            sd = dict(ev.actions.state_delta or {}) if ev.actions else {}
            yield _sse("node", node=node, text=text[:400], delta=sd,
                       route=(ev.actions.route if ev.actions else None),
                       at=round(time.monotonic() - t0, 2))
    except Exception as exc:                               # noqa: BLE001
        log.exception("run failed")
        yield _sse("error", message=f"{type(exc).__name__}: {exc}"[:300])

    sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
    yield _sse("state", state=dict(sess.state) if sess else {},
               floors=await _floors(sess), progress=_probe(),
               seconds=round(time.monotonic() - t0, 1))


def _stream(gen, sid: str) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no", "X-Session-Id": sid})


def _msg(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    sid = (body.get("session_id") or "").strip() or f"v-{os.urandom(4).hex()}"
    return _stream(_run(sid, _msg((body.get("text") or "").strip())), sid)


@app.post("/close")
async def close(req: Request):
    """🌙 that's all for today — the message that makes `route` take the close edge."""
    body = await req.json()
    sid = (body.get("session_id") or "").strip()
    return _stream(_run(sid, _msg("[close] that's all for today")), sid)


# ── forgetting ──────────────────────────────────────────────────────────────
# One page at a time is `scripts/shelf.py --burn N`; this is all of them.
@app.post("/forget")
async def forget(req: Request) -> dict:
    """Floor three empties, the drawer clears — floor one keeps its books,
    because those are the record, not the memory."""
    body = await req.json()
    gone = await tower.forget_all(_memory, APP, USER)
    sid = (body.get("session_id") or "").strip()
    if sid:
        sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
        if sess:
            from google.adk.events import Event, EventActions
            await _sessions.append_event(sess, Event(
                author="archive", invocation_id=f"forget-{os.urandom(3).hex()}",
                actions=EventActions(state_delta={"user:case": {}, "case": {},
                                                  "recalled": []})))
    sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid) if sid else None
    return {"ok": True, "forgot": gone, "floors": await _floors(sess)}


@app.post("/reset")
async def reset(req: Request) -> dict:
    body = await req.json()
    sid = (body.get("session_id") or "").strip()
    await tower.forget_all(_memory, APP, USER)
    if sid:
        sess = await _sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
        if sess is None:
            sess = await _sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
        from google.adk.events import Event, EventActions
        await _sessions.append_event(sess, Event(
            author="archive", invocation_id=f"reset-{os.urandom(3).hex()}",
            actions=EventActions(state_delta={"user:case": {}, "case": {}, "recalled": []})))
    return {"ok": True}
