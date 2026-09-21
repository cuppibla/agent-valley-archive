# The Archive — Agent Valley, week four

A tower that writes everything down, and an archivist who is pleased to meet you
every single time.

This is the lab repo for **Agent 101 Live, chapter four: Remember**. You climb
four rungs of agent memory — a visit, a visitor, what was said, the whole valley
— and every rung up happens because something fell out of the one below, on
screen, where you can watch it fall.

```
floor 4   the season        the whole valley   BigQuery, embedded in place chapter 6
floor 3   the tower         what was said      Vertex AI Memory Bank       chapters 3-5
floor 2   your drawer       this visitor       the `user:` prefix          chapter 2
floor 1   the books         every visit        SqliteSessionService        chapter 1
the desk  the slip          this visit         session.state               chapter 1
```

Three edits, each one line; one tower you build and connect; one warehouse you
load. The codelab is the guide; this is what it drives.

## Run it

```bash
uv sync
cp .env.example .env
uv run python scripts/preflight.py     # is this machine ready, and where am I?
bash valley.sh                         # the Archive: agent 8440 + app 3440
```

Open **http://localhost:3440**. Press ▶ Start, then The Archive, and pick
whoever has come to ask.

The workbench is the other window onto the same agent:

```bash
uv run adk web --session_service_uri=sqlite:///archive.db . --allow_origins="*"
```

Same file, same graph, two surfaces. Nothing in `archive/` knows which one is
looking at it.

## What is where

```
archive/
  agent.py      the graph: route → recall → vesper | file → goodnight | look | elder
  state.py      every key the Archive remembers, and how long each one lives
  service.py    the app's back end — one agent, re-imported on every message
  progress.py   how the app knows which edits you have made (it reads your code)
  tower.py      listing and forgetting: the two things ADK's memory API cannot do
  topics.py     what the tower is allowed to keep
  season/       chapter 6 — two fixed queries against the warehouse: VECTOR_SEARCH and one GQL MATCH
scripts/
  preflight.py      am I ready, and which floors are lit
  make_tower.py     build the Agent Engine that Memory Bank lives on, topics and all
  season_csv.py     the valley's past as five CSVs
  season.sh         GCS → BigQuery → embeddings in place → a property graph over the tables
  shelf.py          floor three from the terminal — list the cards, or burn one
  walk.py           walk the codelab chapter by chapter against the real agent
site/             the Archive itself — Next.js, talks to the service over SSE
```

## The one that keeps everyone honest

```bash
uv run python scripts/walk.py        # all six chapters, plus the tower when .env names one
uv run python scripts/walk.py 3      # just one
```

`walk.py` is not a unit test. Every assertion in it is a **sentence the codelab
says to the learner**, applied to the real agent with the real edits applied and
undone. When it fails, the prose is wrong, not just the code.
