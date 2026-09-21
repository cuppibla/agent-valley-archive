"""Every key the Archive remembers, in one place.

Three keys. Each one is written by somebody and read by somebody else.

    key            scope    written by        read by
    ────────────────────────────────────────────────────────────────
    case           ???      write_down        vesper, the slip, page
    recalled       session  recall            vesper, the tower panel
    user:visits    user     the service       the tower (floor one)

`CASE` is the line chapter 2 changes, and the change is five characters.
A key with no prefix lives for ONE VISIT — a session is a visit. `user:` makes
it follow the visitor into every visit after this.

    (none)   this visit          the desk
    user:    every visit         floor two, the drawer
    app:     everyone, forever   part of floor four
    temp:    this turn only      never even climbs the stairs
"""

from __future__ import annotations

# 👉 EDIT TWO — chapter 2. Five characters. A key with no prefix lives for one
#    visit; `user:` follows the visitor into every visit after this.
CASE = "case"

#: What `recall` found this turn. A session key, so it is gone next visit —
#: which is correct: it is a lookup result, not a memory.
RECALLED = "recalled"

#: How many visits this visitor has made. The service bumps it; floor one draws it.
VISITS = "user:visits"

#: The four lines on the slip, in the order Vesper fills them.
SLIP_FIELDS = ("no", "item", "mark", "symptom")
