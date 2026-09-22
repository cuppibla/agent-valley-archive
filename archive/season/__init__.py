"""Floor four — the season, read out of the company warehouse.

Chapter 6 loads the valley's past into BigQuery (`scripts/season.sh`): five
tables, embeddings generated in place, and one property graph laid over the
tables without moving a row. The elder reads it two ways, and BOTH statements
are fixed. The model never writes SQL or GQL: it fills in one parameter, the
code runs the same statement every time, and the answer comes back with the
path it walked.

    season_search(text)          what SOUNDS alike  — VECTOR_SEARCH over the
                                 embeddings; each match carries its mark, which
                                 is WHERE TO LOOK next
    season_known_issue(mark)     what IS connected  — one GQL MATCH through the
                                 graph: mark → every item stamped with it → who
                                 asked, what they said → the fix, if there is one

The dataset name comes from BQ_DATASET (default `archive`), the project from
GOOGLE_CLOUD_PROJECT — the same two the rest of the lab already reads.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

DATASET = os.environ.get("BQ_DATASET", "archive")
SEASON = "lamplight"

# The one walk the elder is allowed. Read it as a sentence: start at a mark,
# step back to every item stamped with it, back again to whoever asked about
# each one — and, if the mark has a fix, one step forward to it.
GQL = """
SELECT * FROM GRAPH_TABLE(`{ds}.season_graph`
  MATCH (m:Mark)<-[:stamped]-(i:Item)<-[a:asked]-(v:Visitor)
  WHERE m.mark = @mark AND a.season = @season
  OPTIONAL MATCH (m)-[:fixed]->(f:Fix)
  RETURN v.name AS who, a.said AS said, a.day AS day, f.what AS what, f.found_by AS found_by)
ORDER BY day"""

_client = None
_open: tuple[float, bool] = (0.0, False)
_checking = threading.Lock()


def _bq():
    """One client, made on first use — the import alone costs a second."""
    global _client
    if _client is None:
        from google.cloud import bigquery
        _client = bigquery.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return _client


def _check() -> bool:
    """One bounded round trip: does the embeddings table exist?"""
    try:
        _bq().get_table(f"{DATASET}.ask_embeddings", retry=None, timeout=8)
        return True
    except Exception:                                      # noqa: BLE001
        return False


def _refresh() -> None:
    global _open
    if not _checking.acquire(blocking=False):              # one check at a time
        return
    try:
        _open = (time.monotonic(), _check())
    finally:
        _checking.release()


def is_open(*, fresh: bool = False) -> bool:
    """Has the season been loaded — do the embeddings exist?

    The app asks on every poll, so the answer is cached for thirty seconds and
    refreshed on a background thread: a BigQuery round trip must never sit on
    the event loop the chat stream shares, or one slow answer turns into the
    tower going dark. The elder's tools pass `fresh=True`, so a season loaded a
    moment ago is not reported locked by a stale cache.
    """
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return False
    at, was = _open
    stale = time.monotonic() - at >= 30
    if fresh and (stale or not was):
        _refresh()                                         # on the caller's thread, bounded
        return _open[1]
    if stale:
        threading.Thread(target=_refresh, daemon=True).start()
    return was


def _run(sql: str, **params: str) -> list[Any]:
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in params.items()])
    return list(_bq().query(sql.replace("{ds}", DATASET), job_config=cfg))


def season_search(text: str) -> dict:
    """Search everything anyone said this season, by meaning.

    Args:
        text: What to look for — a description of the trouble, in any words.
    Returns:
        The closest things other visitors said: who said it, the mark on what
        they brought, and a distance. The mark is where to look next.
    """
    if not is_open(fresh=True):
        return {"status": "locked", "note": "the season is not in the warehouse yet"}
    rows = _run("""
        SELECT v.name AS who, i.mark AS mark, base.content AS said, ROUND(distance, 3) AS distance
        FROM VECTOR_SEARCH(
          TABLE `{ds}.ask_embeddings`, 'embedding',
          (SELECT ml_generate_embedding_result FROM ML.GENERATE_EMBEDDING(
             MODEL `{ds}.embedder`, (SELECT @q AS content))),
          top_k => 5)
        JOIN `{ds}.asks` a ON a.id = base.id
        JOIN `{ds}.items` i ON i.id = a.item_id
        JOIN `{ds}.visitors` v ON v.id = a.visitor_id
        ORDER BY distance""", q=text)
    return {"status": "success",
            "matches": [{"who": r.who, "mark": r.mark, "said": r.said, "distance": r.distance}
                        for r in rows],
            "note": "matched by meaning, not words. Similar is not connected: nothing here "
                    "says whether any of these has to do with this visitor's lantern — "
                    "but each match carries a mark, and a mark is where to look"}


def season_known_issue(mark: str, season: str = SEASON) -> dict:
    """Whether an item with this mark has a known issue this season — the
    governed traversal, one GQL MATCH: mark → the items stamped with it → who
    asked and what they said → the fix, if one was found.

    Args:
        mark: The little stamp on the base, e.g. q7.
        season: Which season to look in, e.g. lamplight.
    Returns:
        How many others came about it, what they said, what was found to be
        wrong, and the path that was walked to get there.
    """
    if not is_open(fresh=True):
        return {"status": "locked", "note": "the season is not in the warehouse yet"}
    try:
        rows = _run(GQL, mark=mark, season=season)
    except Exception as e:                                 # noqa: BLE001
        if "Property graph" in str(e) or "not found" in str(e).lower():
            return {"status": "locked",
                    "note": "the graph is not laid over the tables yet — "
                            "bash scripts/season.sh, step 10"}
        raise
    if not rows:
        return {"status": "not_found", "mark": mark, "season": season}
    said = list(dict.fromkeys(r.said for r in rows if r.said))
    fix = next((r for r in rows if r.what), None)
    path = [f"mark {mark}", f"{len(rows)} visits this season",
            f"{len(said)} different things said"]
    if fix:
        path.append(fix.what)
    return {"status": "success", "count": len(rows),
            "who": [r.who for r in rows[:6]], "said": said,
            "known_issue": fix.what if fix else None,
            "found_by": fix.found_by if fix else None,
            "walked": "(Mark)<-[stamped]-(Item)<-[asked]-(Visitor), then (Mark)-[fixed]->(Fix)",
            "path": " → ".join(path)}


def walk(mark: str = "q7") -> dict[str, Any]:
    """The path alone, without the model — what the app prints as the citation."""
    out = season_known_issue(mark)
    if out.get("status") != "success":
        return {"open": False, **out}
    return {"open": True, "steps": out["path"].split(" → "), **out}
