"""What the tower is allowed to keep — chapter 5.

Two topics. `USER_PREFERENCES` is one of Memory Bank's managed topics, so it
costs nothing to ask for. `LANTERN_CONTEXT` is ours, and a custom topic lives in
two places, which is the thing to notice:

  * its DEFINITION — a label and one sentence saying what belongs in it — is
    configured on the tower itself, when `scripts/make_tower.py` builds it
    (`context_spec.memory_bank_config.customization_configs`);
  * its NAME is what closing time hands the tower in `FILING["allowed_topics"]`,
    as a `MemoryTopicId`, so extraction only keeps what those topics cover.

The lesson this file carries: what should NOT be remembered is not something you
resist writing into a prompt. It is something the topics make impossible to
extract.
"""

from __future__ import annotations

LANTERN_CONTEXT = {
    "label": "LANTERN_CONTEXT",
    "description": (
        "Why this visitor cares about the object they brought, what they have "
        "already tried to fix it, and what they are or are not willing to do "
        "about it. Durable dispositions only — never the case number, the mark, "
        "the date of the visit, pleasantries, or anything unrelated to the object."
    ),
}

#: What `FILING` hands the tower at closing time — the two topic ids.
TOPICS = [
    {"managed_memory_topic": "USER_PREFERENCES"},
    {"custom_memory_topic_label": LANTERN_CONTEXT["label"]},
]


def labels() -> list[str]:
    """The topic names, for the progress bar and the app."""
    return [t.get("managed_memory_topic") or t.get("custom_memory_topic_label") or "?"
            for t in TOPICS]


def tower_config() -> dict:
    """The Memory Bank half of the tower's configuration — what `make_tower.py`
    creates it with, and what it re-applies if the tower already stands."""
    return {"memory_bank_config": {"customization_configs": [
        {"memory_topics": [
            {"managed_memory_topic": {"managed_topic_enum": "USER_PREFERENCES"}},
            {"custom_memory_topic": LANTERN_CONTEXT},
        ]},
    ]}}
