"""Topic names -> TopicSpecs, so any topic can be watched, not just the core ones.

    resolve_topics(["rt/lf/bmsstate", "rt/some/topic"], "eth10", 0)   # -> {name: TopicSpec}

Each name is looked up in order, stopping at the first that knows it:
    1. CORE_TOPICS   hand-checked, instant
    2. topic cache   learned from earlier discovery runs (bridge/cache/topics.json), instant
    3. discovery     one short run for whatever is left; it also updates the cache
"""

import difflib

from h2_bridge.discovery.topic_cache import load_topic_cache
from h2_bridge.telemetry.core_topics import CORE_TOPICS
from h2_bridge.telemetry.models import TopicSpec
from h2_bridge.telemetry.sources.base_source import TopicError
from h2_bridge.utils.sdk_type_lookup import lookup_type

# How long to listen for a topic's writers when neither CORE_TOPICS nor the cache knows it.
DISCOVERY_SECS = 2.0


def resolve_topics(names, interface, domain_id, secs=DISCOVERY_SECS):
    """Return {name: TopicSpec} for `names`, in the order given.

    Runs discovery (once, for all of them) only for names that are neither core
    nor cached. Raises TopicError if a topic isn't seen, has no writers, has
    writers of different types, or uses a type this SDK doesn't have.
    """
    found = {}
    cache = None
    for name in names:
        if name in CORE_TOPICS:
            found[name] = CORE_TOPICS[name]
            continue
        cache = load_topic_cache() if cache is None else cache
        spec = _from_cache(name, cache)
        if spec:
            found[name] = spec

    missing = [name for name in names if name not in found]
    if missing:
        found.update(_discover(missing, interface, domain_id, secs))
    return {name: found[name] for name in names}


def _from_cache(name, cache):
    """TopicSpec from the cache entry, or None if there's none (or its type isn't in this SDK)."""
    entry = cache.get(name)
    msg_type = lookup_type(entry["type"]) if entry else None
    return TopicSpec(name, msg_type, expected_hz=None) if msg_type else None


def _discover(names, interface, domain_id, secs):
    """{name: TopicSpec} for `names`, from one discovery run (which also updates the cache)."""
    from h2_bridge.discovery.snapshot_views import group_by_topic
    from h2_bridge.discovery.collect import collect_snapshot
    from h2_bridge.discovery.topic_cache import update_topic_cache

    snapshot = collect_snapshot(interface, domain_id, secs)
    update_topic_cache(snapshot)
    seen = group_by_topic(snapshot)
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
