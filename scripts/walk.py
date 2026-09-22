"""Walk the codelab, chapter by chapter, against the real agent.

Not a unit test — a rehearsal. Every assertion here is a sentence the codelab
makes to the learner, so a failure means the prose is wrong, not just the code.

    uv run python scripts/walk.py 1      one chapter
    uv run python scripts/walk.py        all of them
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import forge  # noqa: F401,E402
from google.adk.artifacts.file_artifact_service import FileArtifactService  # noqa: E402
from google.adk.memory import InMemoryMemoryService  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.sqlite_session_service import SqliteSessionService  # noqa: E402
from google.genai import types  # noqa: E402

from archive import progress, tower  # noqa: E402
from archive.service import Counted  # noqa: E402 — the real wrapper the app uses

APP, USER = "archive", "user"
DB = str(ROOT / "walk.db")

OK, BAD = "\033[32m✓\033[0m", "\033[31m✗\033[0m"
_fails: list[str] = []


def check(claim: str, cond: bool, detail: str = "") -> None:
    print(f"  {OK if cond else BAD} {claim}" + (f"   — {detail}" if detail else ""))
    if not cond:
        _fails.append(claim)


TOWER = os.environ.get("AGENT_ENGINE", "")


def tower_service():
    """The same three lines `archive/service.py` runs when .env names a tower."""
    from google.adk.memory import VertexAiMemoryBankService
    return VertexAiMemoryBankService(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("MEMORY_BANK_LOCATION", "us-central1"),
        agent_engine_id=TOWER.split("/")[-1])


class World:
    """One learner's machine: a session store and a memory store."""

    def __init__(self, memory=None):
        self.sessions = SqliteSessionService(DB)
        self.memory = Counted(memory or InMemoryMemoryService())
        self.artifacts = FileArtifactService(str(ROOT / ".artifacts"))

    def runner(self):
        # The service re-imports on every message — that is the whole reason the
        # codelab can say "no restart" for the two edits that live in the agent.
        # The harness must do the same or it tests a stale module.
        import importlib
        importlib.reload(importlib.import_module("archive.state"))
        wf = importlib.reload(importlib.import_module("archive.agent")).root_agent
        return Runner(app_name=APP, agent=wf, session_service=self.sessions,
                      memory_service=self.memory, artifact_service=self.artifacts)

    async def say(self, sid: str, text: str) -> str:
        if await self.sessions.get_session(app_name=APP, user_id=USER, session_id=sid) is None:
            await self.sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
        msg = types.Content(role="user", parts=[types.Part(text=text)])
        said = ""
        async for ev in self.runner().run_async(user_id=USER, session_id=sid, new_message=msg):
            info = (ev.model_dump().get("node_info") or {})
            node = (info.get("path") or "").split("/")[-1].split("@")[0]
            parts = (ev.content.parts if ev.content else []) or []
            if any(p.function_call or p.function_response for p in parts):
                continue
            text_ = " ".join(p.text.strip() for p in parts if p.text and p.text.strip())
            if node == "vesper" and text_:
                said = text_
        return said

    async def state(self, sid: str) -> dict:
        s = await self.sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
        return dict(s.state) if s else {}

    async def slip(self, sid: str) -> dict:
        st = await self.state(sid)
        return dict(st.get("user:case") or st.get("case") or {})


def _uncomment(path, commented: str, bare: str, on: bool) -> None:
    """Toggle one 👉 line between its commented and live form. Line-exact — the
    two forms differ only by the leading "# ", which is the whole edit."""
    lines = path.read_text().splitlines()
    src, dst = (commented, bare) if on else (bare, commented)
    if any(ln == dst for ln in lines):          # already where we want it
        return
    path.write_text("\n".join(dst if ln == src else ln for ln in lines) + "\n")


EDITS = {
    # name: (file, the line as it ships — commented out, the line once uncommented)
    "state":  ("archive/agent.py",
               "    # tool_context.state[CASE] = case",
               "    tool_context.state[CASE] = case"),
    "recall": ("archive/agent.py",
               "            # found = await ctx.search_memory(query)",
               "            found = await ctx.search_memory(query)"),
}


def edit(name: str, on: bool = True) -> None:
    """Apply or undo one of the three edits, the way a learner would."""
    if name == "prefix":
        p = ROOT / "archive/state.py"
        s = p.read_text()
        s = (s.replace('CASE = "case"', 'CASE = "user:case"') if on
             else s.replace('CASE = "user:case"', 'CASE = "case"'))
        p.write_text(s)
        return
    f, commented, bare = EDITS[name]
    _uncomment(ROOT / f, commented, bare, on)


def edits_off() -> None:
    for name in ("state", "prefix", "recall"):
        edit(name, False)


SAY_FACTS = "My lantern goes out at night. Case #k7f2. There's a little q7 stamped on the base."
SAY_1 = "I read by it at night, so night is exactly when I need it."
SAY_2 = "I've tried hanging it higher. No change."
SAY_3 = "I don't want a new one — it was a gift."


async def ch1(w: World) -> None:
    print("\n\033[1mChapter 1 — she remembers, and she remembers overnight\033[0m")
    edits_off()
    sid = "ch1-visit"
    before = await w.slip(sid)
    check("the slip starts empty", before == {}, str(before))
    said = await w.say(sid, SAY_FACTS)
    check("run it broken: she heard you and wrote nothing down",
          await w.slip(sid) == {}, said[:80])
    p = progress.read(w.sessions, w.memory, db=DB)
    check("progress says level 0 — the desk is dark", p["level"] == 0 and not p["state_write"])

    edit("state", True)
    sid = "ch1-again"
    await w.say(sid, SAY_FACTS)
    slip = await w.slip(sid)
    got = set(slip)
    check("EDIT ONE: one message fills the slip", len(got) >= 3, f"{len(got)} fields: {sorted(got)}")
    check("it caught the case number", "k7f2" in str(slip.get("no", "")).lower(), str(slip.get("no")))
    check("it caught the mark", "q7" in str(slip.get("mark", "")).lower(), str(slip.get("mark")))

    # a second store object over the SAME file is what "survives the night" means
    fresh = World()
    kept = await fresh.slip(sid)
    check("a fresh process still finds the visit", set(kept) == got, f"{sorted(kept)}")

    p = progress.read(w.sessions, w.memory, db=DB)
    check("progress says level 1", p["level"] == 1, f"level={p['level']} case_key={p['case_key']}")
    check("file_writes is True from the start — the write policy ships in `file`",
          p["file_writes"] is True)
    check("recall_reads is False despite the comment naming the call",
          p["recall_reads"] is False)


async def ch2(w: World) -> None:
    print("\n\033[1mChapter 2 — the next visit, she doesn't\033[0m")
    edit("state", True); edit("prefix", False)
    v1, v2 = "ch2-a", "ch2-b"
    await w.say(v1, SAY_FACTS)
    check("visit one has a slip", bool(await w.slip(v1)))
    said = await w.say(v2, "I was here last month about my lantern.")
    check("visit two starts empty", (await w.slip(v2)).get("no") is None)
    check("and she says so rather than inventing one",
          "k7f2" not in said.lower(), said[:90])

    edit("prefix", True)
    v3, v4 = "ch2-c", "ch2-d"
    await w.say(v3, SAY_FACTS)
    slip3 = await w.slip(v3)
    await w.say(v4, "Hello again.")   # a brand-new visit, same visitor
    slip4 = await w.slip(v4)
    check("five characters carry the slip into the next visit",
          slip4.get("no") == slip3.get("no") and bool(slip4), f"{slip4}")
    p = progress.read(w.sessions, w.memory, db=DB)
    check("progress says level 2", p["level"] == 2, f"case_key={p['case_key']}")


async def ch3(w: World) -> None:
    print("\n\033[1mChapter 3 — the slip has no line for that\033[0m")
    edit("state", True); edit("prefix", True); edit("recall", False)
    sid = "ch3-a"
    for s in (SAY_FACTS, SAY_1, SAY_2, SAY_3):
        await w.say(sid, s)
    slip = await w.slip(sid)
    check("the three sentences did NOT land on the slip",
          set(slip) <= {"no", "item", "mark", "symptom"}, f"{sorted(slip)}")

    # the write policy is read, not written: closing time files the day as shipped
    await w.say(sid, "[close] that's all for today")
    check("closing time files the day — the write policy ships in `file`",
          w.memory.writes >= 1, f"writes={w.memory.writes}")
    cards = await tower.cards(w.memory, APP, USER)
    check("floor three has cards now", len(cards) > 0, f"{len(cards)} cards")
    check("and in-process they are QUOTES, not facts",
          all(c["kind"] == "quote" for c in cards), cards[0]["text"][:60] if cards else "")

    # filed is not remembered: the shelf is full and nobody is looking at it
    said = await w.say("ch3-blind", "What have I already tried?")
    hits = (await w.state("ch3-blind")).get("recalled") or []
    check("filed is not remembered — recall never looked, so she cannot say",
          hits == [] and not ("hang" in said.lower() or "high" in said.lower()),
          f"{len(hits)} hits — {said[:70]}")

    edit("recall", True)
    w2 = World(w.memory.inner)        # same tower, fresh runner — the edit reloads
    sid2, sid3 = sid, "ch3-c"
    said = await w2.say(sid3, "What have I already tried?")
    check("EDIT THREE: a later visit can answer it", "hang" in said.lower() or "high" in said.lower(), said[:90])

    p = progress.read(w2.sessions, w2.memory, db=DB)
    check("progress says file_writes and recall_reads are True now",
          p["file_writes"] is True and p["recall_reads"] is True)
    check("but still level 2 — the tower is in this process",
          p["level"] == 2, f"level={p['level']} store={p['memory_store']}")


async def ch4(w: World) -> None:
    print("\n\033[1mChapter 5 — she keeps everything, forever\033[0m")
    edit("state", True); edit("prefix", True); edit("recall", True)
    p = progress.read(w.sessions, w.memory, db=DB)
    check("the rules are in FILING from the start — nothing to edit",
          p["topics"] == ["USER_PREFERENCES", "LANTERN_CONTEXT"], str(p["topics"]))

    cards = await tower.cards(w.memory, APP, USER)
    if cards:
        target = cards[0]["id"]
        gone = await tower.burn(w.memory, APP, USER, target)
        after = await tower.cards(w.memory, APP, USER)
        check("burning one page takes it off the shelf",
              gone and len(after) == len(cards) - 1, f"{len(cards)} → {len(after)}")
    n = await tower.forget_all(w.memory, APP, USER)
    left = await tower.cards(w.memory, APP, USER)
    listed = await w.sessions.list_sessions(app_name=APP, user_id=USER)
    check("forget-everything empties floor three", left == [], f"forgot {n}")
    check("...and floor one keeps its books", len(listed.sessions) > 0,
          f"{len(listed.sessions)} visits on the shelf")

    import inspect
    from google.adk.memory.base_memory_service import BaseMemoryService
    names = [n for n, _ in inspect.getmembers(BaseMemoryService, inspect.isfunction)
             if not n.startswith("_")]
    check("ADK's memory abstraction really has no delete",
          not any("delete" in n or "remove" in n for n in names), ", ".join(names))


async def chT(w: World) -> None:
    """The tower — every claim chapters 4 and 5 make about
    Memory Bank. Runs only when .env names one; nothing here can be faked."""
    print("\n\033[1mThe tower — Memory Bank\033[0m")
    if not TOWER:
        check("skipped: no AGENT_ENGINE in .env — run scripts/make_tower.py first", True)
        return
    edit("state", True); edit("prefix", True); edit("recall", True)
    t = World(tower_service())
    await tower.forget_all(t.memory, APP, USER)              # start from a bare shelf
    p = progress.read(t.sessions, t.memory, db=DB)
    check("the service is VertexAiMemoryBankService", p["memory_store"] == "VertexAiMemoryBankService")
    check("progress says the tower is lit — level 3, or 4 if the season is open too",
          p["level"] >= 3, f"level={p['level']}")

    sid = "T-a"
    for line in (SAY_FACTS, SAY_1, SAY_2, SAY_3, "I had soup for lunch and the weather was fine."):
        await t.say(sid, line)
    t0 = time.monotonic()
    await t.say(sid, "[close] that's all for today")
    waited = time.monotonic() - t0
    check("closing time blocks until the facts exist (wait_for_completion)",
          t.memory.writes == 1 and waited > 1.0, f"waited {waited:.1f}s")

    cards = await tower.cards(t.memory, APP, USER)
    check("floor three holds FACTS now, not your sentences",
          bool(cards) and all(c["kind"] == "fact" for c in cards),
          f"{len(cards)} cards · " + " | ".join(c["text"][:50] for c in cards[:3]))
    check("...none of them is a quote of what you said",
          not any(c["text"].strip().lower() == SAY_2.strip().lower() for c in cards))
    low = " ".join(c["text"].lower() for c in cards)
    check("topics kept the soup out", "soup" not in low and "weather" not in low)
    check("...and let the lantern in", "lantern" in low or "gift" in low or "night" in low)

    fresh = World(tower_service())                          # a new process, same tower
    again = await tower.cards(fresh.memory, APP, USER)
    check("a fresh process still sees the shelf — the memory left the process",
          len(again) == len(cards), f"{len(again)} cards")

    said = await fresh.say("T-b", "Is it me, or is it the lantern?")
    hits = (await fresh.state("T-b")).get("recalled") or []
    check("a question in different words still finds it — meaning, not keywords",
          len(hits) > 0, f"{len(hits)} hit(s) — she said: {said[:70]}")

    await fresh.say("T-c", "Actually — I think I do want a new one now.")
    await fresh.say("T-c", "[close] that's all for today")
    after = await tower.cards(fresh.memory, APP, USER)
    both = [c for c in after if "gift" in c["text"].lower() or "replace" in c["text"].lower()
            or "new one" in c["text"].lower()]
    check("consolidation revised the preference instead of adding a sibling",
          len(both) <= 1, " | ".join(c["text"][:60] for c in both))

    if after:
        gone = await tower.burn(fresh.memory, APP, USER, after[0]["id"])
        check("burning one page, on the real client", gone and
              len(await tower.cards(fresh.memory, APP, USER)) == len(after) - 1)
    n = await tower.forget_all(fresh.memory, APP, USER)
    check("forget-everything empties the tower", await tower.cards(fresh.memory, APP, USER) == [],
          f"forgot {n}")


async def ch5(w: World) -> None:
    print("\n\033[1mChapter 5, self-study — what she saw didn't stay\033[0m")
    edit("state", True); edit("prefix", True)
    photo = (ROOT / "img/lantern.jpg").read_bytes()
    sid = "ch5-a"
    if await w.sessions.get_session(app_name=APP, user_id=USER, session_id=sid) is None:
        await w.sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
    msg = types.Content(role="user", parts=[
        types.Part(text="[show] take a look at this"),
        types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=photo))])
    said = ""
    async for ev in w.runner().run_async(user_id=USER, session_id=sid, new_message=msg):
        info = (ev.model_dump().get("node_info") or {})
        if (info.get("path") or "").split("/")[-1].split("@")[0] == "vesper":
            parts = (ev.content.parts if ev.content else []) or []
            text = " ".join(p.text.strip() for p in parts if p.text and p.text.strip())
            said = text or said
    check("she reads the mark off it", "q7" in said.lower(), said[:90])
    slip = await w.slip(sid)
    check("...and writes down two characters nobody said",
          "q7" in str(slip.get("mark", "")).lower(), str(slip.get("mark")))
    kept = list((ROOT / ".artifacts/apps/archive/users/user/sessions"
                 / sid / "artifacts").glob("shown-*.jpg"))
    check("the photo itself is in the storeroom, not the tower", bool(kept),
          f"{len(kept)} file(s)")


async def ch6(w: World) -> None:
    print("\n\033[1mChapter 6 — nobody else has asked\033[0m")
    from archive import season
    if not season.is_open():
        check("skipped: the season is not in BigQuery — run scripts/season.sh first", True)
        return
    p = progress.read(w.sessions, w.memory, db=DB)
    check("the season unlocks floor four", p["season"] == "open")
    check("...but the badge still counts the floors actually lit", p["level"] < 4,
          f"level={p['level']} store={p['memory_store']}")

    alike = season.season_search("the flame keeps dying on me once the sun is down")
    m = alike.get("matches") or []
    check("VECTOR_SEARCH finds other visitors, by meaning", len(m) >= 3 and
          all(x["who"] and x["distance"] for x in m), f"{len(m)} · " + (m[0]["said"][:50] if m else ""))
    qwords = {"flame", "dying", "sun", "down"}
    check("...with no content word in common with the question",
          m and not (qwords & set(re.findall(r"[a-z]+", m[0]["said"].lower()))), m[0]["said"] if m else "")
    check("...and every match carries a mark — where to look next",
          m and all(x.get("mark") for x in m) and m[0]["mark"] == "q7", str([x.get("mark") for x in m]))

    known = season.season_known_issue("q7")
    check("one GQL MATCH through the property graph finds the other visits",
          known.get("count") == 31, known.get("path", "")[:100])
    check("...and what was finally wrong with them", bool(known.get("known_issue")) and
          "wick" in known["known_issue"], str(known.get("found_by")))
    check("...and says which edges it walked", "stamped" in known.get("walked", "") and
          "fixed" in known.get("walked", ""), known.get("walked", ""))
    check("a mark with no fix still walks, and says so",
          season.season_known_issue("p1").get("known_issue") is None and
          season.season_known_issue("p1").get("count") == 1)
    check("the statement is fixed — the tool takes a mark, never a query",
          "MATCH" in season.GQL and "@mark" in season.GQL)

    sid = "ch6-a"
    said = ""
    if await w.sessions.get_session(app_name=APP, user_id=USER, session_id=sid) is None:
        await w.sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
    msg = types.Content(role="user",
                        parts=[types.Part(text="[season] has anyone else had a q7 lantern go out at night?")])
    async for ev in w.runner().run_async(user_id=USER, session_id=sid, new_message=msg):
        info = (ev.model_dump().get("node_info") or {})
        if (info.get("path") or "").split("/")[-1].split("@")[0] == "elder":
            parts = (ev.content.parts if ev.content else []) or []
            text = " ".join(p.text.strip() for p in parts if p.text and p.text.strip())
            said = text or said
    low = said.lower()
    check("the elder answers from the warehouse, path and all",
          ("31" in said or "thirty-one" in low) and "wick" in low and "→" in said, said[:110])

    # no mark in the message: she must search first, take the mark the matches
    # carry, and only then walk — never present the matches as the answer
    sid = "ch6-b"
    said, calls = "", []
    if await w.sessions.get_session(app_name=APP, user_id=USER, session_id=sid) is None:
        await w.sessions.create_session(app_name=APP, user_id=USER, session_id=sid)
    msg = types.Content(role="user",
                        parts=[types.Part(text="[season] has anyone else had a lantern that keeps dying once the sun is down?")])
    async for ev in w.runner().run_async(user_id=USER, session_id=sid, new_message=msg):
        for part in ((ev.content.parts if ev.content else []) or []):
            if part.function_call:
                calls.append(part.function_call.name)
        info = (ev.model_dump().get("node_info") or {})
        if (info.get("path") or "").split("/")[-1].split("@")[0] == "elder":
            parts = (ev.content.parts if ev.content else []) or []
            text = " ".join(p.text.strip() for p in parts if p.text and p.text.strip())
            said = text or said
    check("with no mark, the elder searches first and walks second",
          calls[:1] == ["season_search"] and "season_known_issue" in calls, " → ".join(calls))
    check("...and still arrives at the thirty-one, with the path",
          ("31" in said or "thirty-one" in said.lower()) and "→" in said, said[:110])


async def main() -> None:
    which = sys.argv[1:] or ["1", "2", "3", "4", "T", "5", "6"]
    Path(DB).unlink(missing_ok=True)
    # a learner may have left an edit in; every chapter assumes the one before
    edits_off()
    try:
        w = World()
        for n in which:
            await {"1": ch1, "2": ch2, "3": ch3, "4": ch4, "T": chT,
                   "5": ch5, "6": ch6}[n](w)
    finally:
        edits_off()
        Path(DB).unlink(missing_ok=True)
    print()
    if _fails:
        print(f"\033[31m{len(_fails)} claim(s) the codelab makes are not true yet:\033[0m")
        for f in _fails:
            print("   ·", f)
        sys.exit(1)
    print("\033[32mevery claim in these chapters held.\033[0m")


if __name__ == "__main__":
    asyncio.run(main())
