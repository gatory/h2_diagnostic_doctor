"""Save and load Snapshots as JSON files in the outputs folder.

    save_snapshot(snapshot, name)  -> outputs/discovery/<date>/<name>_<time>_<interface>.json
    load_snapshot(path)            -> Snapshot

Where files go is decided by h2_bridge.utils.output_paths; this module only turns a
Snapshot into JSON and back.
"""

from datetime import datetime

from h2_bridge.discovery.models import Endpoint, Participant, Snapshot

# Old field names -> current ones, so snapshots saved before a rename still load.
# (2026-11-24: Snapshot.iface/domain became interface/domain_id.)
_RENAMED_FIELDS = {"iface": "interface", "domain": "domain_id"}


def save_snapshot(snapshot, name="snapshot"):
    """Write a Snapshot as JSON to the outputs folder and return the path.

    The folder is fixed; `name` only sets the start of the file name.
    The time is when the run started:
    outputs/discovery/<date>/<name>_<time>_<interface>.json
    """
    import json
    from dataclasses import asdict

    from h2_bridge.utils.output_paths import output_path

    started = datetime.fromisoformat(snapshot.taken_at)
    path = output_path("discovery", name, snapshot.interface, when=started)

    with open(path, "w") as f:
        json.dump(asdict(snapshot), f, indent=2)
    return path


def load_snapshot(path):
    """Read a Snapshot back from a JSON file written by save_snapshot().

    Files saved with old field names (see _RENAMED_FIELDS) are read too.
    Raises ValueError if the file isn't a snapshot (wrong JSON shape).
    """
    import json

    with open(path) as f:
        data = json.load(f)

    # The run info fields (taken_at, host, ...) map 1:1 onto Snapshot's fields,
    # after renaming any old field names to their current ones.
    run_info = {
        _RENAMED_FIELDS.get(k, k): v for k, v in data.items() if k not in ("participants", "endpoints")
    }

    try:
        return Snapshot(
            **run_info,
            participants=[Participant(**p) for p in data["participants"]],
            endpoints=[Endpoint(**e) for e in data["endpoints"]],
        )
    except (KeyError, TypeError) as e:  # missing or unexpected fields
        raise ValueError(f"{path} is not a discovery snapshot: {e}") from None
