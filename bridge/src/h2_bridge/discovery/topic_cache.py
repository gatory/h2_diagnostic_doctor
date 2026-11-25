"""The topic cache: which type each topic carries, learned from discovery runs.

    update_topic_cache(snapshot)     # after a discovery run -> what changed
    load_topic_cache()               # {topic: {"type", "last_seen", "interface", "domain_id"}}

Kept in bridge/cache/topics.json so telemetry can watch a known topic without
waiting for discovery. Plain data only (type names, not SDK classes): turning
an entry into something to subscribe with is telemetry's job.

Rules:
- Only writers count: their type is the one that decodes the data.
- Writers that disagree on the type (e.g. unitree_go vs unitree_hg) give no
  entry, and remove an old one: guessing would silently get no data.
- A topic missing from a snapshot is kept (a short run can miss a slow
  program); `last_seen` says how old an entry is.
- An older snapshot never overwrites a newer entry.
"""

from datetime import datetime

from h2_bridge.discovery.analysis import group_by_topic
from h2_bridge.utils.cache import read_json, write_json

CACHE_FILE = "topics.json"
CACHE_VERSION = 1


def load_topic_cache():
    """{topic: entry} from the cache file ({} if missing, unreadable, or another version)."""
    data = read_json(CACHE_FILE, default={})
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    return data.get("topics", {})


def update_topic_cache(snapshot):
    """Merge one Snapshot into the cache and save it.

    Returns {"new": [topics], "changed": [topics], "removed": [topics]}.
    """
    topics = load_topic_cache()
    changes = {"new": [], "changed": [], "removed": []}
    seen_at = datetime.fromisoformat(snapshot.taken_at)

    for name, entry in group_by_topic(snapshot).items():
        writer_types = {w.type_name for w in entry["writers"]}
        old = topics.get(name)
        if old and datetime.fromisoformat(old["last_seen"]) > seen_at:
            continue  # this snapshot is older than what we know
        if len(writer_types) > 1:  # conflicting writers: don't claim a type
            if old:
                del topics[name]
                changes["removed"].append(name)
            continue
        if not writer_types:  # readers only: nothing to decode
            continue
        (type_name,) = writer_types
        if old is None:
            changes["new"].append(name)
        elif old["type"] != type_name:
            changes["changed"].append(name)
        topics[name] = {
            "type": type_name,
            "last_seen": snapshot.taken_at,
            "interface": snapshot.interface,
            "domain_id": snapshot.domain_id,
        }

    write_json(CACHE_FILE, {"version": CACHE_VERSION, "topics": topics})
    return changes
