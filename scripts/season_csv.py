"""Write the valley's past as five CSVs — the files `season.sh` loads into BigQuery.

Chapters 1 to 5 generate every fact they use, which is why this lab stands
alone. Chapter 6 cannot: institutional memory is *other people's* memories, and
by construction you were not there. So the season ships as data, the way a
support system would export it — plain columns, explicit types.

    uv run python scripts/season_csv.py        # rewrites season/*.csv

    visitors   who came
    items      what they brought
    asks       one visit — who, what, which day, and what they said
    fixes      what turned out to be wrong, and who found it
    seasons    the window the whole thing sits in
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "season"
SEASON = "lamplight"

NAMES = [
    ("Bramble", "bear"), ("Clover", "bunny"), ("Rusty", "fox"), ("Pip", "owl"),
    ("Fern", "deer"), ("Mochi", "cat"), ("Ember", "dragon"), ("Biscuit", "dog"),
    ("Juniper", "deer"), ("Marlow", "otter"), ("Tansy", "mouse"), ("Wick", "moth"),
]

# What the thirty-one said. Deliberately in their own words — no two the same
# phrasing as the visitor's, so a search by meaning has something to find that
# a search by keyword would miss.
SAID = [
    "it goes out about an hour after I light it",
    "mine dies right when the wind picks up",
    "it only happens on the cold nights",
    "the flame sits low and then it's gone",
    "I've tried hanging it higher. No change.",
    "it burns fine for an evening and then never again",
    "the wick looks short to me, shorter than my old one",
    "I bought it at the spring fair, same as everyone",
    "it keeps cutting out after dark, which is the only time I need it",
    "the glass is clean, so it isn't that",
]

CAUSE = ("the wicks in the q7 batch were dipped too shallow — "
         "they drown in the oil and starve in an hour")


def write(name: str, header: list[str], rows: list[list[str]]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = random.Random(4)
    visitors, items, asks = [], [], []

    for i in range(31):                                  # the q7 lanterns
        name, species = NAMES[i % len(NAMES)]
        if i >= len(NAMES):
            name = f"{name} {i // len(NAMES) + 1}"
        vid, iid = f"v{i:03d}", f"i{i:03d}"
        visitors.append([vid, name, species])
        items.append([iid, "lantern", "q7"])
        asks.append([f"a{i:03d}", vid, iid, f"day {rng.randint(3, 88)}", SEASON,
                     SAID[i % len(SAID)]])

    # a few other things went wrong this season, so a count of "lanterns" is
    # not just a count of rows
    for i, (kind, mark, said) in enumerate([
            ("kettle", "b2", "it whistles when it is empty"),
            ("umbrella", "r4", "it will not close"),
            ("lantern", "p1", "the handle came away in my hand")]):
        vid, iid = f"o{i:03d}", f"j{i:03d}"
        visitors.append([vid, f"Someone {i}", "mouse"])
        items.append([iid, kind, mark])
        asks.append([f"b{i:03d}", vid, iid, f"day {rng.randint(3, 88)}", SEASON, said])

    write("visitors", ["id", "name", "species"], visitors)
    write("items", ["id", "kind", "mark"], items)
    write("asks", ["id", "visitor_id", "item_id", "day", "season", "said"], asks)
    write("fixes", ["mark", "what", "found_by", "day"],
          [["q7", CAUSE, "Marlow the otter", "day 62"]])
    write("seasons", ["id", "name", "opened", "closed"],
          [[SEASON, "the lamplight season", "day 1", "day 90"]])
    print(f"  season/ · {len(visitors)} visitors, {len(asks)} asks, 1 fix")


if __name__ == "__main__":
    main()
