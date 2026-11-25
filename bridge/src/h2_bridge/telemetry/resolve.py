"""Topic names -> TopicSpecs, so any topic can be watched, not just the core ones.

    resolve_topics(["rt/lf/bmsstate", "rt/some/topic"], "eth10", 0)   # -> {name: TopicSpec}

Core topics come straight from CORE_TOPICS (instant). Any other name is looked up
with one short discovery run: the type its writers publish, then the SDK class for it.
"""

import difflib

from h2_bridge.telemetry.layout import CORE_TOPICS
from h2_bridge.telemetry.models import TopicSpec
from h2_bridge.telemetry.sources.base import TopicError
from h2_bridge.utils.sdk_types import lookup_type

# How long to listen for a non-core topic's writers.
DISCOVERY_SECS = 2.0


def resolve_topics(names, interface, domain_id, secs=DISCOVERY_SECS):
    """Return {name: TopicSpec} for `names`, in the order given.

    Runs discovery (once, for all of them) only if some name isn't a core topic.
    Raises TopicError if a topic isn't seen, has no writers, has writers of
    different types, or uses a type this SDK doesn't have.
    """
    others = [name for name in names if name not in CORE_TOPICS]
    found = _discover(others, interface, domain_id, secs) if others else {}
    return {name: CORE_TOPICS[name] if name in CORE_TOPICS else found[name] for name in names}


def _discover(names, interface, domain_id, secs):
    """{name: TopicSpec} for non-core `names`, from one discovery run."""
    from h2_bridge.discovery.analysis import group_by_topic
    from h2_bridge.discovery.collect import collect_snapshot

    seen = group_by_topic(collect_snapshot(interface, domain_id, secs))
    return {name: _spec_for(name, seen, secs) for name in names}


def _spec_for(name, seen, secs):
    """TopicSpec for one topic from discovery's {topic: {types, writers, readers}}."""
    if name not in seen:
        published = [topic for topic, entry in seen.items() if entry["writers"]]
        close = difflib.get_close_matches(name, published, n=3, cutoff=0.5)
        hint = f"did you mean: {', '.join(close)}?" if close else "is it publishing?"
        raise TopicError(f"no topic {name!r} seen in {secs:g} s; {hint}")

    writers = seen[name]["writers"]
    if not writers:
        raise TopicError(f"nothing publishes {name!r} (it only has readers)")

    types = sorted({w.type_name for w in writers})
    if len(types) > 1:  # e.g. unitree_go vs unitree_hg: guessing would silently get no data
        raise TopicError(f"{name!r} has writers of different types ({', '.join(types)}); can't pick one")

    msg_type = lookup_type(types[0])
    if msg_type is None:
        raise TopicError(f"{name!r} uses type {types[0]}, which this SDK doesn't have")
    return TopicSpec(name, msg_type, expected_hz=None)
